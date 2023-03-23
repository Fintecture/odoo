import collections
import logging
import pprint

from odoo.addons.payment_fintecture.const import CALLBACK_URL, WEBHOOK_URL, PAYMENT_ACQUIRER_NAME

from odoo import http, SUPERUSER_ID
from odoo.http import request

_logger = logging.getLogger(__name__)


class FintectureController(http.Controller):

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
                redirect_uri = '/web#id={}&menu_id={}&action={}&view_type=form&model=payment.acquirer'.format(
                    fintecture_acquirer.id,
                    str(request.env.ref('payment.payment_acquirer_menu').id),
                    str(request.env.ref('payment.action_payment_acquirer').id),
                )
                return request.redirect(redirect_uri)
        elif status == 'payment_created' and session_id:
            logging.info(session_id)
            tx_ids = request.session.get("__payment_tx_ids__", [])
            logging.info(tx_ids)
            logging.info(rs)
            if rs['transaction'] and not tx_ids:
                request.session.__payment_tx_ids__ = [rs['transaction'].id]
            if rs['transaction'] and rs['transaction'].landing_route:
                return request.redirect(rs['transaction'].landing_route)
            return request.redirect('/payment/status')
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
        company = request.env['res.company'].sudo().with_user(SUPERUSER_ID).browse(int(state_params[0]))

        if len(state_params) > 1 and state_params[1] != '0':
            transaction = request.env['payment.transaction'].sudo().with_user(SUPERUSER_ID).browse(int(state_params[1]))
        else:
            transaction = False
        return {
            'company': company,
            'transaction': transaction,
            'operation': state_params[2] if len(state_params) > 2 else False
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
