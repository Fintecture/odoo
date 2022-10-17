from odoo.addons.payment_fintecture.const import PAYMENT_ACQUIRER_NAME

from odoo import fields, models


class FintectureSale(models.Model):
    _inherit = "sale.order"

    fintecture_is_enabled = fields.Boolean(
        string="Fintecture enabled",
        compute="_compute_fintecture_payment_link"
    )
    fintecture_payment_link = fields.Char(
        string="Fintecture payment link",
        compute="_compute_fintecture_payment_link"
    )
    fintecture_payment_qr = fields.Binary(
        string="Fintecture QR",
        compute="_compute_fintecture_payment_link"
    )
    fintecture_iban_holder = fields.Char(
        string="Fintecture IBAN holder",
        compute="_compute_fintecture_payment_link"
    )
    fintecture_iban_account = fields.Char(
        string="Fintecture IBAN account",
        compute="_compute_fintecture_payment_link"
    )
    fintecture_iban_swift_bic = fields.Char(
        string="Fintecture IBAN SWIFT/BIC",
        compute="_compute_fintecture_payment_link"
    )
    fintecture_iban_bank_name = fields.Char(
        string="Fintecture IBAN bank name",
        compute="_compute_fintecture_payment_link"
    )
    fintecture_iban_bank_address = fields.Char(
        string="Fintecture IBAN bank address",
        compute="_compute_fintecture_payment_link"
    )
    fintecture_first_use_date = fields.Date(
        string="Fintecture first time used",
        compute="_compute_fintecture_payment_link"
    )
    fintecture_sale_viban = fields.Boolean(
        string="Include virtual IBAN in quotes",
        compute="_compute_fintecture_configuration"
    )
    fintecture_sale_link_qr = fields.Boolean(
        string="Include link/QR in quotes",
        compute="_compute_fintecture_configuration"
    )

    def _prepare_fintecture_transaction_values(self):
        """
        This private method build the dictionary for build the transaction, is separated because is a good practice in Odoo
        to make code extensible.
        :return: Void
        """
        self.ensure_one()
        acquirer = self.env['payment.acquirer'].get_fintecture_acquirer()
        order = self.sudo()
        return {
            'acquirer_id': acquirer.id,
            'reference': order.name,
            'amount': order.amount_total,
            'currency_id': order.currency_id.id,
            'partner_id': order.partner_id.id,
            'sale_order_ids': [(4, order.id)]
        }

    def has_to_be_paid(self, include_draft=False):
        result = super(FintectureSale, self).has_to_be_paid(include_draft=True)
        return result

    def _compute_fintecture_payment_link(self):
        """
        This compute method check if the fintecture module is enabled/sandbox. If it is then check if there are any
        fintecture transaction already opened and return the transaction data in a compute fields to can be used
        by the documents and email templates.
        If any fintecture transaction exists this method creates the transaction and link with the native transaction_ids
        of this extending module.
        :return: Void
        """
        PaymentTrxObj = self.env['payment.transaction'].sudo()
        acquirer = self.env['payment.acquirer'].get_fintecture_acquirer()
        for order in self:
            if acquirer.state == 'disabled':
                order.fintecture_payment_link = False
                order.fintecture_iban_holder = False
                order.fintecture_iban_account = False
                order.fintecture_iban_swift_bic = False
                order.fintecture_iban_bank_name = False
                order.fintecture_iban_bank_address = False
                order.fintecture_payment_qr = False
                order.fintecture_first_use_date = False
                order.fintecture_is_enabled = False
                continue

            order.fintecture_is_enabled = True
            trx_data = order._prepare_fintecture_transaction_values()
            trxs = order.transaction_ids.filtered(
                lambda x: x.acquirer_id.provider == PAYMENT_ACQUIRER_NAME and x.state != 'done'
            )
            if len(trxs) <= 0:
                trx = PaymentTrxObj.sudo().search([
                    ('reference', '=', order.name)
                ], limit=1)
                if not trx:
                    trx = PaymentTrxObj.create(trx_data)
                else:
                    trx.write(trx_data)
            else:
                trx = trxs[-1]

            if trx.acquirer_id.fintecture_viban_unique_key == 'project' and hasattr(
                    order, 'project_id'
            ) and order.project_id:
                unique_key = "project.{}".format(str(order.project_id.id))
            else:
                unique_key = False

            trx.with_context(
                unique_key=unique_key
            )._get_processing_values()

            order.fintecture_payment_link = trx.fintecture_url
            order.fintecture_iban_holder = trx.fintecture_iban_holder
            order.fintecture_iban_account = trx.fintecture_iban_account
            order.fintecture_iban_swift_bic = trx.fintecture_iban_swift_bic
            order.fintecture_iban_bank_name = trx.fintecture_iban_bank_name
            order.fintecture_iban_bank_address = trx.fintecture_iban_bank_address
            order.fintecture_payment_qr = trx.fintecture_create_qr()
            search_first_move = PaymentTrxObj.search([
                ('acquirer_id.provider', '=', PAYMENT_ACQUIRER_NAME),
                ('partner_id', '=', order.partner_id.id)
            ], limit=1, order="id ASC")
            if not search_first_move:
                order.fintecture_first_use_date = fields.Date.today()
            else:
                order.fintecture_first_use_date = search_first_move.create_date.date()

    def _compute_fintecture_configuration(self):
        """
        This compute method check from the acquirer if has this 2 options avaiable to be used in docs and email template.
        :return: Void
        """
        acquirer = self.env['payment.acquirer'].get_fintecture_acquirer()
        for move in self:
            move.fintecture_sale_viban = acquirer.fintecture_sale_viban
            move.fintecture_sale_link_qr = acquirer.fintecture_sale_link_qr
