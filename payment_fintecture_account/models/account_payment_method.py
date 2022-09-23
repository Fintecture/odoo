# -*- coding: utf-8 -*-

from odoo import api, models
from odoo.addons.payment_fintecture.const import PAYMENT_ACQUIRER_NAME


class AccountPaymentMethod(models.Model):
    _inherit = 'account.payment.method'

    @api.model
    def _get_payment_method_information(self):
        res = super()._get_payment_method_information()
        res[PAYMENT_ACQUIRER_NAME] = {
            'mode': 'unique',
            'domain': [
                ('type', '=', 'bank')
            ]
        }
        return res
