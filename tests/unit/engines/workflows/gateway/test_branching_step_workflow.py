import pytest
from sqlalchemy.orm import Session as SQLAlchemySession

from ivr_gateway.engines.workflows import WorkflowEngine
from ivr_gateway.exit_paths import HangUpExitPath
from ivr_gateway.models.enums import WorkflowState
from ivr_gateway.models.workflows import WorkflowRun, Workflow
from ivr_gateway.steps.api.v1 import PlayMessageStep, InputActionStep, BranchWorkflowStep, \
    BranchMapWorkflowStep
from ivr_gateway.steps.config import StepTree, StepBranch, Step
from ivr_gateway.steps.inputs import MenuActionInput
from ivr_gateway.steps.result import StepSuccess, StepError
from tests.factories import workflow as wcf


class TestBranchingStepGatewayWorkflow:

    @pytest.fixture
    def step_tree(self) -> StepTree:
        return StepTree(
            branches=[
                StepBranch(
                    name="root",
                    steps=[
                        Step(
                            name="step-1",
                            step_type=PlayMessageStep.get_type_string(),
                            step_kwargs={
                                "template": "Hello from Iivr"
                            }
                        ),
                        Step(
                            name="step-2",
                            step_type=InputActionStep.get_type_string(),
                            step_kwargs={
                                "name": "enter_number",
                                "input_key": "number",
                                "input_prompt": "Please enter a number",
                                "actions": [{
                                    "name": "opt-1", "display_name": "Option 1"
                                }, {
                                    "name": "opt-2", "display_name": "Option 2"
                                }],
                            },
                        ),
                        Step(
                            name="step-3",
                            step_type=BranchMapWorkflowStep.get_type_string(),
                            step_kwargs={
                                "field": "step[root:step-2].input.value",
                                "on_error_reset_to_step": "step-2",
                                "branches": {
                                    "opt-1": "branch-1",
                                },
                            },
                        ),
                    ]
                ),
                StepBranch(
                    name="branch-1",
                    steps=[
                        Step(
                            name="step-3",
                            step_type=PlayMessageStep.get_type_string(),
                            step_kwargs={
                                "template": "You have selected option 1. Goodbye from Iivr."
                            },
                            exit_path={
                                "exit_path_type": HangUpExitPath.get_type_string(),
                            },
                        )]
                ),
                StepBranch(
                    name="branch-2",
                    steps=[
                        Step(
                            name="step-3",
                            step_type=PlayMessageStep.get_type_string(),
                            step_kwargs={
                                "template": "You might have selected option 2 or had some field in your session. "
                                            "Goodbye."
                            },
                            exit_path={
                                "exit_path_type": HangUpExitPath.get_type_string(),
                            },
                        )]
                ),
            ]
        )

    @pytest.fixture
    def workflow(self, db_session: SQLAlchemySession, step_tree: StepTree) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "branching_workflow", step_tree=step_tree)
        return workflow_factory.create()

    @pytest.fixture
    def workflow_run(self, db_session: SQLAlchemySession, workflow: Workflow) -> WorkflowRun:
        run = WorkflowRun(workflow=workflow, workflow_config=workflow.latest_config)
        db_session.add(run)
        db_session.commit()
        return run

    def test_4_step_branching_workflow_with_input(self, db_session: SQLAlchemySession, workflow: Workflow,
                                                  workflow_run: WorkflowRun):
        engine = WorkflowEngine(db_session, workflow_run)
        engine.initialize()
        # Run the first step
        current_step = engine.get_current_step()
        result, next_step_or_exit = engine.run_current_workflow_step()
        assert isinstance(next_step_or_exit, InputActionStep)
        assert isinstance(result, StepSuccess)
        assert current_step.step_run is not None
        if current_step.step_run:
            assert not current_step.step_run.state.error
            assert current_step.step_run.state.result["value"] == "Hello from Iivr"
        # Run input step
        current_step = engine.get_current_step()
        result, next_step_or_exit = engine.run_current_workflow_step(
            step_input=MenuActionInput("number", 1, menu_actions=next_step_or_exit.actions)
        )
        assert isinstance(result, StepSuccess)
        assert isinstance(next_step_or_exit, BranchWorkflowStep)
        assert current_step.step_run is not None
        if current_step.step_run:
            assert not current_step.step_run.state.error
            assert current_step.step_run.state.input["input_prompt"] == "Please enter a number"
            assert current_step.step_run.state.input["value"] == "opt-1"
        result, next_step_or_exit = engine.run_current_workflow_step()
        assert workflow_run.state == WorkflowState.step_in_progress
        assert isinstance(result, StepSuccess)
        assert isinstance(next_step_or_exit, PlayMessageStep)
        assert workflow_run.current_step_branch_name == "branch-1"
        assert workflow_run.get_current_step_run().branch == "branch-1"
        # Run final step
        result, next_step_or_exit = engine.run_current_workflow_step()
        assert workflow_run.state == WorkflowState.finished
        assert isinstance(result, StepSuccess)
        assert result.result == "You have selected option 1. Goodbye from Iivr."
        assert isinstance(next_step_or_exit, HangUpExitPath)

    def test_error_input_creates_reset_to_step(self, db_session: SQLAlchemySession, workflow: Workflow,
                                               workflow_run: WorkflowRun):
        engine = WorkflowEngine(db_session, workflow_run)
        engine.initialize()
        # Run the first step
        result, next_step_or_exit = engine.run_current_workflow_step()
        assert isinstance(next_step_or_exit, InputActionStep)
        assert isinstance(result, StepSuccess)
        # Run input step
        engine.run_current_workflow_step(
            step_input=MenuActionInput("number", 2, menu_actions=next_step_or_exit.actions)
        )
        result, next_step_or_exit = engine.run_current_workflow_step()
        # Run final step
        assert isinstance(result, StepError)
        assert isinstance(next_step_or_exit, InputActionStep)
        assert next_step_or_exit.name == "step-2"
        result, next_step_or_exit = engine.run_current_workflow_step(
            step_input=MenuActionInput("number", 1, menu_actions=next_step_or_exit.actions)
        )
        assert isinstance(next_step_or_exit, BranchWorkflowStep)
        assert next_step_or_exit.name == "step-3"
        # Run the branch
        result, next_step_or_exit = engine.run_current_workflow_step()
        assert isinstance(result, StepSuccess)
        assert isinstance(next_step_or_exit, PlayMessageStep)
        result, next_step_or_exit = engine.run_current_workflow_step()
        assert isinstance(next_step_or_exit, HangUpExitPath)
