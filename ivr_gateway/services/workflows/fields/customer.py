from sqlalchemy import orm

from ivr_gateway.models.enums import ProductType
from ivr_gateway.models.workflows import WorkflowRun
from ivr_gateway.services.amount.customer import CustomerSummaryService
from ivr_gateway.services.workflows.exceptions import NotInRegistryException
from ivr_gateway.services.workflows.fields.lookup import FieldLookupServiceABC


class CustomerSummaryFieldLookupService(FieldLookupServiceABC):
    card_fields = frozenset([
        "type",
        "id",
        "past_due_amount_cents",
        "total_minimum_payment_due_cents",
        "remaining_statement_balance_cents",
        "current_balance_cents"
    ])
    loan_fields = frozenset([
        "id",
        "type",
        "in_grace_period",
        "can_make_ach_payment",
        "can_run_check_balance_and_quote_payoff",
        "past_due_amount_cents",
        "next_payment_date",
        "next_payment_amount",
        "next_payment_method"
    ])
    product_fields = loan_fields.union(card_fields)
    field_registry = (
        'applications_count',
        'products_count',
        'number_of_open_applications',
        'application_id',
        'application_type',
        'loan_count',
        'card_count',
        'loan_application_count',
        'card_application_count'
    )
    field_registry += tuple(map(lambda field: "loan_" + field, loan_fields))
    field_registry += tuple(map(lambda field: "card_" + field, card_fields))
    field_registry += tuple(map(lambda field: "product_" + field, product_fields))

    def __init__(self, workflow_run: "WorkflowRun", db_session: orm.Session):
        super().__init__(workflow_run, db_session)
        self.client = CustomerSummaryService(db_session, workflow_run.contact_leg.contact)

    def get_field_by_lookup_key(self, lookup_key: str, use_cache: bool = True, service_overrides: dict = None) -> str:
        # TODO: Implement specific service calls on the telco service and route them based on availability
        if lookup_key not in self.field_registry:
            raise NotInRegistryException()
        call = self.workflow_run.contact_leg.contact
        if not use_cache:
            self.client.get_customer_summary(call)
        else:
            self.client.download_info_if_not_cached(call)
        if lookup_key == "products_count":
            return self.client.open_product_count(call)
        elif lookup_key == "applications_count":
            return self.client.open_application_count(call)
        elif lookup_key == "loan_count":
            return self.client.open_product_count(call, product_type=ProductType.Loan)
        elif lookup_key == "card_count":
            return self.client.open_product_count(call, product_type=ProductType.CreditCardAccount)
        elif lookup_key == "loan_application_count":
            return self.client.open_application_count(call, application_type=ProductType.Loan)
        elif lookup_key == "card_application_count":
            return self.client.open_application_count(call, application_type=ProductType.CreditCardAccount)
        elif lookup_key.startswith("product_"):
            return self.client.product_field_lookup(call, lookup_key[len('product_'):])
        elif lookup_key.startswith("application_"):
            return self.client.application_field_lookup(call, lookup_key[len('application_'):])
        elif lookup_key.startswith("loan_"):
            return self.client.product_field_lookup(call, lookup_key[len('loan_'):], product_type=ProductType.Loan)
        elif lookup_key.startswith("card_"):
            return self.client.product_field_lookup(call, lookup_key[len('card_'):],
                                                    product_type=ProductType.CreditCardAccount)
        return self.client.product_field_lookup(call, lookup_key)
