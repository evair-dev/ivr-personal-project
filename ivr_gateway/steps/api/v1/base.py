from abc import ABC

from ivr_gateway.steps.api import APIStep
from ivr_gateway.steps.base import Step
from ivr_gateway.steps.inputs import StepInput
from ivr_gateway.steps.result import StepError, StepResult


class APIV1Step(APIStep, ABC):
    version = "v1"

    def _save_error(self, error: StepError = None, step_input: StepInput = None) -> StepResult:
        from ivr_gateway.steps.api.v1.input import InputStep
        """
        Method for centralizing collecting and logging errors to the step state
        :param error:
        :param step_input:
        :return:
        """
        if isinstance(self, InputStep):
            maybe_input = {
                "input_prompt": self.input_prompt,
                "value": step_input.input_value if step_input is not None else None
            }
        else:
            maybe_input = {}
        error.step_state = self.step_run.create_state_update(step_input=maybe_input, step_result={
            "value": None,
            "message": repr(error),
        }, error=True, retryable=error.retryable)
        return error

    def save_result(self, result: StepResult = None, step_input: StepInput = None) -> StepResult:
        from ivr_gateway.steps.api.v1.input import InputStep

        if isinstance(result, StepError):
            return self._save_error(error=result, step_input=step_input)
        elif isinstance(self, InputStep):
            result.step_state = self.step_run.create_state_update(
                step_input={
                    "input_prompt": self.input_prompt,
                    "value": step_input.get()
                },
                step_result={
                    "value": result.result if result is not None else None
                }
            )
        elif isinstance(self, Step):
            # For type checker
            result.step_state = self.step_run.create_state_update(step_input={}, step_result={
                "value": result.result if result is not None else None
            })
        return result
