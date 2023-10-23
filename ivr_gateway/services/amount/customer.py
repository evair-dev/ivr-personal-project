import requests
from ddtrace import tracer
from sqlalchemy import orm
from json import JSONDecodeError

from ivr_gateway.models.contacts import Contact
from ivr_gateway.services.amount import AmountService


class CustomerSummaryService(AmountService):
    def __init__(self, db_session: orm.Session, contact: Contact):
        super().__init__(db_session, contact=contact)
        self.endpoint = f"{self.base_url}/api/v1/customer_summary"

    def get_customer_summary(self, contact: Contact) -> int:
        customer_id = contact.customer_id
        if customer_id is None:
            contact.session["customer_summary"] = {}
            self.db_session.add(contact)
            self.db_session.commit()
            return 0
        parameters = {"customer_id": customer_id}

        with tracer.trace('amount_service.api.v1.customer_summary'):
            def request():
                return requests.get(self.endpoint, headers=self.headers, params=parameters, timeout=self.timeout)
            exception_occurred, response = self._attempt_request(
                request=request,
                amount_endpoint=self.endpoint,
                tag_name="amount_service.customer_summary.status_code",
                exception_result=0,
                contact=contact)
            if exception_occurred:
                return response
        session = contact.session.copy()

        try:
            session.update({"customer_summary": response.json()})
        except JSONDecodeError:
            contact.session["customer_summary"] = {}
            self.db_session.add(contact)
            self.db_session.commit()
            return 0

        contact.session = session

        self.db_session.add(contact)
        self.db_session.commit()
        return len(contact.session.get("customer_summary", {}).get("open_products", []))

    def download_info_if_not_cached(self, contact: Contact):
        if contact.session.get("customer_summary") is None:
            self.get_customer_summary(contact)

    @staticmethod
    def product_field_lookup(contact: Contact, field_name: str, product_type: str = None):
        customer_summary = contact.session.get("customer_summary", {})
        open_products = customer_summary.get("open_products", None)
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
        customer_summary = contact.session.get("customer_summary", {})
        open_applications = customer_summary.get("open_applications", None)
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
    def open_product_count(contact: Contact, product_type: str = None):
        customer_summary = contact.session.get("customer_summary", {})
        open_products = customer_summary.get("open_products", [])
        if product_type:
            return len([product for product in open_products if product.get("type") == product_type])
        return len(open_products)

    @staticmethod
    def open_application_count(contact: Contact, application_type: str = None):
        customer_summary = contact.session.get("customer_summary", {})
        open_applications = customer_summary.get("open_applications", [])
        if application_type:
            return len([app for app in open_applications if app.get("type") == application_type])
        return len(open_applications)
