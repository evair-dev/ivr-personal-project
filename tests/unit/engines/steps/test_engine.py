from uuid import uuid4

import pytest
from sqlalchemy.orm import Session as SQLAlchemySession

from ivr_gateway.engines.steps import StepEngine, StepEngineState
from ivr_gateway.exit_paths import HangUpExitPath
from ivr_gateway.models.contacts import Contact, InboundRouting, Greeting
from ivr_gateway.models.encryption import active_encryption_key_fingerprint
from ivr_gateway.models.workflows import WorkflowRun, Workflow
from ivr_gateway.services.workflows import WorkflowService
from ivr_gateway.steps.api.v1 import PlayMessageStep
from ivr_gateway.steps.base import Step
from ivr_gateway.steps.config import StepTree, StepBranch, Step as StepTemplate
from ivr_gateway.steps.result import StepSuccess, StepError
from tests.factories.workflow import workflow_factory


class TestStepsEngine:

    @pytest.fixture
    def call(self, db_session) -> Contact:
        call = Contact(global_id=str(uuid4()))
        db_session.add(call)
        db_session.commit()
        return call

    @pytest.fixture
    def greeting(self, db_session) -> Greeting:
        greeting = Greeting(message="test greeting")
        db_session.add(greeting)
        db_session.commit()
        return greeting

    @pytest.fixture
    def workflow(self, db_session: SQLAlchemySession) -> Workflow:
        factory = workflow_factory(db_session, "main_menu", step_tree=StepTree(
            branches=[
                StepBranch(
                    name="root",
                    steps=[
                        StepTemplate(
                            name="step-1",
                            step_type=PlayMessageStep.get_type_string(),
                            step_kwargs={
                                "template": "Hi, welcome to Avant",
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
    def call_routing(self, db_session, workflow: Workflow, greeting: Greeting) -> InboundRouting:
        call_routing = InboundRouting(
            inbound_target="+15555555555",
            workflow=workflow,
            active=True,
            greeting=greeting,
            operating_mode="normal"
        )
        db_session.add(call_routing)
        db_session.commit()
        return call_routing

    @pytest.fixture
    def workflow_run(self, db_session: SQLAlchemySession, workflow: Workflow) -> WorkflowRun:
        run = WorkflowRun(workflow=workflow, workflow_config=workflow.latest_config)
        db_session.add(run)
        db_session.commit()
        return run

    @pytest.fixture
    def step(self, db_session: SQLAlchemySession, workflow_run: WorkflowRun) -> Step:
        workflow_service = WorkflowService(db_session)
        step = workflow_service.create_step_for_workflow(
            workflow_run,
            workflow_run.workflow.latest_config.branches[0].steps[0].name
        )
        workflow_run.initialize_first_step.set(step)
        db_session.add_all(workflow_run.step_runs)
        db_session.add(workflow_run)
        db_session.commit()
        return step

    def test_engine_initialization(self, db_session: SQLAlchemySession, workflow_run: WorkflowRun, step: Step):
        engine = StepEngine(db_session, workflow_run)
        assert engine.state == StepEngineState.uninitialized
        assert step.step_run is not None
        engine.initialize(step)
        assert engine.state == StepEngineState.initialized
        assert step.step_run is not None
        assert step.step_run.initialization is not None
        # State is not created yet for the object (step not run yet)
        assert step.step_run.state is None
        step_run = step.step_run
        step_state = step_run.state
        if step_state and step_run:
            assert step_run.initialization == {
                "args": (),
                "kwargs": {"template": "Hi, welcome to Avant", "fieldset": None},
                "session": {}
            }
            assert step.step_run.state.result["input"] == {}
            assert step_run.encryption_key_fingerprint == active_encryption_key_fingerprint
        result = engine.run_step()
        assert engine.state == StepEngineState.step_complete
        assert isinstance(result, StepSuccess)
        assert result.step_state is not None
        assert step.step_run is not None
        assert step.step_run.state is not None
        if step.step_run:
            assert not step.step_run.state.error
            assert step.step_run.state.result["value"] == "Hi, welcome to Avant"

    def test_running_an_uninitialized_engine_raises_exception(
            self, db_session: SQLAlchemySession, workflow_run: WorkflowRun, step: Step
    ):
        engine = StepEngine(db_session, workflow_run)
        with pytest.raises(StepError) as e:
            engine.run_step()
            exc = e.value
            assert exc.msg == "Cannot run engine that is not initialized"
            assert not exc.retryable
