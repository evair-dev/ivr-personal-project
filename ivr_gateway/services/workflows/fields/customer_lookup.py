from sqlalchemy import orm

from ivr_gateway.models.enums import ProductType
from ivr_gateway.models.workflows import WorkflowRun
from ivr_gateway.services.amount.customer_lookup import CustomerLookupService
from ivr_gateway.services.workflows.exceptions import NotInRegistryException
from ivr_gateway.services.workflows.fields.lookup import FieldLookupServiceABC


class CustomerLookupFieldLookupService(FieldLookupServiceABC):
    card_fields = frozenset([
        "type",
        "id",
        "activatable?",
        "credit_available_cents",
        "past_due_amount_cents",
        "operationally_charged_off?",
        "days_late"
    ])
    loan_fields = frozenset([
        "id",
        "type",
        "funding_date",
        "active_payoff_quote?",
        "product_type",
        "product_subtype",
        "past_due_amount_cents",
        "operationally_charged_off?",
        "in_grace_period?",
        "days_late"
    ])
    product_fields = loan_fields.union(card_fields)
    field_registry = (
        'customer_id',
        'customer_state_of_residence',
        'customer_disaster_relief_plan?',
        'customer_last_contact',
        'applications_count',
        'products_count',
        'loan_count',
        'card_count',
        'number_of_open_applications',
        'application_id',
        'application_type'
    )
    field_registry += tuple(map(lambda field: "loan_" + field, loan_fields))
    field_registry += tuple(map(lambda field: "card_" + field, card_fields))
    field_registry += tuple(map(lambda field: "product_" + field, product_fields))

    def __init__(self, workflow_run: "WorkflowRun", db_session: orm.Session):
        super().__init__(workflow_run, db_session)
        self.client = CustomerLookupService(db_session, workflow_run.contact_leg.contact)

    def get_field_by_lookup_key(self, lookup_key: str, use_cache: bool = True, service_overrides: dict = None) -> str:
        # TODO: Implement specific service calls on the telco service and route them based on availability
        if lookup_key not in self.field_registry:
            raise NotInRegistryException()
        contact = self.workflow_run.contact_leg.contact
        if not use_cache:
            self.client.get_customer_info(contact, service_overrides, self.workflow_run)
        else:
            self.client.download_info_if_not_cached(contact, service_overrides, self.workflow_run)
        if lookup_key == "products_count":
            return self.client.open_product_count(contact)
        elif lookup_key == "applications_count":
            return self.client.open_application_count(contact)
        elif lookup_key == "loan_count":
            return self.client.open_product_count(contact, product_type=ProductType.Loan)
        elif lookup_key == "card_count":
            return self.client.open_product_count(contact, product_type=ProductType.CreditCardAccount)
        elif lookup_key.startswith("product_"):
            return self.client.product_field_lookup(contact, lookup_key[len('product_'):])
        elif lookup_key.startswith("application_"):
            return self.client.application_field_lookup(contact, lookup_key[len('application_'):])
        elif lookup_key.startswith("customer_"):
            return self.client.customer_field_lookup(contact, lookup_key[len('customer_'):])
        elif lookup_key.startswith("loan_"):
            return self.client.product_field_lookup(contact, lookup_key[len('loan_'):], product_type=ProductType.Loan)
        elif lookup_key.startswith("card_"):
            return self.client.product_field_lookup(contact, lookup_key[len('card_'):],
                                                    product_type=ProductType.CreditCardAccount)
        return self.client.product_field_lookup(contact, lookup_key)
