from abc import ABC, abstractmethod
from typing import Union

from ivr_gateway.exit_paths import ExitPath
from ivr_gateway.models.steps import StepRun, StepState
from ivr_gateway.steps.inputs import StepInput
from ivr_gateway.steps.result import StepResult

__all__ = [
    "Step",
    "NextStepOrExit",
    "DEFAULT_RETRY_COUNT"
]

DEFAULT_RETRY_COUNT = 3


class Step(ABC):
    """
    Domain object used to record, and track user interactions and be a way to map behavior
    across multiple subclassed types while maintaining centralized audibility
    """

    def __init__(self, name: str, step_run: StepRun = None, step_state: StepState = None,
                 on_error_reset_to_step: str = None, on_error_switch_to_branch: str = None,
                 retry_count: int = DEFAULT_RETRY_COUNT, *args, **kwargs):
        self.name = name
        self.args = args
        self.kwargs = kwargs
        self.step_run = step_run
        self.step_state = step_state
        self.on_error_reset_to_step = on_error_reset_to_step
        self.on_error_switch_to_branch = on_error_switch_to_branch
        self.retry_count = retry_count

    @abstractmethod
    def run(self) -> StepResult:  # pragma: no cover
        pass

    @abstractmethod
    def get_type_string(self) -> str:  # pragma: no cover
        pass

    @abstractmethod
    def save_result(self, result: StepResult = None, step_input: StepInput = None) -> StepResult:
        pass

    def __repr__(self):
        return f"<Step name: {self.name}, step_run: {self.step_run}>"


NextStepOrExit = Union[Step, ExitPath]
