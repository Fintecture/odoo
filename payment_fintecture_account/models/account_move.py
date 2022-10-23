from odoo.addons.payment_fintecture.const import PAYMENT_ACQUIRER_NAME

from odoo import fields, models
from odoo.exceptions import UserError

class AccountMove(models.Model):
    _inherit = 'account.move'

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
    fintecture_invoice_viban = fields.Boolean(
        string="Include virtual IBAN in invoices",
        compute="_compute_fintecture_configuration"
    )
    fintecture_invoice_link_qr = fields.Boolean(
        string="Include link/QR in invoices",
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
        move = self.sudo()
        country_id = move.partner_id.country_id.id if move.partner_id.country_id else self.env.company.country_id.id
        if not country_id:
            raise UserError("The selected customer or the company must to have a country selected.")
        return {
            'acquirer_id': acquirer.id,
            'reference': move.name,
            'amount': move.amount_residual,
            'currency_id': move.currency_id.id,
            'partner_id': move.partner_id.id,
            'partner_country_id': country_id,
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
        PaymentTrxObj = self.env['payment.transaction'].sudo()
        acquirer = self.env['payment.acquirer'].get_fintecture_acquirer()
        for move in self:
            if acquirer.state == 'disabled':
                move.fintecture_payment_link = False
                move.fintecture_iban_holder = False
                move.fintecture_iban_account = False
                move.fintecture_iban_swift_bic = False
                move.fintecture_iban_bank_name = False
                move.fintecture_iban_bank_address = False
                move.fintecture_payment_qr = False
                move.fintecture_first_use_date = False
                move.fintecture_is_enabled = False
                continue

            move.fintecture_is_enabled = True
            trx_data = move._prepare_fintecture_transaction_values()
            trxs = move.transaction_ids.filtered(
                lambda x: x.acquirer_id and x.acquirer_id.provider == PAYMENT_ACQUIRER_NAME and x.state != 'done'
            )
            if len(trxs) <= 0:
                trx = PaymentTrxObj.sudo().search([
                    ('reference', '=', move.name),
                    ('acquirer_id.company_id', '=', move.company_id.id)
                ], limit=1)
                if not trx:
                    trx = PaymentTrxObj.create(trx_data)
                    move.transaction_ids = [(4, trx.id)]
                else:
                    trx.write(trx_data)
            else:
                trx = trxs[-1]

            if trx.acquirer_id.fintecture_viban_unique_key == 'invoice':
                unique_key = "invoice.{}".format(str(move.id))
            elif trx.acquirer_id.fintecture_viban_unique_key == 'journal':
                unique_key = "journal.{}".format(str(move.journal_id.id))
            elif trx.acquirer_id.fintecture_viban_unique_key == 'project' and move.line_ids[0].analytic_account_id:
                unique_key = "project.{}".format(str(move.line_ids[0].analytic_account_id.id))
            else:
                unique_key = False

            trx.with_context(
                unique_key=unique_key
            )._get_fintecture_processing_values()

            move.fintecture_payment_link = trx.fintecture_url
            move.fintecture_iban_holder = trx.fintecture_iban_holder
            move.fintecture_iban_account = trx.fintecture_iban_account
            move.fintecture_iban_swift_bic = trx.fintecture_iban_swift_bic
            move.fintecture_iban_bank_name = trx.fintecture_iban_bank_name
            move.fintecture_iban_bank_address = trx.fintecture_iban_bank_address
            move.fintecture_payment_qr = trx.fintecture_create_qr()

            search_first_move = PaymentTrxObj.search([
                ('acquirer_id.provider', '=', PAYMENT_ACQUIRER_NAME),
                ('partner_id', '=', move.partner_id.id)
            ], limit=1, order="id ASC")

            if not search_first_move:
                move.fintecture_first_use_date = fields.Date.today()
            else:
                move.fintecture_first_use_date = search_first_move.create_date.date()

    def _compute_fintecture_configuration(self):
        """
        This compute method check from the acquirer if has this 2 options avaiable to be used in docs and email template.
        :return: Void
        """
        acquirer = self.env['payment.acquirer'].get_fintecture_acquirer()
        for move in self:
            move.fintecture_invoice_viban = acquirer.fintecture_invoice_viban
            move.fintecture_invoice_link_qr = acquirer.fintecture_invoice_link_qr
