
from odoo.addons.payment.tests.common import PaymentCommon
from odoo.addons.payment_fintecture.const import PAYMENT_ACQUIRER_NAME


class FintectureCommon(PaymentCommon):

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)

        cls.fintecture = cls._prepare_acquirer(PAYMENT_ACQUIRER_NAME, update_values={
            'fintecture_app_id': '15fb9397-db7d-3a4e-dea2-7d7eb31793c3',
            'fintecture_app_secret': 'd7f6ef34-a6ee-f849-296e-f219a044463c',
            'fintecture_private_key': '''
-----BEGIN PRIVATE KEY-----
a4EFZoBLp8ID5AhV3LpXZQ3TJV2O9ST/vC3ZED8L3gKT1PN4ZIZ+xTIgk6P/aXP2
rOeebp4vv7lCkw5Rke5aG14ST0u16rNWk8gfNUSlTWamdwar1Ar62ICat7lOr0jG
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC/o98uGTAs+83d
LoeLs8zar1Nnm/YI56xCcDC3kvjuwn0Q+9McqjV5RcRM6JaaPC7NtHLTidtQ5L+w
H+wsRAaoSedu/yltLDh1FcRdvQKBgQDMmu0qxdkwVWQKFw1Y60gyNaOI5RnaGI3r
S6Mx5SLmNPAoow4Kjb04mt/kMoauUYKK53yyiz4UxXnmuLdg6SEGG1c+/TJRP6d3
aeqcicPCmUiHUWBRptGAbCbII5eEOw9j2XBCb3z5oiPKMjQwFa2Lry07xxTlFnBO
augmzmWtAgMBAAECggEACTdIk1SeGXuz3GuP6UbpOo3zddJ78iDyH8kzI+7w9Xr8
augmzmWtAgMBAAECggEACTdIk1SeGXuz3GuP6UbpOo3zddJ78iDyH8kzI+7w9Xr8
9uE9KCsNSw8cLE3gYeuyP3qhQforN4UnGyEDtQ5x2wbim1dLA1NjGV2AZbK6phZU
mivNifkbCby6eQDZAzrVBkxWFcpOgl5AN7WTH9JyETjfP5tOIK2A040bpVMJv57r
ZTzrzn/DCoec2TH1wWtBp2SWGU0MDwn39ubzEVIdrIkKjddJ423TTEtc/Hk3f75L
6VkIfLiQh8WAmY89j2I8D9SFgRf3U0Lqrv1rA6LmZpT+ET5ZKAfkbGEb2QKBgEO9
T7qTIky6ARmUVTRb4GK4JlI2TGwPDG8tUzjrLjs+rnpixoEJ/fVUokeL1xvRX4/k
7AEOWUBcA2mAwafD+uJSQc8nnZnvTzbHWxNZgZtDcpcRpMgo9R+jVW1902y3dT0e
smfzEuG3ELLta7QRItlEn7Cu0VqYLssL8Luiifjf6oVH69m7Tjbd9evQhdK3Oevz
RG/FQLpJODva377aQ0iNrQy/297wKSLnKyRluVqRJarS0Ru5CcB/+4aKHzKWEkZB
ovsSdunZ4GRQ1A6XcvFWdV55X+JhjrUYyNmvR96c9qtFepFbS/XJp0AnHn/gtJhS
E19/UgJOsQKBgQDPYXc8xNUY2954jjlpW3t4FRWJQlOyaBX/XHYh4uvF/HqDKHEB
kvS17mwAYZ2vHCBoF6EgkAC68WSlG0UcSmkZ3qUrZ7utHZq6xBcqhV+9ddsUCKi0
n3wj2Q6Zlu+IRlEERPjqrWQrhe2hZ4t2gG3SlQYfttbT/qjB04lufoLs7gSivO6h
Q10ZZ77m8v07IhZoF0sI0lwrYaDLLwTPnzSGMGFhAoGAOB4ZmUarL1gmefrNue9q
wQC5aMjLGlV8iReTBKNpDmJlRK1e3XfC1lmX1s5gaKWBQCau1oVlJ9vt1WO3E0q3
smfzEuG3ELLta7QRItlEn7Cu0VqYLssL8Luiifjf6oVH69m7Tjbd9evQhdK3Oevz
nwY+1E2M0KzPi+Tc/f72xeCsUbvIDjw+Q1VQI6kYOs5ykNBs1nn4J7M7IN0fR+gv
M/VgNW3Ghn47o21UJav6rcZ=
-----END PRIVATE KEY-----
            ''',
            'payment_icon_ids': [(5, 0, 0)],
        })

        cls.acquirer = cls.fintecture
