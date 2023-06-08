# -*- coding:utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero
import logging
_logger = logging.getLogger(__name__)

class HrPayslipLine(models.Model):
    _inherit = 'hr.payslip.line'






    def _get_partner_id(self, credit_account):
        """
        Get partner_id of slip line to use in account_move_line
        """
        # use partner of salary rule or fallback on employee's address
        register_partner_id = self.salary_rule_id.register_id.partner_id
        partner_id = register_partner_id.id or self.slip_id.employee_id.address_home_id.id
        if credit_account:
            if register_partner_id or self.salary_rule_id.account_credit.internal_type in ('receivable', 'payable'):
                return partner_id
        else:
            if register_partner_id or self.salary_rule_id.account_debit.internal_type in ('receivable', 'payable'):
                return partner_id
        return False


class HrPayslipInput(models.Model):
    _inherit = 'hr.payslip.input'
    salary_rule = fields.Many2one('hr.salary.rule','Name')

    # occurs when user add salary rule name to other inputs
    # change the value of name, code and contract_id accordingly
    @api.onchange('salary_rule')
    def onchange_salary_rule(self):
        salary_rule_id = self.salary_rule

        self.name = salary_rule_id.name
        self.code = salary_rule_id.code

        #self.contract = self.env['hr.payslip'].search().contract_id


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    date = fields.Date('Date Account', states={'draft': [('readonly', False)]}, readonly=True,
                       help="Keep empty to use the period of the validation(Payslip) date.")
    journal_id = fields.Many2one('account.journal', 'Salary Journal', readonly=True, required=True,
                                 states={'draft': [('readonly', False)]},
                                 default=lambda self: self.env['account.journal'].search([('type', '=', 'general')],
                                                                                         limit=1))
    move_id = fields.Many2one('account.move', 'Accounting Entry', readonly=True, copy=False)

    @api.model
    def create(self, vals):
        if 'journal_id' in self.env.context:
            vals['journal_id'] = self.env.context.get('journal_id')
        return super(HrPayslip, self).create(vals)

    def compute_sheet(self):
        res = super(HrPayslip, self).compute_sheet()

        basic = allowance = deductions = 0.0
        for line in self.line_ids:
            for input_line in self.input_line_ids:
                if input_line.code == line.code:
                    line.amount = input_line.amount

            if line.category_id.code == "ALW":
                allowance += line.amount

            elif line.category_id.code == "DED":
                deductions += line.amount

            elif line.category_id.code == "BASIC":
                basic = line.amount

            elif line.code == "GROSS":
                line.amount = basic + allowance

            elif line.code == "NET":
                line.amount = basic + allowance - deductions

        return res

    @api.onchange('contract_id')
    def onchange_contract(self):
        super(HrPayslip, self).onchange_contract()
        self.journal_id = self.contract_id.journal_id.id or (
                    not self.contract_id and self.default_get(['journal_id'])['journal_id'])

    def action_payslip_cancel(self):
        moves = self.mapped('move_id')
        moves.filtered(lambda x: x.state == 'posted').button_cancel()
        moves.unlink()
        return super(HrPayslip, self).action_payslip_cancel()

    def calc_sal_tax(self):
        pass

    def action_payslip_done(self):
        res = super(HrPayslip, self).action_payslip_done()

        for slip in self:
            line_ids = []
            debit_sum = 0.0
            credit_sum = 0.0
            date = slip.date or slip.date_to
            currency = slip.company_id.currency_id

            name = _('Payslip of %s') % (slip.employee_id.name)
            move_dict = {
                'narration': name,
                'ref': slip.number,
                'journal_id': slip.journal_id.id,
                'date': date,
            }
            for line in slip.details_by_salary_rule_category:
                amount = currency.round(slip.credit_note and -line.total or line.total)
                if currency.is_zero(amount):
                    continue
                debit_account_id = line.salary_rule_id.account_debit.id
                credit_account_id = line.salary_rule_id.account_credit.id

                if debit_account_id:
                    debit_line = (0, 0, {
                        'name': line.name,
                        'partner_id': line._get_partner_id(credit_account=False),
                        'account_id': debit_account_id,
                        'journal_id': slip.journal_id.id,
                        'date': date,
                        'debit': amount > 0.0 and amount or 0.0,
                        'credit': amount < 0.0 and -amount or 0.0,
                        'analytic_account_id': line.salary_rule_id.analytic_account_id.id,
                        # 'tax_line_id': line.salary_rule_id.account_tax_id.id,
                    })
                    line_ids.append(debit_line)
                    debit_sum += debit_line[2]['debit'] - debit_line[2]['credit']
                if credit_account_id:
                    credit_line = (0, 0, {
                        'name': line.name,
                        'partner_id': line._get_partner_id(credit_account=True),
                        'account_id': credit_account_id,
                        'journal_id': slip.journal_id.id,
                        'date': date,
                        'debit': amount < 0.0 and -amount or 0.0,
                        'credit': amount > 0.0 and amount or 0.0,
                        'analytic_account_id': line.salary_rule_id.analytic_account_id.id,
                        # 'tax_line_id': line.salary_rule_id.account_tax_id.id,
                    })
                    line_ids.append(credit_line)
                    credit_sum += credit_line[2]['credit'] - credit_line[2]['debit']

            move_dict['line_ids'] = line_ids
            move = self.env['account.move'].create(move_dict)
            slip.write({'move_id': move.id, 'date': date})
            
            if not move.line_ids:
                raise UserError(_("As you installed the payroll accounting module you have to choose Debit and Credit"
                                  " account for at least one salary rule in the choosen Salary Structure."))
            move.post()
        return res


class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    analytic_account_id = fields.Many2one('account.analytic.account', 'Analytic Account', help="Analytic account")
    account_tax_id = fields.Many2one('account.tax', 'Tax', help="Tax account")
    account_debit = fields.Many2one('account.account', 'Debit Account', help="Debit account", domain=[('deprecated', '=', False)])
    account_credit = fields.Many2one('account.account', 'Credit Account', help="CRedit account", domain=[('deprecated', '=', False)])


class HrContract(models.Model):
    _inherit = 'hr.contract'
    _description = 'Employee Contract'

    analytic_account_id = fields.Many2one('account.analytic.account', 'Analytic Account', help="Analytic account")
    journal_id = fields.Many2one('account.journal', 'Salary Journal', help="Journal")


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    journal_id = fields.Many2one('account.journal', 'Salary Journal', states={'draft': [('readonly', False)]},
                                 readonly=True,
                                 required=True, help="journal",
                                 default=lambda self: self.env['account.journal'].search([('type', '=', 'general')],
                                                                                         limit=1))