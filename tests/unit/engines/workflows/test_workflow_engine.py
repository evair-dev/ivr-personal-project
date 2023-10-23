from unittest.mock import patch, Mock

import pytest
from sqlalchemy.orm import Session as SQLAlchemySession

from ivr_gateway.engines.steps import StepEngine
from ivr_gateway.engines.workflows import WorkflowEngine, WorkflowEngineState, WorkflowEngineUnrecoverableException, \
    WorkflowEngineInvalidStateException
from ivr_gateway.exit_paths import HangUpExitPath
from ivr_gateway.models.enums import WorkflowState
from ivr_gateway.models.workflows import WorkflowRun, Workflow
from ivr_gateway.steps.api.v1 import PlayMessageStep, InputActionStep
from ivr_gateway.steps.config import StepTree, StepBranch, Step
from ivr_gateway.steps.inputs import MenuActionInput
from ivr_gateway.steps.result import StepSuccess, StepError
from tests.factories.workflow import workflow_factory


class TestWorkflowEngine:

    @pytest.fixture
    def workflow(self, db_session: SQLAlchemySession) -> Workflow:
        factory = workflow_factory(db_session, "main_menu", step_tree=StepTree(
            branches=[
                StepBranch(
                    name="root",
                    steps=[
                        Step(
                            name="step-1",
                            step_type=PlayMessageStep.get_type_string(),
                            step_kwargs={
                                "template": "Hi, welcome to Avant",
                            },
                        ),
                        Step(
                            name="step-2",
                            step_type=InputActionStep.get_type_string(),
                            step_kwargs={
                                "name": "enter_number",
                                "actions": [{
                                    "name": "opt-1",
                                    "display_name": "Option 1"
                                }, {
                                    "name": "opt-2",
                                    "display_name": "Option 2"
                                }],
                                "input_key": "number",
                                "input_prompt": "Please enter a number",
                            },
                            exit_path={
                                "exit_path_type": HangUpExitPath.get_type_string(),
                            }
                        )
                    ]
                )
            ]
        ))
        return factory.create()

    @pytest.fixture
    def workflow_run(self, db_session: SQLAlchemySession, workflow: Workflow) -> WorkflowRun:
        run = WorkflowRun(workflow=workflow, workflow_config=workflow.latest_config)
        db_session.add(run)
        db_session.commit()
        return run

    def test_workflow_engine_initialization(self, db_session: SQLAlchemySession, workflow: Workflow,
                                            workflow_run):
        engine = WorkflowEngine(db_session, workflow_run)
        assert engine.state == WorkflowEngineState.uninitialized
        assert workflow_run.state == WorkflowState.uninitialized
        engine.initialize()
        assert engine.state == WorkflowEngineState.initialized
        assert workflow_run.state == WorkflowState.initialized
        assert workflow_run.session == {}
        assert workflow_run.step_runs.count() == 1
        fsm = db_session.query(WorkflowRun).filter(WorkflowRun.id == workflow_run.id).first()
        assert fsm.state == WorkflowState.initialized

    def test_workflow_engine_run_step(self, db_session: SQLAlchemySession,
                                      workflow: Workflow, workflow_run: WorkflowRun):
        engine = WorkflowEngine(db_session, workflow_run)
        engine.initialize()
        # Run the first step
        current_step_run = engine.workflow_run.get_current_step_run()
        result, next_step_or_exit = engine.run_current_workflow_step()
        assert engine.state == WorkflowEngineState.step_in_progress
        assert engine.workflow_run.state == WorkflowState.requesting_user_input
        # Make sure the step's state is created
        assert current_step_run is not None
        if current_step_run:
            assert not current_step_run.state.error
            assert current_step_run.state.result["value"] == "Hi, welcome to Avant"
        assert isinstance(next_step_or_exit, InputActionStep)
        # Run input step
        result, next_step_or_exit = engine.run_current_workflow_step(
            step_input=MenuActionInput("number", 1, menu_actions=next_step_or_exit.actions)
        )
        assert workflow_run.state == WorkflowState.finished
        assert isinstance(result, StepSuccess)
        assert isinstance(next_step_or_exit, HangUpExitPath)
        assert workflow_run.exit_path_type == HangUpExitPath.get_type_string()
        assert workflow_run.exit_path_kwargs == {}

    def test_workflow_engine_reinitialize_workflow_and_run_step(self, db_session: SQLAlchemySession,
                                                                workflow: Workflow, workflow_run):
        engine = WorkflowEngine(db_session, workflow_run)
        engine.initialize()
        # Run the first step
        engine.run_current_workflow_step()
        # Now Reinitialize
        new_engine = WorkflowEngine(db_session, workflow_run)
        new_engine.initialize()
        rehydrated_step = new_engine.get_current_step()
        assert isinstance(rehydrated_step, InputActionStep)
        assert len(rehydrated_step.actions) == 2
        # Run input step
        result, next_step_or_exit = engine.run_current_workflow_step(
            step_input=MenuActionInput("number", "1", menu_actions=rehydrated_step.actions)
        )
        assert workflow_run.state == WorkflowState.finished
        assert isinstance(result, StepSuccess)
        assert isinstance(next_step_or_exit, HangUpExitPath)

    @patch.object(StepEngine, "run_step")
    def test_workflow_engine_correctly_handles_a_step_error(self, mock_run_step,
                                                            db_session: SQLAlchemySession,
                                                            workflow: Workflow, workflow_run):
        mock_run_step.side_effect = StepError(msg="A retryable step error occurred", retryable=True)

        engine = WorkflowEngine(db_session, workflow_run)

        can_retry_mock = Mock()
        can_retry_mock.return_value = True
        engine.can_current_step_retry = can_retry_mock

        engine.initialize()
        # Run the first step
        result, next_step_or_exit = engine.run_current_workflow_step()

        assert isinstance(result, StepError)
        assert engine.state == WorkflowEngineState.step_in_progress
        assert workflow_run.state == WorkflowState.step_in_progress

    @patch.object(StepEngine, "run_step")
    @patch.object(StepEngine, "get_step_error_message")
    def test_workflow_engine_correctly_handles_a_non_retryable_step_error(self, mock_get_step_error_message,
                                                                          mock_run_step,
                                                                          db_session: SQLAlchemySession,
                                                                          workflow: Workflow,
                                                                          workflow_run: WorkflowRun):
        error_message = "A non-retryable step error occurred"
        mock_run_step.side_effect = StepError(msg=error_message, retryable=False)
        mock_get_step_error_message.return_value = error_message
        engine = WorkflowEngine(db_session, workflow_run)

        engine.initialize()
        # Run the first step
        with pytest.raises(WorkflowEngineUnrecoverableException):
            engine.run_current_workflow_step()
        assert engine.state == WorkflowEngineState.error
        assert workflow_run.state == WorkflowState.error

    @patch.object(StepEngine, "run_step")
    @patch.object(StepEngine, "get_step_error_message")
    def test_workflow_engine_correctly_handles_the_can_retry_ask(self, mock_get_step_error_message,
                                                                 mock_run_step,
                                                                 db_session: SQLAlchemySession,
                                                                 workflow: Workflow,
                                                                 workflow_run: WorkflowRun):
        error_message = "A non-retryable step error occurred"
        mock_run_step.side_effect = StepError(msg=error_message, retryable=False)
        mock_get_step_error_message.return_value = error_message
        engine = WorkflowEngine(db_session, workflow_run)
        engine.initialize()
        # Run the first step
        with pytest.raises(WorkflowEngineUnrecoverableException):
            engine.run_current_workflow_step()
        assert engine.state == WorkflowEngineState.error
        assert workflow_run.state == WorkflowState.error
        # Now try resetting the engine for the retryable state
        # Mock out the retry call because we mocked out the step run
        can_retry_mock = Mock()
        can_retry_mock.return_value = True
        engine.step_engine.can_current_step_retry = can_retry_mock
        assert engine.can_current_step_retry()
        can_retry_mock = Mock()
        can_retry_mock.return_value = False
        engine.step_engine.can_current_step_retry = can_retry_mock
        assert not engine.can_current_step_retry()

    def test_workflow_engine_throws_uninitialized_exception_on_can_retry_method_when_uninitialized(
            self, db_session: SQLAlchemySession, workflow: Workflow, workflow_run: WorkflowRun
    ):
        engine = WorkflowEngine(db_session, workflow_run)
        with pytest.raises(WorkflowEngineInvalidStateException):
            engine.can_current_step_retry()

    def test_workflow_engine_can_retry_method_returns_correct_information(
            self, db_session: SQLAlchemySession, workflow: Workflow, workflow_run: WorkflowRun
    ):
        engine = WorkflowEngine(db_session, workflow_run)
        engine.initialize()
        assert engine.can_current_step_retry()
        engine.run_current_workflow_step()
        assert engine.can_current_step_retry()

    def test_workflow_engine_can_retry_input_step(
            self, db_session: SQLAlchemySession, workflow: Workflow, workflow_run: WorkflowRun
    ):
        engine = WorkflowEngine(db_session, workflow_run)
        engine.initialize()
        # Run first step to put on input step
        engine.run_current_workflow_step()
        # Now mock out the engine run_step
        mock_run_step = Mock()
        mock_run_step.side_effect = StepError(msg="A retryable step error occurred", retryable=True)
        engine.step_engine.run_step = mock_run_step
        result, next_step_or_exit = engine.run_current_workflow_step()
        assert isinstance(result, StepError)
        # Now try resetting the engine for the retryable state
        # Mock out the retry call because we mocked out the step run
        assert engine.state == WorkflowEngineState.step_in_progress
        assert workflow_run.state == WorkflowState.requesting_user_input

    def test_workflow_in_error_state_initialized_engine_to_error_state(
            self, db_session: SQLAlchemySession, workflow: Workflow, workflow_run: WorkflowRun
    ):
        # Initialize the workflow run
        engine = WorkflowEngine(db_session, workflow_run)
        engine.initialize()
        # Manually put the workflow into error
        workflow_run.state = WorkflowState.error
        db_session.add(workflow_run)
        db_session.commit()
        # Construct a new engine
        engine2 = WorkflowEngine(db_session, workflow_run)
        engine2.initialize()
        assert engine2.state == WorkflowEngineState.error
