from typing import Type, List

from ddtrace import tracer

from ivr_gateway.serde.steps.action import StepActionSchema, NumberedStepActionSchema
from ivr_gateway.steps.action import NumberedStepAction, StepAction
from ivr_gateway.steps.api.v1.base import APIV1Step
from ivr_gateway.steps.api.v1.play_message import PlayMessageStep
from ivr_gateway.steps.exceptions import StepInitializationException
from ivr_gateway.steps.inputs import StringInput, StepInput, StepInputBindingException, MenuActionInput, NumberedMenuActionInput
from ivr_gateway.steps.result import StepResult, StepError, StepInputSuccess, StepReplay, UserStepError,StepExitQueue
from ivr_gateway.utils import dynamic_class_loader

__all__ = [
    "InputStep",
    "InputActionStep",
    "NumberedInputActionStep",
    "ConfirmationStep",
    "AgreementStep"
]
DEFAULT_TIMEOUT = 6


class InputStep(APIV1Step):

    def __init__(self, name: str, input_key: str = None, input_prompt: str = None, input_type: str = None,
                 timeout: int = None, start_new_message: bool = False, error_message: str = None, *args, **kwargs):
        self.input_key = input_key
        self._input_prompt = input_prompt
        self.input_type = input_type or StringInput.get_type_string()
        self.timeout = timeout if timeout is not None else DEFAULT_TIMEOUT
        self.start_new_message = start_new_message
        self.error_message = error_message
        kwargs.update({
            "input_key": input_key,
            "input_prompt": input_prompt,
            "input_type": input_type,
            "timeout": timeout,
            "start_new_message": start_new_message,
            "error_message": error_message
        })
        super().__init__(name, *args, **kwargs)

    @tracer.wrap()
    def run(self, step_input: StepInput = None) -> StepResult:
        return input_step_run_strategy(self, step_input)

    def get_input_type(self) -> Type[StepInput]:
        input_cls = dynamic_class_loader(self.input_type)
        assert issubclass(input_cls, StepInput)  # nosec
        return input_cls

    def map_user_input_to_input_type(self, input_value: str) -> StepInput:
        DynamicInputClass = self.get_input_type()
        return DynamicInputClass(input_key=self.input_key, input_value=input_value)

    @property
    def expected_input_length(self) -> int:
        return self.get_input_type().expected_input_length

    @property
    def input_prompt(self):
        return self._input_prompt


def input_step_run_strategy(input_step: InputStep, step_input: StepInput) -> StepResult:
    if step_input is None:
        raise input_step.save_result(result=StepError("Required step input missing", retryable=True))
    try:
        if isinstance(step_input, (MenuActionInput, NumberedMenuActionInput)):
            action = step_input.get_action()
            if action is None:
                result = StepExitQueue(result=step_input.get())
            elif action.is_replay:
                result = StepReplay(result=step_input.get())
            else:
                result = StepInputSuccess(result=step_input.get())
        else:
            result = StepInputSuccess(result=step_input.get())
        if input_step.input_key is not None and input_step.step_run.workflow_run is not None:
            input_step.step_run.workflow_run.store_session_variable(input_step.input_key, step_input.get())
    except StepInputBindingException:
        binding_error_msg = "Error binding step input"
        if hasattr(step_input, "input_value") and step_input.input_value in [None, ""]:
            binding_error_msg = "Timeout binding step input"
        raise input_step.save_result(result=UserStepError(msg=binding_error_msg, retryable=True,
                                     user_msg=input_step.error_message), step_input=step_input)
    return input_step.save_result(result=result, step_input=step_input)


class InputActionStep(InputStep):

    def __init__(self, name: str, initial_prompt: str = None, actions: List[StepAction] = None, *args, **kwargs):
        self.actions = actions
        self.initial_prompt = initial_prompt
        schema = StepActionSchema()
        kwargs.update({
            "initial_prompt": initial_prompt,
            "actions": [schema.dump(a) for a in actions]
        })
        super().__init__(name, *args, **kwargs)

    @tracer.wrap()
    def run(self, step_input: StepInput = None) -> StepResult:
        return input_step_run_strategy(self, step_input)

    @property
    def expected_input_length(self) -> int:
        return 1

    @property
    def input_prompt(self):
        if self._input_prompt is not None:
            return self._input_prompt
        key_prompts = []
        for i in range(len(self.actions)):
            key_prompts.append(f"{self.actions[i].display_name}, press {i + 1}.")
        joined_options = " ".join(key_prompts)
        if self.initial_prompt is None:
            return joined_options
        return f"{self.initial_prompt} {joined_options}"

class NumberedInputActionStep(InputStep):
    
    def __init__(self, name: str, initial_prompt: str = None, actions: List[NumberedStepAction] = None, *args, **kwargs):
        self.actions = {}
        for action in actions:
            if action.number in self.actions.keys():
                raise StepInitializationException("NumberedInputActionStep binds two actions to the same input")
            self.actions[int(action.number)] = action
        self.initial_prompt = initial_prompt
        schema = NumberedStepActionSchema()
        kwargs.update({
            "initial_prompt": initial_prompt,
            "actions": [schema.dump(a) for a in actions]
        })
        super().__init__(name, *args, **kwargs)

    @tracer.wrap()
    def run(self, step_input: StepInput = None) -> StepResult:
        return input_step_run_strategy(self, step_input)

    @property
    def expected_input_length(self) -> int:
        return 1

    @property
    def input_prompt(self):
        if self._input_prompt is not None:
            return self._input_prompt
        key_prompts = []
        for i in self.actions.keys():
            key_prompts.append(f"{self.actions[i].display_name}, press {i}.")
        joined_options = " ".join(key_prompts)
        if self.initial_prompt is None:
            return joined_options
        return f"{self.initial_prompt} {joined_options}"

class ConfirmationStep(NumberedInputActionStep, PlayMessageStep):
    def __init__(self, name: str, confirm_key: str = None, confirm_type: str = None, input_prompt: str = None,
                 initial_prompt: str = None, template: str = None, *args, **kwargs):
        self.actions = [NumberedStepAction("correct", "If this is correct",number=1),
                        NumberedStepAction("incorrect", "To try again",number=2),
                        NumberedStepAction("repeat", "To hear this again", is_replay=True, number=9)]

        if template is None:
            if confirm_type is None or confirm_key is None:
                raise StepInitializationException("No valid way to create a confirmation message")
            template = "You entered {{ session." + confirm_key + " | " + confirm_type + " }}"

        self.confirm_key = confirm_key
        self.confirm_type = confirm_type
        kwargs.update({
            "template": template,
            "confirm_type": confirm_type,
            "confirm_key": confirm_key,
            "input_prompt": input_prompt,
            "initial_prompt": initial_prompt,
            "actions": self.actions
        })
        super().__init__(name, *args, **kwargs)

class AgreementStep(NumberedInputActionStep, PlayMessageStep):
    def __init__(self, name: str, confirm_key: str = None, confirm_type: str = None, input_prompt: str = None,
                 initial_prompt: str = None, template: str = None, *args, **kwargs):

        self.actions = [NumberedStepAction("yes", "If yes",number=1),
                        NumberedStepAction("no", "If no",number=2),
                        NumberedStepAction("repeat", "To hear this again", is_replay=True, number=9)]
        if template is None:
            if confirm_type is None or confirm_key is None:
                raise StepInitializationException("No valid way to create a confirmation message")
            template = "You entered {{ session." + confirm_key + " | " + confirm_type + " }}"

        self.confirm_key = confirm_key
        self.confirm_type = confirm_type
        kwargs.update({
            "template": template,
            "confirm_type": confirm_type,
            "confirm_key": confirm_key,
            "input_prompt": input_prompt,
            "initial_prompt": initial_prompt,
            "actions": self.actions
        })
        super().__init__(name, *args, **kwargs)
