import os

from ivr_gateway.models.contacts import Contact
from ivr_gateway.models.enums import Partner


class ScreenPopService:

    def base_url(self, partner: Partner = None) -> str:
        return os.getenv(str(partner.value).upper() +'_SCREENPOP_BASE_URL')

    def get_url(self, contact: Contact, partner: Partner) -> str:
        if contact.customer_id is None:
            return self.base_url(partner=partner)
        if contact.secured is not None:
            return self.get_secured_url(contact, partner=partner)
        return self.get_unsecured_url(contact, partner=partner)

    def get_unsecured_url(self, contact: Contact, partner: Partner) -> str:
        return f"{self.base_url(partner=partner)}/customers/{contact.customer_id}/customer_details"

    def get_secured_url(self, contact: Contact, partner: Partner) -> str:
        return f"{self.base_url(partner=partner)}/customers/{contact.customer_id}/workflow/secure_call?key={contact.secured_key}"
