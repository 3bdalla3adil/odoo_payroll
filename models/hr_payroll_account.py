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

    def action_payslip_done(self):
        # res = super(HrPayslip, self).action_payslip_done()
        if not self.company_id.gratuity_acc:
                raise UserError(_("Please configure Payroll Accounts"))
        if not self.contract_id.analytic_account_id:
                raise UserError(_("Please configure Analytic Account id on contract"))
        for slip in self:
            if not self.move_id:
                line_ids = []
                
                date = slip.date or slip.date_to
                currency = slip.company_id.currency_id
                name = _('Payslip of %s') % (slip.employee_id.name)
                move_dict = {
                    'narration': name,
                    'ref': slip.number,
                    'journal_id': slip.journal_id.id,
                    'date': date,
                }
                net_amount = pf_amount = gratuity_amount = ssf_amt = tds_amt = total_tds_ssf = rf_amount = dr_net_amount = cr_net_amount = 0.0
                all_amounts_dr = []
                all_amounts_cr = []
                # for line in slip.line_ids:
                    # amount = currency.round(slip.credit_note and -line.total or line.total)
                    # if currency.is_zero(amount):
                    #     continue
                net_amount = slip.line_ids.filtered(lambda l: l.salary_rule_id.sal_rule_type  == 'is_gross').amount 
                advance_amount = slip.line_ids.filtered(lambda l: l.salary_rule_id.sal_rule_type  == 'is_advance').amount 
                pf_amount = slip.line_ids.filtered(lambda l: l.salary_rule_id.sal_rule_type  == 'is_pf').amount 
                gratuity_amount = slip.line_ids.filtered(lambda l: l.salary_rule_id.sal_rule_type  == 'is_gra').amount 
                ssf_amt = slip.line_ids.filtered(lambda l: l.salary_rule_id.sal_rule_type  == 'is_ssf').amount 
                tds_amt = slip.line_ids.filtered(lambda l: l.salary_rule_id.sal_rule_type  == 'is_tds').amount 
                insur_amt = slip.line_ids.filtered(lambda l: l.salary_rule_id.sal_rule_type  == 'is_insurance').amount 

                total_tds_ssf = ssf_amt + tds_amt
                rf_amount = (pf_amount*2) + gratuity_amount
                dr_net_amount = net_amount - pf_amount - gratuity_amount
                cr_net_amount = net_amount - total_tds_ssf - rf_amount - advance_amount - insur_amt

                all_amounts_dr.append(
                    {
                        'amt': dr_net_amount,
                        'acc_id': slip.company_id.main_sal_acc.id
                    })
                all_amounts_dr.append(
                    {
                        'amt': pf_amount,
                        'acc_id': slip.company_id.pf_acc.id
                    })
                all_amounts_dr.append(
                    {
                        'amt': gratuity_amount,
                        'acc_id': slip.company_id.gratuity_acc.id
                    })
                
                all_amounts_cr.append(
                    {
                        'amt': ssf_amt,
                        'acc_id': slip.company_id.ssf_pay_acc.id
                    })

                all_amounts_cr.append(
                    {
                        'amt': advance_amount,
                        'acc_id': slip.company_id.advance_sal_acc.id
                    })

                all_amounts_cr.append(
                    {
                        'amt': tds_amt,
                        'acc_id': slip.company_id.tds_pay_acc.id
                    })
                all_amounts_cr.append(
                    {
                        'amt': rf_amount,
                        'acc_id': slip.company_id.retire_fund_acc.id
                    })
                all_amounts_cr.append(
                    {
                        'amt': insur_amt,
                        'acc_id': slip.company_id.insurance_acc.id
                    })
                all_amounts_cr.append(
                    {
                        'amt': cr_net_amount,
                        'acc_id': slip.company_id.sal_pay_acc.id
                    })
                
                for k in all_amounts_dr:
                    line_data = (0, 0, {
                        'name': slip.number,
                        'partner_id': False,
                        'account_id': k['acc_id'],
                        'journal_id': slip.journal_id.id,
                        'date': date,
                        'debit': k['amt'] > 0.0 and k['amt'] or 0.0,
                        'credit': 0.0,
                        'analytic_account_id': slip.contract_id.analytic_account_id.id,
                        # 'tax_line_id': line.salary_rule_id.account_tax_id.id,
                    })
                    line_ids.append(line_data)
                for k in all_amounts_cr:
                    line_data = (0, 0, {
                        'name': slip.number,
                        'partner_id': False,
                        'account_id': k['acc_id'],
                        'journal_id': slip.journal_id.id,
                        'date': date,
                        'credit': k['amt'] > 0.0 and k['amt'] or 0.0,
                        'debit': 0.0,
                        'analytic_account_id': slip.contract_id.analytic_account_id.id,
                        # 'tax_line_id': line.salary_rule_id.account_tax_id.id,
                    })
                    line_ids.append(line_data)

                move_dict['line_ids'] = line_ids
                move = self.env['account.move'].create(move_dict)
                slip.write({'move_id': move.id, 'date': date})
                print(move)
                print(move.line_ids)
                if not move.line_ids:
                    raise UserError(_("As you installed the payroll accounting module you have to choose Debit and Credit"
                                    " account for at least one salary rule in the choosen Salary Structure."))
                move.post()
        if self.move_id:
            if self.move_id.state == 'posted':
                _logger.info("====posted===OOO")
                self.tax_hr_lines_ids.calc_tax_paid()
        return self.write({'state': 'done'})


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
