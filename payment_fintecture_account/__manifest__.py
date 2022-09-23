# -*- coding: utf-8 -*-

{
    'name': 'Fintecture Payment Acquirer for Invoice',
    'version': '1.0',
    'category': 'Sale/Payment Acquirers',
    'summary': 'Payment Acquirer: Fintecture Implementation',
    'description': """Fintecture Payment Acquirer for Sale""",
    'website': 'https://fintecture.com/',
    'author': 'Fintecture',
    'depends': [
        'payment_fintecture',
        'account',
        'account_payment',
    ],
    'data': [
        'data/mail_template_data.xml',
        'views/account_move_report.xml',
        'views/account_payment_views.xml',
    ],
    'application': True,
    'assets': {
    },
    "qweb": [],
    "installable": True,
    'application': True,
    'license': 'LGPL-3',
}
