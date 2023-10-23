from ddtrace import tracer

from ivr_gateway.steps.api.v1.base import APIV1Step
from ivr_gateway.steps.result import StepResult, StepSuccess

__all__ = [
    "NoopStep"
]


class NoopStep(APIV1Step):
    """
    Used to represent a step w/ no operation, needs to be ABC b/c we need gateway and external versions that are
    concrete to input
    """

    @tracer.wrap()
    def run(self) -> StepResult:
        return self.save_result(result=StepSuccess(result=None))
