from collections import namedtuple

API_VERSION = '2022-09-10'  # The API version of Fintecture implemented in this module

PAYMENT_ACQUIRER_NAME = 'fintecture'

# Fintecture proxy URL. Is because in a future we want to offer Fintecture like a IAP service in Odoo.
PROXY_URL = 'https://fintecture.api.odoo.com/api/fintecture/'

PMT = namedtuple('PaymentMethodType', ['name', 'countries', 'currencies', 'recurrence'])
PAYMENT_METHOD_TYPES = [
    PMT('card', [], [], 'recurring'),
    PMT('ideal', ['nl'], ['eur'], 'punctual'),
    PMT('bancontact', ['be'], ['eur'], 'punctual'),
    PMT('eps', ['at'], ['eur'], 'punctual'),
    PMT('giropay', ['de'], ['eur'], 'punctual'),
    PMT('p24', ['pl'], ['eur', 'pln'], 'punctual'),
]
# Mapping of transaction states to Fintecture Payment state and status.
# See https://docs.fintecture.com/v2 for the exhaustive list of state and status.
INTENT_STATUS_MAPPING = {
    'draft': (
        # session status
        # transfer state
    ),
    'pending': (
        # session status
        'payment_pending',
        'sca_required',
        'provider_required',
        'payment_waiting',
        # transfer state
        'processing',
        'pending',
        'authorized',
        'accepted',
    ),
    'done': (
        # session status
        'payment_created',
        'payment_partial',
        'insufficient',
        # transfer state
        'completed',
        'received',
        'sent',
    ),
    'cancel': (
        # session status
        'payment_unsuccessful',
        # transfer state
        'rejected',
    ),
    'error': (
        # session status
        'payment_error',
        # transfer state
    )
}

# Events which are handled by the webhook
WEBHOOK_HANDLED_EVENTS = [
    'checkout.session.completed',
]

CALLBACK_URL = '/payment/fintecture/callback'
WEBHOOK_URL = '/payment/fintecture/webhook'

CHECKOUT_URL = '/payment/fintecture/checkout_return'
VALIDATION_URL = '/payment/fintecture/validation_return'

WEBHOOK_AGE_TOLERANCE = 10 * 60
