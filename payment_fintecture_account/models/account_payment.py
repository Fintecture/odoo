import logging

from odoo.addons.payment_fintecture.const import CALLBACK_URL, PAYMENT_ACQUIRER_NAME

from odoo import fields, models

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    # related fields
    fintecture_payment_link = fields.Char(
        string="Fintecture payment link",
        compute="_compute_fintecture_payment_link"
    )
    fintecture_payment_qr = fields.Binary(
        string="Fintecture QR",
        compute="_compute_fintecture_payment_link"
    )

    def _prepare_fintecture_transaction_values(self):
        """
        This private method build the dictionary for build the transaction, is separated because is a good practice in Odoo
        to make code extensible.
        :return: Void
        """
        self.ensure_one()
        acquirer = self.env['payment.acquirer'].get_fintecture_acquirer()
        payment = self.sudo()
        return {
            'acquirer_id': acquirer.id,
            'reference': payment.name,
            'amount': payment.amount_company_currency_signed,
            'currency_id': payment.currency_id.id,
            'partner_id': payment.partner_id.id,
            'operation': 'online_redirect',
        }

    def _compute_fintecture_payment_link(self):
        """
       This compute method check if the fintecture module is enabled/sandbox. If it is then check if there are any
       fintecture transaction already opened and return the transaction data in a compute fields to can be used
       by the documents and email templates.
       If any fintecture transaction exists this method creates the transaction and link with the native transaction_ids
       of this extending module.
       :return: Void
       """
        acquirer = self.env['payment.acquirer'].get_fintecture_acquirer()
        PaymentTrxObj = self.env['payment.transaction'].sudo()
        for pay in self:
            if pay.state in ['draft', 'cancel'] or acquirer.state == 'disabled':
                pay.fintecture_payment_link = False
                pay.fintecture_payment_qr = False
                continue

            trx_data = pay._prepare_fintecture_transaction_values()
            trxs = pay.transaction_ids.filtered(lambda x: x.acquirer_id.provider == PAYMENT_ACQUIRER_NAME)
            if len(trxs) <= 0:
                trx = PaymentTrxObj.sudo().search([
                    ('reference', '=', pay.name)
                ], limit=1)
                if not trx:
                    trx = PaymentTrxObj.create(trx_data)
                else:
                    trx.write(trx_data)
            else:
                trx = trxs[-1]
            trx._get_processing_values()
            pay.fintecture_payment_link = trx.fintecture_url
            pay.fintecture_payment_qr = trx.fintecture_create_qr()
