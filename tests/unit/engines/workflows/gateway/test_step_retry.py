import pytest
from sqlalchemy.orm import Session as SQLAlchemySession

from ivr_gateway.engines.workflows import WorkflowEngine, WorkflowEngineUnrecoverableException
from ivr_gateway.exit_paths import HangUpExitPath
from ivr_gateway.models.workflows import WorkflowRun, Workflow
from ivr_gateway.steps.api.v1 import InputStep, PlayMessageStep
from ivr_gateway.steps.config import StepTree, StepBranch, Step
from ivr_gateway.steps.inputs import Last4SSNInput
from ivr_gateway.steps.result import StepSuccess, StepError
from tests.factories import workflow as wcf


class TestStepRetry:

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
                            name="last-4-ssn",
                            step_type=InputStep.get_type_string(),
                            step_kwargs={
                                "input_key": "number",
                                "input_prompt": "Please enter last 4 of your social security number",
                                "input_type": Last4SSNInput.get_type_string()

                            },
                        ),
                        Step(
                            name="play-last-4-ssn",
                            step_type=PlayMessageStep.get_type_string(),
                            step_kwargs={
                                "fieldset": [
                                    ("step[root:last-4-ssn].input.value", "last4_input")
                                ],
                                "template": "You entered {{ last4_input }}, thank you."
                            },
                            exit_path={
                                "exit_path_type": HangUpExitPath.get_type_string(),
                            },
                        ),
                    ]
                ),
            ]
        )

    @pytest.fixture
    def workflow(self, db_session: SQLAlchemySession, step_tree: StepTree) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "step_retry", step_tree=step_tree)
        return workflow_factory.create()

    @pytest.fixture
    def workflow_run(self, db_session: SQLAlchemySession, workflow: Workflow) -> WorkflowRun:
        run = WorkflowRun(workflow=workflow, workflow_config=workflow.latest_config)
        db_session.add(run)
        db_session.commit()
        return run

    def test_workflow_runs_correctly(self, db_session: SQLAlchemySession, workflow: Workflow,
                                     workflow_run: WorkflowRun):
        engine = WorkflowEngine(db_session, workflow_run)
        engine.initialize()
        # Run the first step
        result, next_step_or_exit = engine.run_current_workflow_step()
        assert isinstance(next_step_or_exit, InputStep)
        assert isinstance(result, StepSuccess)
        # Construct a StepInput using the step
        step_input = next_step_or_exit.map_user_input_to_input_type("1234")
        # Run the step using the constructed input
        result, next_step_or_exit = engine.run_current_workflow_step(step_input=step_input)
        # Run the step using the constructed input
        assert isinstance(result, StepSuccess)
        assert isinstance(next_step_or_exit, PlayMessageStep)
        result, next_step_or_exit = engine.run_current_workflow_step()
        assert result.result == "You entered 1234, thank you."

    def test_workflow_handles_incorrect_input(self, db_session: SQLAlchemySession, workflow: Workflow,
                                              workflow_run: WorkflowRun):
        engine = WorkflowEngine(db_session, workflow_run)
        engine.initialize()
        # Run the first step
        result, next_step_or_exit = engine.run_current_workflow_step()
        assert isinstance(next_step_or_exit, InputStep)
        assert isinstance(result, StepSuccess)
        input_step = next_step_or_exit
        step_input = next_step_or_exit.map_user_input_to_input_type("12345")
        result, next_step_or_exit = engine.run_current_workflow_step(step_input=step_input)
        assert isinstance(result, StepError)
        assert isinstance(next_step_or_exit, InputStep)
        step_input = next_step_or_exit.map_user_input_to_input_type("1234")
        result, next_step_or_exit = engine.run_current_workflow_step(step_input=step_input)
        assert isinstance(result, StepSuccess)
        assert isinstance(next_step_or_exit, PlayMessageStep)
        result, next_step_or_exit = engine.run_current_workflow_step()
        assert result.result == "You entered 1234, thank you."
        step_run = workflow_run.get_branch_step_run("root", input_step.name)
        assert step_run.run_count == 2

    def test_workflow_fails_when_receiving_3_wrong_inputs(self, db_session: SQLAlchemySession, workflow: Workflow,
                                                          workflow_run: WorkflowRun):
        engine = WorkflowEngine(db_session, workflow_run)
        engine.initialize()
        # Run the first step
        result, next_step_or_exit = engine.run_current_workflow_step()
        assert isinstance(next_step_or_exit, InputStep)
        assert isinstance(result, StepSuccess)
        step_input = next_step_or_exit.map_user_input_to_input_type("12345")
        engine.run_current_workflow_step(step_input=step_input)
        engine.run_current_workflow_step(step_input=step_input)
        with pytest.raises(WorkflowEngineUnrecoverableException):
            engine.run_current_workflow_step(step_input=step_input)
        assert workflow_run.get_current_step_run().run_count == 3
