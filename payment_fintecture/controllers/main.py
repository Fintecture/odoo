import hashlib
import hmac
import json
import logging
import pprint
import collections

from datetime import datetime

from odoo import http, SUPERUSER_ID
from odoo.exceptions import ValidationError
from odoo.http import request
from odoo.tools import consteq

from odoo.addons.payment_fintecture import utils as fintecture_utils
from odoo.addons.payment_fintecture.const import CALLBACK_URL, WEBHOOK_URL, CHECKOUT_URL, VALIDATION_URL, \
    WEBHOOK_AGE_TOLERANCE, PAYMENT_ACQUIRER_NAME

_logger = logging.getLogger(__name__)


class FintectureController(http.Controller):

    # TODO: remove me!
    @http.route(CHECKOUT_URL, type='http', auth='public', csrf=False)
    def fintecture_return_from_checkout(self, **data):
        """ Process the data returned by Fintecture after redirection for checkout.

        :param dict data: The GET params appended to the URL in `_fintecture_create_checkout_session`
        """
        # Retrieve the tx and acquirer based on the tx reference included in the return url
        tx_sudo = request.env['payment.transaction'].sudo()._get_tx_from_feedback_data(
            PAYMENT_ACQUIRER_NAME, data
        )
        acquirer_sudo = tx_sudo.acquirer_id

        # Fetch the PaymentIntent, Charge and PaymentMethod objects from Fintecture
        payment_intent = acquirer_sudo._fintecture_make_request(
            f'payment_intents/{tx_sudo.fintecture_payment_intent}', method='GET'
        )
        _logger.info("received payment_intents response:\n%s", pprint.pformat(payment_intent))
        self._include_payment_intent_in_feedback_data(payment_intent, data)

        # Handle the feedback data crafted with Fintecture API objects
        request.env['payment.transaction'].sudo()._handle_feedback_data(PAYMENT_ACQUIRER_NAME, data)

        # Redirect the user to the status page
        return request.redirect('/payment/status')

    # TODO: remove me!
    @http.route(VALIDATION_URL, type='http', auth='public', csrf=False)
    def fintecture_return_from_validation(self, **data):
        """ Process the data returned by Fintecture after redirection for validation.

        :param dict data: The GET params appended to the URL in `_fintecture_create_checkout_session`
        """
        # Retrieve the acquirer based on the tx reference included in the return url
        acquirer_sudo = request.env['payment.transaction'].sudo()._get_tx_from_feedback_data(
            PAYMENT_ACQUIRER_NAME, data
        ).acquirer_id

        # Fetch the Session, SetupIntent and PaymentMethod objects from Fintecture
        checkout_session = acquirer_sudo._fintecture_make_request(
            f'checkout/sessions/{data.get("checkout_session_id")}',
            payload={'expand[]': 'setup_intent.payment_method'},  # Expand all required objects
            method='GET'
        )
        _logger.info("received checkout/session response:\n%s", pprint.pformat(checkout_session))
        self._include_setup_intent_in_feedback_data(checkout_session.get('setup_intent', {}), data)

        # Handle the feedback data crafted with Fintecture API objects
        request.env['payment.transaction'].sudo()._handle_feedback_data(PAYMENT_ACQUIRER_NAME, data)

        # Redirect the user to the status page
        return request.redirect('/payment/status')

    @http.route(route=CALLBACK_URL, type='http', auth='public', methods=['GET'])
    def fintecture_callback(self, **kwargs):
        """ Process the redirection event sent by Fintecture to the webhook.

        :return: An empty string to acknowledge the notification with an HTTP 200 response
        :rtype: str
        """
        _logger.info('|FintectureController| Received a callback and now it will be processed...')
        query_params = collections.OrderedDict(request.httprequest.args)
        _logger.debug('|FintectureController| full query_params: ({})...'.format(query_params))

        status = kwargs.get('status', False)
        session_id = query_params.get('session_id', False)

        state = kwargs.get('state', '')
        if not isinstance(state, str):
            _logger.warning('|FintectureController| Callback handler receives an invalid state ({})...'.format(state))
            return ''

        rs = self._parse_state_param(state)
        if rs is False:
            return ''

        acquirer_model = request.env['payment.acquirer'].sudo().with_user(SUPERUSER_ID)
        transaction_model = request.env['payment.transaction'].sudo().with_user(SUPERUSER_ID)
        payment_model = request.env['account.payment'].sudo().with_user(SUPERUSER_ID)
        payment_method_model = request.env['account.payment.method'].sudo().with_user(SUPERUSER_ID)

        if rs['operation'] == 'ais_connect':
            customer_id = kwargs.get('customer_id')
            code = kwargs.get('code')
            provider = kwargs.get('provider')

            _logger.debug('|FintectureController| Callback handler receives customer_id: ({})...'.format(customer_id))
            _logger.debug('|FintectureController| Callback handler receives code: ({})...'.format(code))
            _logger.debug('|FintectureController| Callback handler receives provider: ({})...'.format(provider))

            fintecture_acquirer = acquirer_model.search([
                ('provider', '=', PAYMENT_ACQUIRER_NAME),
                ('fintecture_ais_code', '=', state)
            ], limit=1)
            if fintecture_acquirer:
                fintecture_acquirer.callback_ais_oauth(customer_id, code, provider)

                action = {
                    'type': 'ir.actions.act_url',
                    'res_model': 'payment.acquirer',
                    'views': [[False, 'form']],
                    'res_id': fintecture_acquirer.id,
                    'view_type': 'kanban',
                    'view_mode': 'kanban,tree',
                    'target': 'self',
                }
                # return action

                _logger.debug('|FintectureController| fintecture_acquirer: ({})...'.format(fintecture_acquirer))
                redirect_uri = '/web#id={}&menu_id={}&action={}&view_type=form&model=payment.acquirer' \
                    .format(fintecture_acquirer.id, rs['menu_id'], rs['action_id'])
                _logger.debug('|FintectureController| redirect_url: ({})...'.format(redirect_uri))

                return request.redirect(redirect_uri)

        elif rs['operation'] == 'payment':

            fintecture_payment_method = payment_method_model.search([
                ('code', '=', PAYMENT_ACQUIRER_NAME),
            ], limit=1)
            _logger.debug('|FintectureController| fintecture_payment_method: ({})...'.format(fintecture_payment_method))
            if not fintecture_payment_method:
                raise UserWarning('Fintecture is not installed as an account payment method!!')

            account_payment = payment_model.search([
                ('payment_method_id', '=', fintecture_payment_method.id),
                ('payment_reference', '=', session_id),
            ], limit=1)
            _logger.debug('|FintectureController| account_payment: ({})...'.format(account_payment))

            redirect_uri = '/web#id={}'.format(account_payment.id)
            if rs['menu_id']:
                redirect_uri += '&menu_id={}'.format(rs['menu_id'])
            if rs['action_id']:
                redirect_uri += '&action={}'.format(rs['action_id'])
            redirect_uri += '&view_type=form&model=account.payment'

            _logger.debug('|FintectureController| redirect_url: ({})...'.format(redirect_uri))

            # do not notify about a payment status, created successfully or other??

            return request.redirect(redirect_uri)

        elif rs['operation'] == 'invoice':

            fintecture_acquirer = acquirer_model.search([
                ('provider', '=', PAYMENT_ACQUIRER_NAME),
            ], limit=1)
            if not fintecture_acquirer:
                _logger.warning('|FintectureController| Fintecture does not exists as any payment acquirer...')
                return ''
            _logger.debug('|FintectureController| fintecture_callback(): fintecture_acquirer: {}'
                          .format(fintecture_acquirer))

            tx = transaction_model.search([
                ('acquirer_id', '=', fintecture_acquirer.id),
                ('acquirer_reference', '=', session_id),
            ], limit=1)
            if not tx:
                _logger.warning('|FintectureController| Callback handler receives a session_id={} '
                                'with not registered transaction'.format(session_id))
                return ''
            _logger.debug('|FintectureController| fintecture_callback(): tx: {}'.format(tx))

            # TODO: fix
            # redirect_uri = '/web#id={}'.format(tx.id)
            # if rs['menu_id']:
            #     redirect_uri += '&menu_id={}'.format(rs['menu_id'])
            # if rs['action_id']:
            #     redirect_uri += '&action={}'.format(rs['action_id'])
            # redirect_uri += '&view_type=form&model=account.move'

            # _logger.debug('|FintectureController| redirect_url: ({})...'.format(redirect_uri))

            landing_route = tx.landing_route
            _logger.debug('|FintectureController| fintecture_callback(): landing_route: {}'.format(landing_route))

            return request.redirect(landing_route)

        elif status == 'payment_created' and session_id:
            values = {
                'status': status,
                'session_id': session_id,
            }
            # return request.render("payment_fintecture.success_payment", values)
            return 'Payment Successfully. Here should appears a thank you page for the processed payment.'

        else:
            _logger.error(
                '|FintectureController| Callback handler receives an unknown state ({0}) operation ({1}) for process...'
                    .format(state, rs['operation'])
            )

        return request.redirect('/web')

    @http.route(WEBHOOK_URL, methods=['POST'], type='http', auth='public', csrf=False)
    def fintecture_webhook(self, **kwargs):
        """ Process all events sent by Fintecture to the webhook.

        :return: An empty string to acknowledge the notification with an HTTP 200 response
        :rtype: str
        """
        _logger.info('|FintectureController| Received a webhook request and now it will be processed...')

        form_data = collections.OrderedDict(request.httprequest.form)
        _logger.debug("|FintectureController| received form data: \n%s", pprint.pformat(form_data))

        try:
            state = kwargs.get('state', '')
            if not isinstance(state, str):
                _logger.warning(
                    '|FintectureController| Webhook handler receives an invalid state ({})...'.format(state))
                return ''

            rs = self._parse_state_param(state)
            if rs is False:
                return ''

            event = self._verify_webhook_signature(form_data)
            if event is not False:
                if event['status'] in ['payment_created', 'payment_partial'] and event['transfer_state'] in [
                    'completed', 'received', 'insufficient']:
                    request.env['payment.transaction'].sudo()._handle_feedback_data(PAYMENT_ACQUIRER_NAME, form_data)
                else:
                    _logger.info("|FintectureController| Received webhook of payment with session={0}) has the "
                                 " status='{1}' and transfer_state={2}".format(
                        event.get('session_id'),
                        event.get('status'),
                        event.get('transfer_state')
                    ))
            else:
                _logger.error("|FintectureController| Invalid received webhook content. Canceling processing...")
        except Exception as e:
            _logger.error("""
                |FintectureController| An error occur when manage feedback data 
                received from webhook notification...
            """)
            _logger.error('|FintectureController| ERROR: %s' % str(e))

        return ''

    @staticmethod
    def _parse_state_param(state):
        state_params = state.split('/')
        if not state_params or len(state_params) == 0:
            _logger.warning('|FintectureController| State param parser receives an invalid state ({})...'.format(state))
            return False

        _logger.debug('|FintectureController| _parse_state_param(): state: ({})...'.format(state))
        _logger.debug('|FintectureController| _parse_state_param(): state_params: ({})...'.format(state_params))

        company = state_params[0]
        connection_id = state_params[1] if len(state_params) > 1 else False
        menu_id = state_params[2] if len(state_params) > 2 else False
        action_id = state_params[3] if len(state_params) > 3 else False
        _logger.debug('|FintectureController| _parse_state_param():  connection_id: ({})...'.format(connection_id))
        _logger.debug('|FintectureController| _parse_state_param():  menu_id: ({})...'.format(menu_id))
        _logger.debug('|FintectureController| _parse_state_param():  action_id: ({})...'.format(action_id))

        # TODO: validate 'operation' variable

        return {
            'company': company,
            'connection_id': connection_id,
            'menu_id': menu_id,
            'action_id': action_id,
        }

    @staticmethod
    def _include_payment_intent_in_feedback_data(payment_intent, data):
        data.update({'payment_intent': payment_intent})
        if payment_intent.get('charges', {}).get('total_count', 0) > 0:
            charge = payment_intent['charges']['data'][0]  # Use the latest charge object
            data.update({
                'charge': charge,
                'payment_method': charge.get('payment_method_details'),
            })

    @staticmethod
    def _include_setup_intent_in_feedback_data(setup_intent, data):
        data.update({
            'setup_intent': setup_intent,
            'payment_method': setup_intent.get('payment_method')
        })

    @staticmethod
    def _verify_webhook_signature(form_data):
        _logger.info('|FintectureController| Verifying webhook signature...')

        tx_sudo = request.env['payment.transaction'].sudo()._get_tx_from_feedback_data(
            PAYMENT_ACQUIRER_NAME, form_data
        )

        if not tx_sudo:
            _logger.error("|FintectureController| Invalid received form data which is unrelated to a payment acquirer")
            return False

        payload = request.httprequest.form
        received_digest = request.httprequest.headers.get("Digest", None)
        received_signature = request.httprequest.headers.get("Signature", None)
        received_request_id = request.httprequest.headers.get("X-Request-ID", None)

        _logger.debug("|FintectureController| payload: {}".format(payload))
        _logger.debug("|FintectureController| received_digest: {}".format(received_digest))
        _logger.debug("|FintectureController| received_signature: {}".format(received_signature))
        _logger.debug("|FintectureController| received_request_id: {}".format(received_request_id))

        event = tx_sudo.acquirer_id.fintecture_webhook_signature(
            payload, received_digest, received_signature, received_request_id
        )

        _logger.debug("|FintectureController| validation result of webhook signature: {}".format(event))

        return event
