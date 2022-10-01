from . import controllers
from . import models

from odoo import api, SUPERUSER_ID

from odoo.addons.payment import reset_payment_provider
from odoo.addons.payment_fintecture.const import PAYMENT_ACQUIRER_NAME


def uninstall_hook(cr, registry):
    reset_payment_provider(cr, registry, PAYMENT_ACQUIRER_NAME)


def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    companies = env['res.company'].search([])
    companies.fintecture_create_acquirer()
