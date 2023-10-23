from typing import Optional, Union
from uuid import UUID

from sqlalchemy import orm

from ivr_gateway.steps.config import StepTree
from ivr_gateway.models.contacts import ContactLeg
from ivr_gateway.models.workflows import WorkflowRun
from ivr_gateway.services.workflows.exceptions import NotInRegistryException
from ivr_gateway.services.workflows.fields.lookup import FieldLookupServiceABC
from commands.workflow_registry import workflow_step_tree_registry
from step_trees.shared.ivr.banking_menu import banking_menu_step_tree


class CallFieldLookupService(FieldLookupServiceABC):
    field_registry = (
        'secured',
        'secured_key',
        'is_banking_call'
    )

    def __init__(self, workflow_run: "WorkflowRun", db_session: orm.Session):
        super().__init__(workflow_run, db_session)

    def get_field_by_lookup_key(self, lookup_key: str, use_cache: bool = True,
                                service_overrides: dict = None) -> Optional[Union[bool, str]]:
        # TODO: Implement specific service calls on the telco service and route them based on availability
        if lookup_key not in self.field_registry:
            raise NotInRegistryException()
        call = self.workflow_run.contact_leg.contact
        if lookup_key == "secured":
            if call.secured is None:
                return None
            return call.secured.isoformat()
        elif lookup_key == "secured_key":
            return call.secured_key
        elif lookup_key == "is_banking_call":
            return self._check_if_transferred_from_workflow(self.workflow_run.contact_leg.contact_id,
                                                            banking_menu_step_tree)

    def _check_if_transferred_from_workflow(self, contact_id: Optional[UUID], step_tree: StepTree) -> bool:
        if contact_id is not None:
            # search the workflow registry for workflow name based on step tree type
            workflow_name = [name for name, tree in workflow_step_tree_registry.items() if tree == step_tree][0]
            # get all contact legs for a customer call
            contact_legs = (self.db_session.query(ContactLeg)
                            .filter(ContactLeg.contact_id == contact_id)
                            .all())
            call_workflow_names = [contact_leg.workflow_run.workflow.workflow_name for contact_leg in contact_legs]
            return workflow_name in call_workflow_names

        return False
