
from unittest.mock import patch

from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.payment_fintecture.controllers.onboarding import OnboardingController
from odoo.addons.payment_fintecture.const import WEBHOOK_HANDLED_EVENTS
from .common import FintectureCommon


@tagged('post_install', '-at_install')
class FintectureTest(FintectureCommon):

    def test_processing_values(self):
        dummy_session_id = 'cs_test_sbTG0yGwTszAqFUP8Ulecr1bUwEyQEo29M8taYvdP7UA6Qr37qX6uA6w'
        tx = self.create_transaction(flow='redirect') # We don't really care what the flow is here.

        # Ensure no external API call is done, we only want to check the processing values logic
        def mock_fintecture_create_checkout_session(self):
            return {'id': dummy_session_id}
        with patch.object(
            type(self.env['payment.transaction']),
            '_fintecture_create_checkout_session',
            mock_fintecture_create_checkout_session,
        ), mute_logger('odoo.addons.payment.models.payment_transaction'):
            processing_values = tx._get_fintecture_processing_values()

        self.assertEqual(processing_values['app_id'], self.fintecture.fintecture_app_id)
        self.assertEqual(processing_values['session_id'], dummy_session_id)

    def test_onboarding_action_redirect_to_url(self):
        """ Test that the action generate and return an URL when the acquirer is disabled. """
        with patch.object(
            type(self.env['payment.acquirer']), '_fintecture_fetch_or_create_connected_account',
            return_value={'id': 'dummy'},
        ), patch.object(
            type(self.env['payment.acquirer']), '_fintecture_create_account_link',
            return_value='https://dummy.url',
        ):
            onboarding_url = self.fintecture.action_fintecture_ais_connect()
        self.assertEqual(onboarding_url['url'], 'https://dummy.url')

    def test_create_account_link_pass_required_parameters(self):
        """ Test that the generation of an account link includes all the required parameters. """
        with patch.object(
            type(self.env['payment.acquirer']), '_fintecture_make_proxy_request',
            return_value={'url': 'https://dummy.url'},
        ) as mock:
            self.fintecture._fintecture_create_account_link('dummy', 'dummy')
            for payload_param in ('account', 'return_url', 'refresh_url', 'type'):
                self.assertIn(payload_param, mock.call_args.kwargs['payload'].keys())
