from typing import Optional

import requests
from ddtrace import tracer
from sqlalchemy import orm
from json import JSONDecodeError

from ivr_gateway.models.contacts import Contact
from ivr_gateway.models.workflows import WorkflowRun
from ivr_gateway.services.amount import AmountService
from ivr_gateway.steps.utils import get_field


class CustomerLookupService(AmountService):
    def __init__(self, db_session: orm.Session, contact: Contact):
        super().__init__(db_session, contact=contact)
        self.endpoint = f"{self.base_url}/api/v1/phone_number_customer_lookup"

    def get_customer_info(self, contact: Contact, service_overrides: dict, workflow_run: WorkflowRun) -> int:
        if service_overrides is not None and service_overrides.get("lookup_phone_number") is not None:
            lookup_phone_number = get_field(service_overrides.get("lookup_phone_number"), workflow_run)
        else:
            lookup_phone_number = self.get_customer_phone_number_from_contact(contact)

        if lookup_phone_number is None:
            contact.session["customer_lookup"] = {}
            self.db_session.add(contact)
            self.db_session.commit()
            return 0

        parameters = {"phone_number": lookup_phone_number}

        with tracer.trace('amount_service.api.v1.phone_number_customer_lookup'):
            def request():
                return requests.get(self.endpoint, headers=self.headers, params=parameters, timeout=self.timeout)
            exception_occurred, response = self._attempt_request(
                request=request,
                amount_endpoint=self.endpoint,
                tag_name="amount_service.phone_number_costumer_lookup.status_code",
                exception_result=0,
                contact=contact)
            if exception_occurred:
                return response

        session = contact.session.copy()

        try:
            session.update({"customer_lookup": response.json()})
        except JSONDecodeError:
            contact.session["customer_lookup"] = {}
            self.db_session.add(contact)
            self.db_session.commit()
            return 0

        contact.session = session

        customer_information = response.json().get("customer_information")
        if customer_information is not None:
            contact.customer_id = str(customer_information.get("id"))
        self.db_session.add(contact)
        self.db_session.commit()
        return len(contact.session.get("customer_lookup", {}).get("open_products", []))

    def download_info_if_not_cached(self, contact: Contact, service_overrides: dict, workflow_run: WorkflowRun):
        if contact.session.get("customer_lookup") is None:
            self.get_customer_info(contact, service_overrides, workflow_run)

    @staticmethod
    def get_customer_phone_number_from_contact(contact: Contact) -> Optional[str]:
        if len(contact.contact_legs) == 0:
            return None
        ani = contact.device_identifier
        if ani is None:
            return None
        if ani.startswith("1"):
            return ani[1:]
        return ani

    @staticmethod
    def product_field_lookup(contact: Contact, field_name: str, product_type: str = None):
        customer_info = contact.session.get("customer_lookup", {})
        open_products = customer_info.get("open_products", None)
        if open_products is None:
            return None
        if len(open_products) == 0:
            return None
        if product_type:
            for product in open_products:
                if product.get("type") == product_type:
                    return product.get(field_name)
            return None
        return open_products[0].get(field_name)

    @staticmethod
    def application_field_lookup(contact: Contact, field_name: str, application_type: str = None):
        customer_info = contact.session.get("customer_lookup", {})
        open_applications = customer_info.get("open_applications", None)
        if open_applications is None:
            return None
        if len(open_applications) == 0:
            return None
        if application_type:
            for application in open_applications:
                if application.get("type") == application_type:
                    return application.get(field_name)
            return None
        return open_applications[0].get(field_name)

    @staticmethod
    def customer_field_lookup(contact: Contact, field_name: str):
        customer_info = contact.session.get("customer_lookup", {})
        customer_information = customer_info.get("customer_information", None)
        if customer_information is None:
            return None
        return customer_information.get(field_name)

    @staticmethod
    def open_product_count(contact: Contact, product_type: str = None):
        customer_info = contact.session.get("customer_lookup", {})
        open_products = customer_info.get("open_products", [])
        if product_type:
            return len([product for product in open_products if product.get("type") == product_type])
        return len(open_products)

    @staticmethod
    def open_application_count(contact: Contact, application_type: str = None):
        customer_info = contact.session.get("customer_lookup", {})
        open_applications = customer_info.get("open_applications", [])
        if application_type:
            return len([app for app in open_applications if app.get("type") == application_type])
        return len(open_applications)
