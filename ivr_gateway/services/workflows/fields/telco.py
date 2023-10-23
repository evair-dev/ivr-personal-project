from sqlalchemy import orm

from ivr_gateway.models.workflows import WorkflowRun
from ivr_gateway.services.amount.telco import TelcoService
from ivr_gateway.services.workflows.exceptions import NotInRegistryException
from ivr_gateway.services.workflows.fields.lookup import FieldLookupServiceABC


class TelcoFieldLookupService(FieldLookupServiceABC):
    field_registry = (
        'customer_number',
        'success',
        'customer_id',
        'queue',
        'screen_pop',
        'product_id',
        'product_type',
        'product_status'
    )

    def __init__(self, workflow_run: "WorkflowRun", db_session: orm.Session):
        super().__init__(workflow_run, db_session)
        self.client = TelcoService(self.db_session, workflow_run.contact_leg.contact)

    def get_field_by_lookup_key(self, lookup_key: str, use_cache: bool = True, service_overrides: dict = None) -> str:
        # TODO: Implement specific service calls on the telco service and route them based on availability
        if lookup_key not in self.field_registry:
            raise NotInRegistryException()
        contact = self.workflow_run.contact_leg.contact
        if not use_cache:
            self.client.search_client_info(contact)
        else:
            self.client.download_info_if_not_cached(contact)

        if lookup_key == "customer_number":
            return self.client.get_customer_number(contact)

        return self.client.field_lookup(contact, lookup_key)
