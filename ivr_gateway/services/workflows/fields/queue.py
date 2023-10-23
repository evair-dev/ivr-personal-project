from typing import Optional, Union
from uuid import UUID

from sqlalchemy import orm

from ivr_gateway.models.queues import Queue
from ivr_gateway.models.workflows import WorkflowRun
from ivr_gateway.services.workflows.exceptions import NotInRegistryException
from ivr_gateway.services.workflows.fields.lookup import FieldLookupServiceABC


class QueueFieldLookupService(FieldLookupServiceABC):
    field_registry = (
        'past_due_cents_amount',
        'is_pay_queue'
    )

    def __init__(self, workflow_run: "WorkflowRun", db_session: orm.Session):
        super().__init__(workflow_run, db_session)

    def get_field_by_lookup_key(self, lookup_key: str, use_cache: bool = True,
                                service_overrides: dict = None) -> Union[int, bool]:
        if lookup_key not in self.field_registry:
            raise NotInRegistryException()
        if lookup_key == "past_due_cents_amount":
            return self._get_past_due_amount_for_queue_by_id(self.workflow_run.current_queue_id)
        if lookup_key == "is_pay_queue":
            return self._is_pay_queue(self.workflow_run.current_queue)

    def _get_past_due_amount_for_queue_by_id(self, queue_id: Optional[UUID]) -> int:
        if queue_id is not None:
            queue = (self.db_session.query(Queue)
                     .filter(Queue.id == queue_id)
                     .first())
            return queue.past_due_cents_amount
        else:
            return 1000

    def _is_pay_queue(self, queue: Optional[Queue]) -> bool:
        if queue is None:
            return False
        return 'pay' in queue.name.lower()
