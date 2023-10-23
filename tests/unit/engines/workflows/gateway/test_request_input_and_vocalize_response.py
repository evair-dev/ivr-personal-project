import pytest
from sqlalchemy.orm import Session as SQLAlchemySession

from ivr_gateway.engines.workflows import WorkflowEngine
from ivr_gateway.exit_paths import HangUpExitPath
from ivr_gateway.models.workflows import WorkflowRun, Workflow
from ivr_gateway.steps.api.v1 import InputStep, PlayMessageStep
from ivr_gateway.steps.config import StepTree
from ivr_gateway.steps.inputs import IntegerInput
from ivr_gateway.steps.result import StepSuccess
from tests.factories import workflow as wcf
from tests.fixtures.step_trees.gateway_request_input_and_vocalize import step_tree \
    as gateway_request_input_and_vocalize_step_tree


class TestRequestInputAndVocalizeResponse:

    @pytest.fixture
    def step_tree(self) -> StepTree:
        return gateway_request_input_and_vocalize_step_tree

    @pytest.fixture
    def workflow(self, db_session: SQLAlchemySession, step_tree: StepTree) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "main_menu", step_tree=step_tree)
        return workflow_factory.create()

    @pytest.fixture
    def workflow_run(self, db_session: SQLAlchemySession, workflow: Workflow) -> WorkflowRun:
        run = WorkflowRun(workflow=workflow, workflow_config=workflow.latest_config)
        db_session.add(run)
        db_session.commit()
        return run

    def test_input_and_speak_workflow(self, db_session: SQLAlchemySession, workflow: Workflow,
                                      workflow_run: WorkflowRun):
        engine = WorkflowEngine(db_session, workflow_run)
        engine.initialize()
        # Run the first step
        current_step = engine.get_current_step()
        result, next_step_or_exit = engine.run_current_workflow_step()

        assert isinstance(next_step_or_exit, InputStep)
        assert isinstance(result, StepSuccess)
        assert current_step.step_run is not None
        if current_step.step_run:
            assert not current_step.step_run.state.error
            assert current_step.step_run.state.result["value"] == "Hello from Iivr"
        # Run input step
        result, next_step_or_exit = engine.run_current_workflow_step(
            step_input=IntegerInput("number", 123)
        )
        assert isinstance(result, StepSuccess)
        assert isinstance(next_step_or_exit, PlayMessageStep)
        result, next_step_or_exit = engine.run_current_workflow_step()
        assert isinstance(next_step_or_exit, HangUpExitPath)
        assert workflow_run.session.get("number") == 123
