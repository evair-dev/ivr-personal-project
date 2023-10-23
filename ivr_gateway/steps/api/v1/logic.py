from abc import abstractmethod, ABC
from typing import Tuple, Any

from ddtrace import tracer

from ivr_gateway.steps.api.v1.base import APIV1Step
from ivr_gateway.steps.result import StepResult, StepSuccess, StepError
from ivr_gateway.models.workflows import WorkflowRun

__all__ = [
    "BooleanLogicStep"
]

from ivr_gateway.steps.utils import get_field


class LogicStep(APIV1Step, ABC):
    """
    Step to apply a logic operation on one or many fields or values, and persist the result in a
    workflow_run session field

    Abstract base class used to define required arguments, can operate on a tuple of fields
    """

    def __init__(self, name: str, fieldset: Tuple[str, ...] = None, result_field: str = None, *args, **kwargs):
        """

        :param name: Step name
        :param fieldset: Set of fields name strings or static values that will scope the operation
        :param result_field: Where to store the result of the evaluation
        :param args:
        :param kwargs:
        """
        self.fieldset = fieldset
        self.result_field = result_field
        kwargs.update({
            "fieldset": fieldset,
            "result_field": result_field,
        })
        super().__init__(name, *args, **kwargs)

    @abstractmethod
    def run(self) -> StepResult:  # pragma: no cover
        pass


class BooleanLogicStep(LogicStep):
    """
    Step to apply a boolean logic operation on one or two values, and persist the result in a workflow_run
    session field

    Abstract base class used to define required arguments, can operate on a tuple of fields
    """
    unary_operations = (
        "nonnull",
    )
    binary_operations = (
        "==",
        "!=",
        ">",
        "<",
        ">=",
        "<=",
        "&&",
        "||",
    )
    valid_operations = unary_operations + binary_operations

    def __init__(self, name: str, op: str = None, *args, **kwargs):
        """
        Step to apply a boolean logic operation on one or two fields

        :param name: Step name
        :param op: The logical operation to perform
        :param fieldset: List of values that will scope the operation. Either fields name strings of the form
            "session.[field_name]" or static values
        :param result_field: Where to store the result of the evaluation
        :param args:
        :param kwargs:
        """
        self.op = op
        kwargs.update({
            "op": op,
        })
        if op not in self.valid_operations:
            raise ValueError(f"Op supplied {op}, not supported. Valid operations: {self.valid_operations}")
        super().__init__(name, *args, **kwargs)

    def _get_boolean_fields(self, workflow_run: WorkflowRun) -> (Any, Any):
        f1 = get_field(self.fieldset[0], workflow_run)
        f2 = get_field(self.fieldset[1], workflow_run) if self.op in self.binary_operations else None
        return f1, f2

    @tracer.wrap()
    def run(self) -> StepResult:  # pragma: no cover
        workflow_run = self.step_run.workflow_run
        f1, f2 = self._get_boolean_fields(workflow_run)
        op_result = self._perform_op(f1, f2)
        if type(op_result) is not bool:
            raise StepError(f"Non-boolean result of {self.op} operation in boolean logic step")
        workflow_run.store_session_variable(self.result_field, op_result)
        return self.save_result(result=StepSuccess(result=op_result))

    def _perform_op(self, f1, f2) -> bool:
        """
        Returns comparison operation on the fields from the workflow_run session

        Operation in set validated in constructor
        :return: Bool value of operation
        """
        try:
            if self.op == "==":
                return f1 == f2
            elif self.op == "!=":
                return f1 != f2
            elif self.op == ">":
                return f1 > f2
            elif self.op == "<":
                return f1 < f2
            elif self.op == ">=":
                return f1 >= f2
            elif self.op == "<=":
                return f1 <= f2
            elif self.op == "&&":
                return f1 and f2
            elif self.op == "||":
                return f1 or f2
            elif self.op == "nonnull":
                return f1 is not None
        except TypeError:
            if f2:
                raise StepError(f"Cannot perform {self.op} operation in boolean logic step on values of"
                                f" types {str(type(f1))} and {str(type(f2))}")
            else:
                raise StepError(f"Cannot perform {self.op} operation in boolean logic step on value of"
                                f" type {str(type(f1))}")
