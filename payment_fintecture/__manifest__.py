# -*- coding: utf-8 -*-

{
    'name': 'Payment acquiring & Automated reconciliation by Fintecture',
    'version': '1.0',
    'category': 'Accounting/Payment Acquirers',
    'summary': 'Payment Acquirer: Fintecture Implementation',
    'description': """Fintecture Payment Acquirer""",
    'website': 'https://fintecture.com/',
    'author': 'Fintecture',
    'depends': [
        'payment'
    ],
    'data': [
        'views/payment_views.xml',
        'data/payment_acquirer_data.xml',
    ],
    'application': True,
    'uninstall_hook': 'uninstall_hook',
    'post_init_hook': 'post_init_hook',
    'assets': {
        'web.assets_frontend': [
            'payment_fintecture/static/src/js/payment_form.js',
        ],
    },
    "qweb": [],
    "installable": True,
    'application': True,
    "images": [
        "static/description/main.png"
    ],
    "currency": "EUR",
    "price": 99.90,
    'license': 'LGPL-3',
}
