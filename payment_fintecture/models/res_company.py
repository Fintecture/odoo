from odoo.addons.payment_fintecture.const import PAYMENT_ACQUIRER_NAME

from odoo import models, api
from odoo.exceptions import UserError


class FintectureCompany(models.Model):
    _inherit = "res.company"

    @api.model
    def create(self, vals):
        company = super(FintectureCompany, self).create(vals)
        company.fintecture_create_acquirer()
        return company

    def fintecture_create_acquirer(self):
        rule = self.env.ref('payment.payment_acquirer_company_rule')
        rule.write({'active': False})
        acquirer = self.env.ref('payment_fintecture.payment_acquirer_fintecture')
        if not acquirer:
            return False
        for company in self:
            search_acquirer = self.env['payment.acquirer'].with_company(company).search([
                ('provider', '=', PAYMENT_ACQUIRER_NAME),
                ('company_id', '=', company.id)
            ], limit=1)
            if not search_acquirer:
                acquirer.sudo().copy({
                    'company_id': company.id
                })
        rule.write({'active': True})
