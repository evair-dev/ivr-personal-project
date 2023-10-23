from ivr_gateway.models.exceptions import MissingWorkflowStepConfigurationException
from ivr_gateway.models.workflows import WorkflowRun
from ivr_gateway.steps.config import Step, StepBranch


def get_step_template_from_workflow(workflow_run: WorkflowRun, step_name: str, branch_name=None) -> Step:
    """
    Move to workflow service

    :param workflow_run:
    :param step_name:
    :param branch_name:
    :return:
    """
    if branch_name is None:
        branch_name = workflow_run.current_step_branch_name
    # Index into the step_config_branch
    step_branch = get_step_branch_from_workflow(workflow_run, branch_name)
    # Extract out the
    try:
        return next((x for x in step_branch.steps if x.name == step_name))
    except StopIteration:
        raise MissingWorkflowStepConfigurationException(
            f"Missing step config for {step_name} in "
            f"{map(lambda x: x.name, step_branch.steps)}"
        )


def get_step_branch_from_workflow(workflow_run: WorkflowRun, branch_name: str) -> StepBranch:
    """
    Move to workflow service

    :param workflow_run:
    :param branch_name:
    :return:
    """
    # Index into the step_config_branch
    try:
        return next((
            x for x in workflow_run.workflow_config.step_tree.branches if x.name == branch_name
        ))
    except StopIteration:
        raise MissingWorkflowStepConfigurationException(
            f"Missing step branch for {branch_name} in "
            f"{map(lambda x: x.name, workflow_run.workflow_config.step_tree.branches)}"
        )
