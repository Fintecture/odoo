# -*- coding: utf-8 -*-

{
    'name': 'Fintecture Payment Acquirer for Sale',
    'version': '1.0',
    'category': 'Sale/Payment Acquirers',
    'summary': 'Payment Acquirer: Fintecture Implementation',
    'description': """Fintecture Payment Acquirer for Sale""",
    'website': 'https://fintecture.com/',
    'author': 'Fintecture',
    'depends': [
        'payment_fintecture',
        'sale'
    ],
    'data': [
        'data/mail_template_data.xml',
        'views/sale_order_report.xml',
    ],
    'application': True,
    'assets': {
    },
    "qweb": [],
    "installable": True,
    'application': True,
    'license': 'LGPL-3',
}
