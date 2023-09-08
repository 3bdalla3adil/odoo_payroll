from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class ResCompanyInheritedSal(models.Model):
    _inherit = "res.company"

    main_sal_acc = fields.Many2one('account.account', string='Main Sal Account')
    advance_sal_acc = fields.Many2one('account.account', string='Advance Sal Account')
    pf_acc = fields.Many2one('account.account', string='PF Account(EC)')
    gratuity_acc = fields.Many2one('account.account', string='Gratuity Account')
    retire_fund_acc = fields.Many2one('account.account', string='RF Payable Account')
    ssf_pay_acc = fields.Many2one('account.account', string='SSF Payable Account')
    tds_pay_acc = fields.Many2one('account.account', string='TDS Payable Account')
    sal_pay_acc = fields.Many2one('account.account', string='Salary Payable Account')
    insurance_acc = fields.Many2one('account.account', string='Insurance Account')
    fuel_acc = fields.Many2one('account.account', string='Fuel Account')

class SalResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    main_sal_acc = fields.Many2one('account.account', string='Main Sal Account',related='company_id.main_sal_acc', readonly=False)
    advance_sal_acc = fields.Many2one('account.account', string='Advance Sal Account',related='company_id.advance_sal_acc', readonly=False)
    pf_acc = fields.Many2one('account.account', string='PF Account(EC)',related='company_id.pf_acc', readonly=False)
    gratuity_acc = fields.Many2one('account.account', string='Gratuity Account',related='company_id.gratuity_acc', readonly=False)
    retire_fund_acc = fields.Many2one('account.account', string='RF Payable Account',related='company_id.retire_fund_acc', readonly=False)
    ssf_pay_acc = fields.Many2one('account.account', string='SSF Payable Account',related='company_id.ssf_pay_acc', readonly=False)
    tds_pay_acc = fields.Many2one('account.account', string='TDS Payable Account',related='company_id.tds_pay_acc', readonly=False)
    sal_pay_acc = fields.Many2one('account.account', string='Salary Payable Account',related='company_id.sal_pay_acc', readonly=False)
    insurance_acc = fields.Many2one('account.account', string='Insurance Account', related='company_id.insurance_acc', readonly=False)
    fuel_acc = fields.Many2one('account.account', string='Fuel Account', related='company_id.fuel_acc', readonly=False)