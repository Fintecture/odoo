import logging
import pprint
import uuid
import qrcode
import base64
import json

from io import BytesIO
from datetime import date

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.payment_fintecture import utils as fintecture_utils
from odoo.addons.payment_fintecture.const import INTENT_STATUS_MAPPING, PAYMENT_METHOD_TYPES, CHECKOUT_URL, \
    VALIDATION_URL, CALLBACK_URL, PAYMENT_ACQUIRER_NAME

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    fintecture_payment_intent = fields.Char(
        string="Fintecture Payment Intent ID",
        readonly=True
    )
    fintecture_url = fields.Char(
        string="Fintecture URL"
    )
    fintecture_virtual_beneficiary = fields.Text(
        string="Fintecture Virtual Beneficiary"
    )
    fintecture_iban_holder = fields.Char(
        string="Fintecture IBAN holder",
        compute="_compute_fintecture_iban"
    )
    fintecture_iban_account = fields.Char(
        string="Fintecture IBAN account",
        compute="_compute_fintecture_iban"
    )
    fintecture_iban_swift_bic = fields.Char(
        string="Fintecture IBAN SWIFT/BIC",
        compute="_compute_fintecture_iban"
    )
    fintecture_iban_bank_name = fields.Char(
        string="Fintecture IBAN bank name",
        compute="_compute_fintecture_iban"
    )
    fintecture_iban_bank_address = fields.Char(
        string="Fintecture IBAN bank address",
        compute="_compute_fintecture_iban"
    )

    def _compute_fintecture_iban(self):
        for trx in self:
            if not trx.fintecture_virtual_beneficiary:
                trx.fintecture_iban_holder = ''
                trx.fintecture_iban_account = ''
                trx.fintecture_iban_swift_bic = ''
                trx.fintecture_iban_bank_name = ''
                trx.fintecture_iban_bank_address = ''
                continue

            data = json.loads(trx.fintecture_virtual_beneficiary)

            if not data or 'iban' not in data:
                trx.fintecture_iban_holder = ''
                trx.fintecture_iban_account = ''
                trx.fintecture_iban_swift_bic = ''
                trx.fintecture_iban_bank_name = ''
                trx.fintecture_iban_bank_address = ''
                continue

            trx.fintecture_iban_holder = data['name']
            trx.fintecture_iban_account = data['iban']
            trx.fintecture_iban_swift_bic = data['swift_bic']
            trx.fintecture_iban_bank_name = data['bank_name']

            addresses = []
            if 'street' in data and data['street'] != '':
                addresses.append(data['street'])
            if 'number' in data and data['number'] != '':
                addresses.append(data['number'])
            if 'zip' in data and data['zip'] != '':
                addresses.append(data['zip'])
            if 'city' in data and data['city'] != '':
                addresses.append(data['city'])
            if 'country' in data and data['country'] != '':
                addresses.append(data['country'])
            trx.fintecture_iban_bank_address = ",".join(addresses)

    def _get_specific_processing_values(self, processing_values):
        """ Override of payment to return Fintecture-specific processing values.

        Note: self.ensure_one() from `_get_processing_values`

        :param dict processing_values: The generic processing values of the transaction
        :return: The dict of acquirer-specific processing values
        :rtype: dict
        """
        _logger.info('|PaymentTransaction| Retrieving specific processing values...')

        res = super()._get_specific_processing_values(processing_values)

        if self.provider != PAYMENT_ACQUIRER_NAME or self.operation != 'online_redirect':
            return res

        if self.fintecture_url and self.acquirer_reference:
            return {
                'app_id': fintecture_utils.get_pis_app_id(self.acquirer_id),
                'session_id': self.acquirer_reference,
                'url': self.fintecture_url
            }

        try:
            menu_id = self.env.ref('payment.payment_acquirer_menu').id  # TODO: fix
            action_id = self.env.ref('payment.action_payment_acquirer').id  # TODO: fix
            state = '{}/{}/{}/{}'.format(
                self.company_id.id,
                uuid.uuid4().hex,
                menu_id,
                action_id
            )
            req_pay_data = self._fintecture_create_request_pay(state)
            req_pay_data = req_pay_data['meta']
        except Exception as e:
            raise UserError('An error occur when trying to generate the payment link. '
                            'Try again and if error persist contact your administrator for support about this.')

        return {
            'app_id': fintecture_utils.get_pis_app_id(self.acquirer_id),
            'session_id': req_pay_data['session_id'],
            'url': req_pay_data['url'],
        }

    @api.model
    def _get_tx_from_feedback_data(self, provider, data):
        """ Override of payment to find the transaction based on Fintecture data.

        :param str provider: The provider of the acquirer that handled the transaction
        :param dict data: The feedback data sent by the provider
        :return: The transaction if found
        :rtype: recordset of `payment.transaction`
        :raise: ValidationError if inconsistent data were received
        :raise: ValidationError if the data match no transaction
        """
        _logger.info('|PaymentTransaction| Retrieving transaction from feedback data...')
        tx = super()._get_tx_from_feedback_data(provider, data)
        _logger.debug('|PaymentTransaction| tx: %r' % tx)

        if provider != PAYMENT_ACQUIRER_NAME:
            return tx

        ir_logging_model = self.env['ir.logging']
        payment_transaction_model = self.env['payment.transaction'].sudo().with_user(SUPERUSER_ID)

        session_id = data.get('session_id', False)
        _logger.debug('|PaymentTransaction| session_id: %s' % session_id)
        if not session_id:
            ir_logging_model.sudo().create({
                'name': 'fintecture.transaction.error',
                'type': 'server',
                'dbname': self.env.db,
                'level': 'DEBUG',
                'message': "Se ha enviado información sin el parámetro session_id\nInformación: {}".format(str(data)),
                'path': 'fintecture.model.payment_transaction._get_tx_from_feedback_data',
                'func': '_get_tx_from_feedback_data',
                'line': 188
            })
            raise ValidationError(
                "Fintecture: " + _("Received data has an invalid structure.")
            )

        found_trx = payment_transaction_model.search([
            ('provider', '=', PAYMENT_ACQUIRER_NAME),
            ('acquirer_reference', '=', session_id),
        ], limit=1)
        _logger.debug('|PaymentTransaction| found_trx: %r' % found_trx)
        if not found_trx:
            raise ValidationError(
                "Fintecture: " + _("No transaction found matching reference '%s.'", session_id)
            )
        return found_trx

    def _process_feedback_data(self, data):
        """ Override of payment to process the transaction based on Adyen data.

        Note: self.ensure_one()

        :param dict data: The feedback data build from information passed to the return route.
                          Depending on the operation of the transaction, the entries with the keys
                          'payment_intent', 'charge', 'setup_intent' and 'payment_method' can be
                          populated with their corresponding Fintecture API objects.
        :return: None
        :raise: ValidationError if inconsistent data were received
        """
        _logger.info('|PaymentTransaction| Processing transaction with received feedback data...')
        super()._process_feedback_data(data)
        if self.provider != PAYMENT_ACQUIRER_NAME:
            return
        received_amount = data.get('received_amount', False)
        # handle intent of transfer state and session status
        if self.operation == 'online_redirect':
            transfer_state = data.get('transfer_state', False)
            session_status = data.get('status', False)
            _logger.debug('|PaymentTransaction| transfer_state: {0}'.format(transfer_state))
            _logger.debug('|PaymentTransaction| session_status: {0}'.format(session_status))
        else:
            raise ValidationError(
                "Fintecture: " + _("Invalid transaction operation.")
            )

        if not transfer_state or not session_status:
            raise ValidationError(
                "Fintecture: " + _("Received data is missing transfer state or session status information.")
            )

        if transfer_state in INTENT_STATUS_MAPPING['draft']:
            pass
        elif transfer_state in INTENT_STATUS_MAPPING['pending'] or session_status in INTENT_STATUS_MAPPING['pending']:
            _logger.info('|PaymentTransaction| Setting current transaction (%r) as pending...' % self)
            self._set_pending()
        elif transfer_state in INTENT_STATUS_MAPPING['done'] and session_status in INTENT_STATUS_MAPPING['done']:
            _logger.info('|PaymentTransaction| Setting current transaction (%r) as done...' % self)
            if self.tokenize:
                self._fintecture_tokenize_from_feedback_data(data)
            if received_amount:
                self.write({
                    'amount': float(received_amount)
                })
            self._reconcile_after_done()
            self._set_done()
        elif transfer_state in INTENT_STATUS_MAPPING['cancel'] or session_status in INTENT_STATUS_MAPPING['cancel']:
            _logger.info('|PaymentTransaction| Canceling current transaction (%r)...' % self)
            self._set_canceled()
        else:  # classify unknown intent statuses as `error` tx state
            _logger.info('|PaymentTransaction| Setting current transaction (%r) with error...' % self)
            _logger.warning("received data with invalid intent status: %s", transfer_state)
            self._set_error(
                "Fintecture: " + _("Received data with invalid intent state or status: %s", transfer_state)
            )

    def _fintecture_create_request_pay(self, state=None):
        _logger.info('|PaymentTransaction| Creating the URL for request to pay...')

        _logger.debug('|PaymentTransaction| _fintecture_create_request_pay(): state: {}'
                      .format(state))

        # look for connect invoice to this transaction
        am = self.env['account.move'].search([('transaction_ids', 'in', self.id)], limit=1)
        _logger.debug("|PaymentTransaction| _get_specific_processing_values(): am: %s", pprint.pformat(am))

        invoice_due_date = None
        invoice_expire_date = None
        if am:
            invoice_due_date = int((am.invoice_date_due - date.today()).total_seconds())
            invoice_expire_date = int(invoice_due_date + 86400)  # one day more

        _logger.debug('|PaymentTransaction| _fintecture_create_request_pay(): invoice_due_date: {}'
                      .format(invoice_due_date))
        _logger.debug('|PaymentTransaction| _fintecture_create_request_pay(): invoice_expire_date: {}'
                      .format(invoice_expire_date))

        try:
            lang = self.partner_lang.iso_code
        except:
            try:
                lang = str(self.partner_lang).split('_')[0]
            except:
                lang = ''

        pay_data = self.acquirer_id.fintecture_pis_create_request_to_pay(
            lang_code=lang,
            partner_id=self.partner_id,
            amount=fintecture_utils.to_minor_currency_units(self.amount, self.currency_id) / 100,
            currency_id=self.currency_id,
            reference=self.reference,
            state=state,
            due_date=invoice_due_date,
            expire_date=invoice_expire_date,
        )

        self.acquirer_reference = pay_data['meta']['session_id']
        self.fintecture_payment_intent = pay_data['meta']['session_id']
        self.fintecture_url = pay_data['meta']['url']
        if 'virtual_beneficiary' in pay_data:
            self.fintecture_virtual_beneficiary = json.dumps(pay_data['virtual_beneficiary'])
        return pay_data

    def fintecture_create_qr(self):
        self.ensure_one()
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=20,
            border=4,
        )
        qr.add_data(self.fintecture_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#000000", back_color="#FFFFFF")
        temp = BytesIO()
        img.save(temp, format="PNG")
        qr_img = base64.b64encode(temp.getvalue())
        return qr_img
