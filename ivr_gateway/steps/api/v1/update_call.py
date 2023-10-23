from datetime import datetime

from ddtrace import tracer

from ivr_gateway.services.queues import QueueService
from ivr_gateway.steps.api.v1.base import APIV1Step
from ivr_gateway.steps.result import StepResult, StepSuccess

__all__ = [
    "UpdateCallStep",
    "SecureCallStep",
    "UpdateCurrentQueueStep"
]


class UpdateCallStep(APIV1Step):
    """
    Used to represent a step w/ no operation, needs to be ABC b/c we need gateway and external versions that are
    concrete to input
    """

    def run(self) -> StepResult:
        return self.save_result(result=StepSuccess(result=None))


class SecureCallStep(UpdateCallStep):

    def __init__(self, name: str, *args, **kwargs):
        super().__init__(name, *args, **kwargs)

    @tracer.wrap()
    def run(self) -> StepResult:
        workflow_run = self.step_run.workflow_run
        workflow_state = workflow_run.session.get("state")
        secure_call_key = workflow_state.get("action_to_take")
        if secure_call_key == "NOT_SECURED":
            step_result = StepResult(secure_call_key)
            step_result = self.save_result(step_result)
            success_result = StepSuccess(result=step_result)
            success_result.step_state = step_result.step_state
            return success_result
        call = workflow_run.contact_leg.contact
        call.secured = datetime.now()
        call.secured_key = secure_call_key
        step_result = StepResult(result=call.secured.isoformat())
        step_result = self.save_result(step_result)
        success_result = StepSuccess(result=step_result)
        success_result.step_state = step_result.step_state
        return success_result


class UpdateCurrentQueueStep(UpdateCallStep):
    def __init__(self, name: str, queue: str = None, *args, **kwargs):
        self.queue = queue
        kwargs.update({
            "queue": queue,
        })
        super().__init__(name, *args, **kwargs)

    @tracer.wrap()
    def run(self, queue_service: "QueueService" = None) -> StepResult:
        new_queue = queue_service.get_queue_by_name(self.queue)
        workflow_run = self.step_run.workflow_run
        workflow_run.current_queue = new_queue
        result = StepSuccess(result=self.queue)
        return self.save_result(result=result)
