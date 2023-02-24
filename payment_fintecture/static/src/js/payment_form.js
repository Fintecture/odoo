/* global Fintecture */
odoo.define('payment_fintecture.payment_form', require => {
    'use strict';

    const checkoutForm = require('payment.checkout_form');
    const manageForm = require('payment.manage_form');

    const fintectureMixin = {

        /**
         * Redirect the customer to Fintecture hosted payment page.
         *
         * @override method from payment.payment_form_mixin
         * @private
         * @param {string} provider - The provider of the payment option's acquirer
         * @param {number} paymentOptionId - The id of the payment option handling the transaction
         * @param {object} processingValues - The processing values of the transaction
         * @return {undefined}
         */
        _processRedirectPayment: function (provider, paymentOptionId, processingValues) {
            console.log('|PaymentFintecture| (payment_form) provider: ', provider);
            console.log('|PaymentFintecture| (payment_form) paymentOptionId: ', paymentOptionId);
            console.log('|PaymentFintecture| (payment_form) processingValues: ', processingValues);
            console.log('|PaymentFintecture| (payment_form) processingValues: ', JSON.stringify(processingValues));
            console.log('|PaymentFintecture| (payment_form) arguments: ', JSON.stringify(arguments));

            if (provider !== 'fintecture') {
                return this._super(...arguments);
            }
            window.location = processingValues['url'];
        },

        /**
         * Prepare the options to init the Fintecture JS Object
         *
         * Function overriden in internal module
         *
         * @param {object} processingValues
         * @return {object}
         */
        _prepareFintectureOptions: function (processingValues) {
            return {};
        },
    };

    checkoutForm.include(fintectureMixin);
    manageForm.include(fintectureMixin);

});
