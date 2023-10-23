from typing import TypeVar, Generic

from ivr_gateway.models.steps import StepState

T = TypeVar("T")

DEFAULT_ERROR_MESSAGE = "Unfortunately we did not receive a response or were unable to process your request."


class StepResult(Generic[T]):
    def __init__(self, result: T = None, step_state: StepState = None):
        self.result = result
        self.step_state = step_state

    def set_step_state(self, step_state: StepState):
        self.step_state = step_state

    def __repr__(self):
        return f"<StepResult result: {self.result}, step_state: {self.step_state}>"


class StepSuccess(StepResult[T]):

    def __init__(self, result: T = None, step_state: StepState = None):
        super().__init__(result=result, step_state=step_state)


class StepInputSuccess(StepSuccess):
    pass


class ExternalStepSuccess(StepSuccess[T]):

    def __init__(self, result: T = None, step_state: StepState = None):
        super().__init__(result=result, step_state=step_state)


class StepReplay(StepInputSuccess):
    def __init__(self, result: T = None, step_state: StepState = None):
        super().__init__(result=result, step_state=step_state)


class StepExitQueue(StepInputSuccess):
    def __init__(self, result: T = None, step_state: StepState = None):
        super().__init__(result=result, step_state=step_state)

class StepError(StepResult, Exception):
    def __init__(self, msg: str, retryable: bool = False, reset_step: str = None, step_state: StepState = None,
                 *args, **kwargs):
        kwargs["step_state"] = step_state
        new_args = [msg] + list(args)
        super().__init__(*new_args, **kwargs)
        self.retryable = retryable
        self.reset_step = reset_step
        self.msg = msg

    def __repr__(self):
        return f"<StepError {self.msg}, retryable: {self.retryable}, step_state: {self.step_state}, reset_step: {self.reset_step}>"


class UserStepError(StepError, Exception):
    def __init__(self, msg, user_msg: str = None, step_state: StepState = None, *args, **kwargs):
        self.user_msg = user_msg if user_msg is not None else DEFAULT_ERROR_MESSAGE
        kwargs["step_state"] = step_state
        super().__init__(msg, *args, **kwargs)

    def __repr__(self):
        return f"<StepError {self.msg}, retryable: {self.retryable}, step_state: {self.step_state}, user_msg: {self.user_msg}>"