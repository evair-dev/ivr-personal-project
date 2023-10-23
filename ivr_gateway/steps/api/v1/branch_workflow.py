from abc import ABC
from typing import Dict

from ddtrace import tracer

from ivr_gateway.steps.api.v1.base import APIV1Step
from ivr_gateway.steps.result import StepResult, StepSuccess, StepError
from ivr_gateway.steps.utils import get_field

__all__ = [
    "BranchWorkflowStep",
    "BranchMapWorkflowStep",
    "JumpBranchStep"
]


class BranchWorkflowStep(APIV1Step, ABC):
    def __init__(self, name: str, *args, **kwargs):
        super().__init__(name, *args, **kwargs)


class BranchMapWorkflowStep(BranchWorkflowStep):
    """
    Tree Step Config
    {
        "name": "step-name",
        "step_type": BranchWorkflowStep.get_type_string(),
        "step_kwargs": {
            "field": "field-name"
            "on_error_reset_to_step": "step-name",
            "branches": {
                "branch-1-value" : "branch-1,
                "branch-2-value" : "branch-2
            }
        }
    }
    """

    def __init__(self, name: str, field: str = None, branches: Dict[str, str] = None, default_branch: str = None, *args,
                 **kwargs):
        self.field = field
        self.branches = branches
        self.default_branch = default_branch
        kwargs.update({
            "field": field,
            "branches": branches,
            "default_branch": default_branch
        })
        super().__init__(name, *args, **kwargs)

    @tracer.wrap()
    def run(self) -> StepResult:
        workflow_run = self.step_run.workflow_run
        branch_name = get_field(self.field, workflow_run)
        branch_name = str(branch_name)
        new_branch = self.branches.get(branch_name)
        if new_branch is None:
            new_branch = self.default_branch
        if new_branch is not None and workflow_run.is_valid_step_branch(new_branch):
            return self.save_result(result=StepSuccess(result=new_branch))
        else:
            error = StepError(f"Error switching to branch: {new_branch}", retryable=True,
                              reset_step=self.on_error_reset_to_step)
            raise self.save_result(result=error)


class JumpBranchStep(BranchWorkflowStep):
    """
    Tree Step Config
    {
        "name": "step-name",
        "step_type": BranchWorkflowStep.get_type_string(),
        "step_kwargs": {
            "branch": "branch-name" # Name of the branch to jump to
            "on_error_reset_to_step": "step-name",
        }
    }
    """

    def __init__(self, name: str, branch: str = None, *args, **kwargs):
        self.branch = branch
        kwargs.update({
            "branch": branch
        })
        super().__init__(name, *args, **kwargs)

    @tracer.wrap()
    def run(self) -> StepResult:
        return self.save_result(result=StepSuccess(result=self.branch))
