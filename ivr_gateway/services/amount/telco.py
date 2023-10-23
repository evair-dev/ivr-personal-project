import os

from ddtrace import tracer
from defusedxml import ElementTree as ET
from typing import Optional

import requests
from sqlalchemy import orm

from ivr_gateway.models.contacts import Contact
from ivr_gateway.services.amount import AmountService


class TelcoService(AmountService):

    def __init__(self, db_session: orm.Session, contact: Contact):
        super().__init__(db_session, contact=contact)
        self.telco_endpoint = f"{self.base_url}/{os.getenv('TELCO_API_PATH')}"

    def search_client_info(self, contact: Contact) -> Optional[str]:

        customer_number = self.get_customer_number(contact)
        url = f"{self.telco_endpoint}/search"
        if customer_number is None:
            contact.session["telco"] = {}
            self.db_session.add(contact)
            self.db_session.commit()
            return None

        telco_api_key = os.getenv('TELCO_API_KEY')
        data = {"telco_api_key": telco_api_key,
                "phone_number": customer_number}
        with tracer.trace('amount_service.api.telco.v1.search'):
            def request():
                return requests.post(url, headers=self.headers, data=data, timeout=self.timeout)
            exception_occurred, response = self._attempt_request(
                request=request,
                amount_endpoint=url,
                tag_name="amount_service.telco_search.status_code",
                exception_result="")
            if exception_occurred:
                return response
        xml_value = ET.fromstring(response.text)
        telco_dict = {}
        for child in xml_value:
            telco_dict[child.tag] = child.text
            if child.tag == "customer_id":
                contact.customer_id = child.text
        contact.session["telco"] = telco_dict
        self.db_session.add(contact)
        self.db_session.commit()
        return contact.customer_id

    def download_info_if_not_cached(self, call: Contact):
        if call.session.get("telco") is None:
            self.search_client_info(call)

    @staticmethod
    def get_customer_number(contact: Contact) -> Optional[str]:
        if len(contact.contact_legs) == 0:
            return None
        ani = contact.device_identifier
        if ani is None:
            return None
        if ani.startswith("1"):
            return ani[1:]
        return ani

    @staticmethod
    def field_lookup(contact: Contact, field_name: str):
        return contact.session["telco"].get(field_name)

# TODO: NEED TO BE ABLE TO REFRESH
