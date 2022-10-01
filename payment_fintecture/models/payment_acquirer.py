import base64
import logging
import uuid

import requests
import fintecture

from werkzeug.urls import url_encode, url_join

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError, UserError

from odoo.addons.payment_fintecture import utils as fintecture_utils
from odoo.addons.payment_fintecture.const import API_VERSION, PROXY_URL, WEBHOOK_HANDLED_EVENTS, CALLBACK_URL, \
    WEBHOOK_URL, PAYMENT_ACQUIRER_NAME, CHECKOUT_URL

_logger = logging.getLogger(__name__)


class PaymentAcquirer(models.Model):
    _inherit = 'payment.acquirer'

    provider = fields.Selection(
        selection_add=[
            (PAYMENT_ACQUIRER_NAME, "Fintecture")
        ],
        ondelete={
            PAYMENT_ACQUIRER_NAME: 'set default'
        }
    )
    fintecture_ais_app_id = fields.Char(
        string="Application ID",
        help="The key solely used to identify application with Fintecture",
        copy=False
    )
    fintecture_ais_app_secret = fields.Char(
        string="Application Secret",
        groups='base.group_system',
        copy=False
    )
    fintecture_ais_private_key_file = fields.Binary(
        string="Private Key File",
        help="The private key content is saved in an external file recovered from your Fintecture developer account. "
             "This signing secret must be set to authenticate the messages sent from Fintecture to Odoo.",
        groups='base.group_system',
        copy=False
    )
    fintecture_ais_private_key_filename = fields.Char(
        string="Filename of Private Key file",
        copy=False
    )
    fintecture_pis_app_id = fields.Char(
        string="Application ID",
        help="The key solely used to identify application with Fintecture",
        copy=False,
        required_if_provider=PAYMENT_ACQUIRER_NAME
    )
    fintecture_pis_app_secret = fields.Char(
        string="Application Secret",
        required_if_provider=PAYMENT_ACQUIRER_NAME,
        copy=False,
        groups='base.group_system'
    )
    fintecture_pis_private_key_file = fields.Binary(
        string="Private Key File",
        required_if_provider=PAYMENT_ACQUIRER_NAME,
        copy=False,
        help="The private key content is saved in an external file recovered from your Fintecture developer account. "
             "This signing secret must be set to authenticate the messages sent from Fintecture to Odoo.",
        groups='base.group_system'
    )
    fintecture_pis_private_key_filename = fields.Char(
        copy=False,
        string="Filename of Private Key file"
    )

    fintecture_ais_connection_id = fields.Char(
        string="Connection identifier",
        copy=False,
        groups='base.group_system'
    )
    fintecture_ais_customer_id = fields.Char(
        string="Customer ID",
        copy=False,
        groups='base.group_system'
    )
    fintecture_ais_provider = fields.Char(
        string="Provider Bank",
        copy=False,
        groups='base.group_system'
    )
    fintecture_ais_code = fields.Char(
        string="Fintecture Code for AIS Authentication",
        copy=False,
        help="The code value has a limit period of time, then it will expires. "
             "Its only used for oAuth in Fintecture AIS Application",
        groups='base.group_system'
    )
    fintecture_ais_access_token = fields.Char(
        string="Fintecture AIS Access Token",
        copy=False,
        groups='base.group_system'
    )
    fintecture_ais_refresh_token = fields.Char(
        string="Fintecture AIS Refresh Token",
        copy=False,
        groups='base.group_system'
    )
    fintecture_sale_viban = fields.Boolean(
        string="Include virtual IBAN in quotes",
        default=True
    )
    fintecture_invoice_viban = fields.Boolean(
        string="Include virtual IBAN in invoices",
        default=True
    )
    fintecture_sale_link_qr = fields.Boolean(
        string="Include link/QR in quotes",
        default=False
    )
    fintecture_invoice_link_qr = fields.Boolean(
        string="Include link/QR in invoices",
        default=False
    )
    fintecture_viban_unique_key = fields.Selection(
        string="Unique key for virtual IBAN",
        selection=[
            ('invoice', 'Invoice'),
            ('project', 'Project'),
            ('journal', 'Journal'),
            ('customer', 'Customer'),
        ],
        default='customer',
        required=True
    )

    @api.depends('provider')
    def _compute_view_configuration_fields(self):
        """
        This method extends the native method in Odoo to add configuration about fintecture acquirer to say Odoo which
        fields we want to show/hide
        :return:
        """
        super()._compute_view_configuration_fields()
        self.filtered(lambda acq: acq.provider == 'fintecture').write({
            'show_payment_icon_ids': False,
            'show_pre_msg': False,
            'show_done_msg': False,
            'show_cancel_msg': False,
        })

    def _get_feature_support(self):
        """Get advanced feature support by provider.

        Each provider should add its technical in the corresponding
        key for the following features:
            * tokenize: support saving payment data in a payment.tokenize
                        object
        """
        res = super(PaymentAcquirer, self)._get_feature_support()
        return res

    # === CONSTRAINT METHODS ===#

    @api.constrains('state', 'fintecture_ais_app_id', 'fintecture_app_secret')
    def _check_state_of_connected_account_is_never_test(self):
        """ Check that the acquirer of a connected account can never been set to 'test'.

        This constraint is defined in the present module to allow the export of the translation
        string of the `ValidationError` should it be raised by modules that would fully implement
        Fintecture Connect.

        Additionally, the field `state` is used as a trigger for this constraint to allow those
        modules to indirectly trigger it when writing on custom fields. Indeed, by always writing on
        `state` together with writing on those custom fields, the constraint would be triggered.

        :return: None
        """
        for acquirer in self:
            if acquirer.state == 'test' and acquirer._fintecture_has_connected_account():
                raise ValidationError(_(
                    "You cannot set the acquirer to Test Mode while it is linked with your Fintecture "
                    "account."
                ))

    def _fintecture_has_connected_account(self):
        """ Return whether the acquirer is linked to a connected Fintecture account.

        Note: This method serves as a hook for modules that would fully implement Fintecture Connect.
        Note: self.ensure_one()

        :return: Whether the acquirer is linked to a connected Fintecture account
        :rtype: bool
        """
        self.ensure_one()
        return False

    @api.constrains('fintecture_viban_unique_key')
    def _check_can_use_unique_key(self):
        """
        This constraint checks when user choose a unique_key if this key may be used. If not alert user and gives a link
        to install specific module.
        :return: Void
        """
        for acquirer in self:
            if acquirer.fintecture_viban_unique_key == 'project' and 'project.project' not in self.env:
                base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                url = "{}/web#id={}&model=ir.module.module&view_type=form".format(
                    base_url, str(self.env.ref('base.module_project').id)
                )
                raise ValidationError(_(
                    "You cannot set project as unique key because you need install the project module. <a href='{}'>Install</a>".format(
                        url
                    )
                ))

    # === ACTION METHODS === #

    def action_fintecture_ais_connect(self, menu_id=None):
        """ Create a Fintecture Connect account and redirect the user to the next onboarding step.

        If the acquirer is already enabled, close the current window. Otherwise, generate a Fintecture
        Connect onboarding link and redirect the user to it. If provided, the menu id is included in
        the URL the user is redirected to when coming back on Odoo after the onboarding. If the link
        generation failed, redirect the user to the acquirer form.

        Note: This method serves as a hook for modules that would fully implement Fintecture Connect.
        Note: self.ensure_one()

        :param int menu_id: The menu from which the user started the onboarding step, as an
                            `ir.ui.menu` id.
        :return: The next step action
        :rtype: dict
        """
        _logger.info('|PaymentAcquirer| Prepare for connect with Fintecture AIS Application...')

        self.ensure_one()

        _logger.debug('|PaymentAcquirer| self.company_id: {0}'.format(self.company_id))

        if self.state == 'enabled':
            self.company_id._mark_payment_onboarding_step_as_done()
            action = {'type': 'ir.actions.act_window_close'}
        else:
            # Account creation
            # connected_account = self._fintecture_fetch_or_create_connected_account()

            action = {
                'type': 'ir.actions.act_window',
                'model': 'payment.acquirer',
                'views': [[False, 'form']],
                'res_id': self.id,
            }

            base_url = self.get_base_url()
            redirect_uri = f'{url_join(base_url, CALLBACK_URL)}'
            menu_id = menu_id or self.env.ref('payment.payment_acquirer_menu').id
            action_id = self.env.ref('payment.action_payment_acquirer').id
            state = 'ais_connect,{},{},{}'.format(uuid.uuid4().hex, menu_id, action_id)

            _logger.debug('|PaymentAcquirer| base_url: {0}'.format(base_url))
            _logger.debug('|PaymentAcquirer| redirect_uri: {0}'.format(redirect_uri))
            _logger.debug('|PaymentAcquirer| menu_id: {0}'.format(menu_id))
            _logger.debug('|PaymentAcquirer| action_id: {0}'.format(action_id))
            _logger.debug('|PaymentAcquirer| state: {0}'.format(state))

            self._prepare_fintecture_environment(app_type='ais')

            connect_response = fintecture.AIS.connect(
                app_id=self.fintecture_ais_app_id,
                redirect_uri=redirect_uri,
                state=state
            )
            _logger.debug('|PaymentAcquirer| connect_response: %r\n' % connect_response)

            link_url = connect_response['meta']['url']
            connect_id = connect_response['meta']['connect_id']

            _logger.debug('|PaymentAcquirer| link_url: {0}'.format(link_url))
            _logger.debug('|PaymentAcquirer| connect_id: {0}'.format(connect_id))

            self.write({
                'fintecture_ais_connection_id': connect_id,
                'fintecture_ais_code': state,
            })

            # Link generation
            # account_link_url = self._fintecture_create_account_link(connected_account['id'], menu_id)
            # if account_link_url:
            if link_url:
                action = {
                    'type': 'ir.actions.act_url',
                    # 'url': account_link_url,
                    'url': link_url,
                    'target': 'self',
                }

        return action

    def action_reset_fintecture_connect_data(self):
        _logger.info('|PaymentAcquirer| Resetting data related of Fintecture connect of AIS Application...')

        self.ensure_one()

        self.write({
            'fintecture_ais_connection_id': False,
            'fintecture_ais_customer_id': False,
            'fintecture_ais_provider': False,
            'fintecture_ais_code': False,
            'fintecture_ais_access_token': False,
            'fintecture_ais_refresh_token': False,
        })

    def callback_ais_oauth(self, customer_id, code, provider):
        _logger.info('|PaymentAcquirer| Doing a oAuth authentication with received code from callback redirection...')
        _logger.debug('|PaymentAcquirer| callback_ais_oauth(): customer_id: {0}'.format(customer_id))
        _logger.debug('|PaymentAcquirer| callback_ais_oauth(): code: {0}'.format(code))
        _logger.debug('|PaymentAcquirer| callback_ais_oauth(): provider: {0}'.format(provider))

        self.write({
            'fintecture_ais_customer_id': customer_id,
            'fintecture_ais_code': code,  # replaces connection identifier previous used
            'fintecture_ais_provider': provider,
        })

        try:
            self._prepare_fintecture_environment(app_type='ais')

            oauth_response = fintecture.AIS.oauth(code=code)

            access_token = oauth_response['access_token']
            refresh_token = oauth_response['refresh_token']
            expires_in = oauth_response['expires_in']

            _logger.debug('|PaymentAcquirer| callback_ais_oauth(): access_token: {0}'.format(access_token))
            _logger.debug('|PaymentAcquirer| callback_ais_oauth(): refresh_token: {0}'.format(refresh_token))
            _logger.debug('|PaymentAcquirer| callback_ais_oauth(): expires_in: {0}'.format(expires_in))

            self.write({
                'fintecture_ais_access_token': access_token,
                'fintecture_ais_refresh_token': refresh_token,
            })

        except Exception as e:
            _logger.error('|PaymentAcquirer| An error occur when trying to authentication Fintecture AIS app by oAuth.')
            _logger.error('|PaymentAcquirer| ERROR: %r\n' % e)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'payment.acquirer',
            'views': [[False, 'form']],
            'res_id': self.id,
            'view_type': 'form',
            'view_mode': 'form',
        }

    def fintecture_pis_create_request_to_pay(self, lang_code, partner_id, amount, currency_id, reference, state,
                                             due_date=None, expire_date=None):
        _logger.info('|PaymentAcquirer| Creating the URL for request to pay...')

        self._authenticate_in_pis()

        if due_date is not None and expire_date is not None and due_date >= expire_date:
            raise ValueError('Due date parameter must be lower than expiry date parameter')

        # add or subtract two more hours for expire date
        if due_date is None:
            if expire_date is not None:
                due_date = expire_date - 7200
            else:
                due_date = 86400

        if expire_date is None:
            if due_date is not None:
                expire_date = due_date + 7200
            else:
                expire_date = 93600

        base_url = self.get_base_url()
        redirect_url = f'{url_join(base_url, CALLBACK_URL)}'
        unique_key = self.env.context.get('unique_key', False)
        if not unique_key:
            unique_key = "customer.{}".format(str(partner_id.id))
        meta = {
            'psu_name': partner_id.name,
            'psu_email': "{}.{}@odoo.fintecture.com".format(
                unique_key,
                str(self.fintecture_pis_app_id)
            ),
            'due_date': due_date,
            'expire': expire_date,
            "reconciliation": {
                "level": "payer",
                "match_amount": True
            }
        }
        if partner_id.email:
            meta['cc'] = partner_id.email
        if partner_id.mobile:
            meta['psu_phone'] = partner_id.mobile
        if partner_id.country_id:
            meta['psu_address'] = {
                'country': partner_id.country_id.code
            }
            if partner_id.street:
                meta['psu_address']['street'] = partner_id.street
            if partner_id.zip:
                meta['psu_address']['zip'] = partner_id.zip
            if partner_id.city:
                meta['psu_address']['city'] = partner_id.city

        data = {
            'type': 'connect',
            'attributes': {
                'amount': str(amount),
                'currency': str(currency_id.name).upper(),
                'communication': "Reference {}".format(reference)
            }
        }

        _logger.debug('|PaymentAcquirer| used redirect_uri: {0}'.format(redirect_url))
        _logger.debug('|PaymentAcquirer| used state: {0}'.format(state))
        _logger.debug('|PaymentAcquirer| used language: {0}'.format(lang_code))
        _logger.debug('|PaymentAcquirer| used meta: {0}'.format(meta))
        _logger.debug('|PaymentAcquirer| used data: {0}'.format(data))

        pay_response = fintecture.PIS.connect(
            redirect_uri=redirect_url,
            state=state,
            with_virtualbeneficiary=True,
            meta=meta,
            data=data,
            language=lang_code,
        )
        _logger.debug('|PaymentAcquirer| received request to pay result: {0}'.format(pay_response))

        return pay_response

    def fintecture_webhook_signature(self, payload, digest, signature, request_id):
        _logger.info('|PaymentAcquirer| Retrieve webhook content and validate signature...')

        # TODO: take into account when decide to validate AIS webhook
        #  for now we only validate PIS webhooks; refactorize behaviour
        self._prepare_fintecture_environment(app_type='pis')

        if not fintecture.private_key:
            _logger.error("|PaymentAcquirer| ignored webhook validation due to undefined private key")
            return False

        try:
            event = fintecture.Webhook.construct_event(
                payload, digest, signature, request_id
            )
        except ValueError as e:
            _logger.error("|PaymentAcquirer| Error while decoding event. Bad payload!")
            _logger.error("|PaymentAcquirer| ERROR: %r\n" % e)
            return False
        except fintecture.error.SignatureVerificationError as e:
            _logger.error("|PaymentAcquirer| Invalid signature!")
            _logger.error("|PaymentAcquirer| ERROR: %r\n" % e)
            return False

        return event

    def get_fintecture_acquirer(self):
        return self.env[self._name].sudo().search([
            ('provider', '=', PAYMENT_ACQUIRER_NAME),
            ('company_id', '=', self.env.company.id)
        ], limit=1)

    def _get_fintecture_webhook_url(self):
        return url_join(self.get_base_url(), WEBHOOK_URL)

    # === BUSINESS METHODS - PAYMENT FLOW === #

    def _fintecture_make_request(self, endpoint, payload=None, method='POST', offline=False):
        """ Make a request to Fintecture API at the specified endpoint.

        Note: self.ensure_one()

        :param str endpoint: The endpoint to be reached by the request
        :param dict payload: The payload of the request
        :param str method: The HTTP method of the request
        :param bool offline: Whether the operation of the transaction being processed is 'offline'
        :return The JSON-formatted content of the response
        :rtype: dict
        :raise: ValidationError if an HTTP error occurs
        """
        self.ensure_one()

        url = url_join('https://api.fintecture.com/v2/', endpoint)
        headers = {
            'AUTHORIZATION': f'Bearer {fintecture_utils.get_pis_app_secret(self)}',
            'Fintecture-Version': API_VERSION,  # SetupIntent requires a specific version.
            **self._get_fintecture_extra_request_headers(),
        }
        try:
            response = requests.request(method, url, data=payload, headers=headers, timeout=60)
            # Fintecture can send 4XX errors for payment failures (not only for badly-formed requests).
            # Check if an error code is present in the response content and raise only if not.
            # See https://fintecture.com/docs/error-codes.
            # If the request originates from an offline operation, don't raise and return the resp.
            if not response.ok \
                    and not offline \
                    and 400 <= response.status_code < 500 \
                    and response.json().get('error'):  # The 'code' entry is sometimes missing
                try:
                    response.raise_for_status()
                except requests.exceptions.HTTPError:
                    _logger.exception("invalid API request at %s with data %s", url, payload)
                    error_msg = response.json().get('error', {}).get('message', '')
                    raise ValidationError(
                        "Fintecture: " + _(
                            "The communication with the API failed.\n"
                            "Fintecture gave us the following info about the problem:\n'%s'", error_msg
                        )
                    )
        except requests.exceptions.ConnectionError:
            _logger.exception("unable to reach endpoint at %s", url)
            raise ValidationError("Fintecture: " + _("Could not establish the connection to the API."))
        return response.json()

    def _get_fintecture_extra_request_headers(self):
        """ Return the extra headers for the Fintecture API request.

        Note: This method serves as a hook for modules that would fully implement Fintecture Connect.

        :return: The extra request headers.
        :rtype: dict
        """
        return {}

    def _get_default_payment_method_id(self):
        self.ensure_one()
        if self.provider != PAYMENT_ACQUIRER_NAME:
            return super()._get_default_payment_method_id()
        return self.env.ref('payment_fintecture.payment_method_fintecture').id

    # === BUSINESS METHODS - FINTECTURE CONNECT ONBOARDING === #

    def _fintecture_fetch_or_create_connected_account(self):
        """ Fetch the connected Fintecture account and create one if not already done.

        Note: This method serves as a hook for modules that would fully implement Fintecture Connect.

        :return: The connected account
        :rtype: dict
        """

        return {}

    def _prepare_fintecture_environment(self, app_type='pis'):
        _logger.info('|PaymentAcquirer| Preparing Fintecture environment...')

        if self.state == 'test':
            fintecture.env = fintecture.environments.ENVIRONMENT_SANDBOX
        elif self.state == 'enabled':
            fintecture.env = fintecture.environments.ENVIRONMENT_PRODUCTION
        else:
            fintecture.env = fintecture.environments.ENVIRONMENT_TEST

        if app_type == 'ais':
            fintecture.app_id = self.fintecture_ais_app_id
            fintecture.app_secret = self.fintecture_ais_app_secret
            if self.fintecture_ais_private_key_file and len(self.fintecture_ais_private_key_file) > 0:
                fintecture.private_key = base64.b64decode(self.fintecture_ais_private_key_file).decode('utf-8')
        elif app_type == 'pis':
            fintecture.app_id = self.fintecture_pis_app_id
            fintecture.app_secret = self.fintecture_pis_app_secret
            if self.fintecture_pis_private_key_file and len(self.fintecture_pis_private_key_file) > 0:
                try:
                    fintecture.private_key = base64.b64decode(self.fintecture_pis_private_key_file).decode('utf-8')
                except Exception as e:
                    _logger.error('|PaymentAcquirer| Revisar el certificado porque hay algo mal')
        else:
            raise ValueError('Invalid Fintecture application type for setup environment keys...')

    def _authenticate_in_pis(self):
        _logger.info('|PaymentAcquirer| Authenticating with Fintecture PIS application...')

        self._prepare_fintecture_environment(app_type='pis')

        try:
            oauth_response = fintecture.PIS.oauth()

            access_token = oauth_response['access_token']
            expires_in = oauth_response['expires_in']

            _logger.debug('|PaymentAcquirer| _retrieve_pis_access_token(): access_token: {0}'.format(access_token))
            _logger.debug('|PaymentAcquirer| _retrieve_pis_access_token(): expires_in: {0}'.format(expires_in))

            fintecture.access_token = access_token

        except Exception as e:
            _logger.error('|PaymentAcquirer| An error occur when trying to authenticate through oAuth...')
            _logger.error('|PaymentAcquirer| ERROR {0}'.format(str(e)))
            raise UserError(_('Invalid authentication. Check your credential in payment acquirer configuration page.'))

    def fintecture_get_form_action_url(self):
        return CHECKOUT_URL
