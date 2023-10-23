from uuid import uuid4

import pytest
from sqlalchemy import orm

from ivr_gateway.engines.workflows import WorkflowEngine
from ivr_gateway.exceptions import NonUpdateableModelError
from ivr_gateway.exit_paths import HangUpExitPath
from ivr_gateway.models.contacts import Contact, Greeting, InboundRouting, ContactLeg
from ivr_gateway.models.workflows import WorkflowConfig, Workflow, WorkflowRun
from ivr_gateway.steps.api.v1 import PlayMessageStep, InputActionStep
from ivr_gateway.steps.config import StepTree, StepBranch, Step
from tests.factories import workflow as wcf


class TestWorkflowConfigs:

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
                            exit_path={
                                "exit_path_type": HangUpExitPath.get_type_string(),
                            },
                        ),
                    ]
                ),
            ]
        )

    @pytest.fixture
    def workflow(self, db_session: orm.Session, step_tree: StepTree) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "workflow_config_test", step_tree=step_tree)
        return workflow_factory.create()

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
    def workflow_run(self, db_session: orm.session, workflow: Workflow) -> WorkflowRun:
        run = WorkflowRun(workflow=workflow, workflow_config=workflow.latest_config)
        db_session.add(run)
        db_session.commit()
        return run

    @pytest.fixture
    def call_leg(self, db_session, call: Contact, call_routing: InboundRouting, workflow_run: WorkflowRun) -> ContactLeg:
        call_leg = ContactLeg(
            contact=call,
            inbound_routing=call_routing,
            contact_system="test",
            contact_system_id="test",
            workflow_run=workflow_run
        )
        db_session.add(call_leg)
        db_session.commit()
        return call_leg

    def test_workflow_config_update_creates_new_revision(self, db_session: orm.Session, workflow: Workflow):
        initial_wc = workflow.latest_config
        initial_step_tree_sha = initial_wc.step_tree_sha
        wc = WorkflowConfig(workflow=workflow, step_tree=StepTree(branches=[]))
        db_session.add(wc)
        db_session.commit()
        assert wc.step_tree_sha is not None
        assert workflow.latest_config == wc
        initial_wc.step_tree = StepTree(branches=[])
        db_session.add(initial_wc)
        db_session.commit()
        assert initial_wc.step_tree_sha != initial_step_tree_sha

    def test_a_run_workflow_cannot_be_updates(self, db_session: orm.Session, workflow_run: WorkflowRun):
        workflow_config = workflow_run.workflow.latest_config
        engine = WorkflowEngine(db_session, workflow_run)
        engine.initialize()
        engine.run_current_workflow_step()
        workflow_config.step_tree = StepTree(branches=[])
        db_session.add(workflow_config)
        with pytest.raises(NonUpdateableModelError):
            db_session.commit()


