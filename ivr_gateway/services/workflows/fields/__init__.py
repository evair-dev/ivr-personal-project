from sqlalchemy import orm

from ivr_gateway.models.workflows import WorkflowRun
from ivr_gateway.services.workflows.exceptions import MissingWorkflowService
from ivr_gateway.services.workflows.fields.call import CallFieldLookupService
from ivr_gateway.services.workflows.fields.customer import CustomerSummaryFieldLookupService
from ivr_gateway.services.workflows.fields.customer_lookup import CustomerLookupFieldLookupService
from ivr_gateway.services.workflows.fields.lookup import FieldLookupServiceABC
from ivr_gateway.services.workflows.fields.telco import TelcoFieldLookupService
from ivr_gateway.services.workflows.fields.queue import QueueFieldLookupService

WORKFLOW_SERVICE_REGISTRY = {
    "customer": CustomerSummaryFieldLookupService,
    "call": CallFieldLookupService,
    "customer_lookup": CustomerLookupFieldLookupService,
    "queue": QueueFieldLookupService,
    "telco": TelcoFieldLookupService,
}


class FieldSessionService:

    def __init__(self, db_session: orm.Session):
        self.db_session = db_session

    def get_service_for_workflow(self, workflow_run: WorkflowRun, service_name: str) -> FieldLookupServiceABC:
        if service_name in WORKFLOW_SERVICE_REGISTRY:
            return WORKFLOW_SERVICE_REGISTRY[service_name](workflow_run, self.db_session)
        else:
            raise MissingWorkflowService(
                f"Missing an entry for {service_name} in WORKFLOW_SERVICE_REGISTRY: {WORKFLOW_SERVICE_REGISTRY}"
            )

    def get_field_for_step(self, workflow_run: WorkflowRun, service_name: str, lookup_key: str,
                           use_cache: bool = True, service_overrides: dict = None) -> str:
        service = self.get_service_for_workflow(workflow_run, service_name)
        return service.get_field_by_lookup_key(lookup_key, use_cache=use_cache, service_overrides=service_overrides)
