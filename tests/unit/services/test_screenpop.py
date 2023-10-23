import datetime

from ivr_gateway.models.contacts import Contact
from ivr_gateway.models.enums import Partner
from ivr_gateway.services.screenpop import ScreenPopService


class TestScreenPopServices:

    def test_screenpop_service(self):
        contact = Contact()
        screenpop_service = ScreenPopService()
        assert screenpop_service.get_url(contact, Partner.IVR) == "https://csp.amount.com/us"
        contact.customer_id = 'test'
        assert screenpop_service.get_url(contact, Partner.IVR) == "https://csp.amount.com/us/customers/test/customer_details"
        contact.secured = datetime.datetime.now()
        contact.secured_key = 'test_key'
        assert screenpop_service.get_url(contact, Partner.IVR) == \
               "https://csp.amount.com/us/customers/test/workflow/secure_call?key=test_key"

    def test_screenpop_service_for_partners(self, monkeypatch):
        contact = Contact()
        screenpop_service = ScreenPopService()
        monkeypatch.setenv("BBVA_SCREENPOP_BASE_URL", "https://csp.amount.com/bbva")
        monkeypatch.setenv("REGIONS_SCREENPOP_BASE_URL", "https://csp.amount.com/regions")
        monkeypatch.setenv("HSBC_SCREENPOP_BASE_URL", "https://csp.amount.com/hsbc")
        monkeypatch.setenv("PNC_SCREENPOP_BASE_URL", "https://csp.amount.com/pnc")
        assert screenpop_service.get_url(contact, Partner.PNC) == "https://csp.amount.com/pnc"
        assert screenpop_service.get_url(contact, Partner.REGIONS) == "https://csp.amount.com/regions"
        assert screenpop_service.get_url(contact, Partner.HSBC) == "https://csp.amount.com/hsbc"
        assert screenpop_service.get_url(contact, Partner.BBVA) == "https://csp.amount.com/bbva"
