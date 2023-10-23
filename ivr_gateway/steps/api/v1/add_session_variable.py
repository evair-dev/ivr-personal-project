from ddtrace import tracer

from ivr_gateway.steps.api.v1.base import APIV1Step
from ivr_gateway.steps.result import StepResult, StepSuccess
from ivr_gateway.steps.utils import get_field

__all__ = [
    "CopySessionVariable"
]


class CopySessionVariable(APIV1Step):
    def __init__(self, name: str, existing_field: str, new_field_name, *args, **kwargs):
        self.existing_field = existing_field
        self.new_field_name = new_field_name
        kwargs.update({
            "existing_field": existing_field,
            "new_field_name": new_field_name
        })
        self.value = None
        super().__init__(name, *args, **kwargs)

    @tracer.wrap()
    def run(self) -> StepResult:
        workflow_run = self.step_run.workflow_run
        self.value = get_field(self.existing_field, workflow_run)
        workflow_run.store_session_variable(self.new_field_name, self.value)
        return self.save_result(result=StepSuccess(result=self.value))
