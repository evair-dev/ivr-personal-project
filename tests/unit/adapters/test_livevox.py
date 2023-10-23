import pytest
from sqlalchemy.orm import Session as SQLAlchemySession

from unittest.mock import Mock
from uuid import uuid4

from ivr_gateway.adapters.livevox import LiveVoxRequestAdapter
from ivr_gateway.exit_paths import SMSExitPath
from ivr_gateway.models.contacts import Greeting, InboundRouting, Contact, ContactLeg
from ivr_gateway.models.workflows import WorkflowRun, Workflow
from ivr_gateway.steps.api.v1 import PlayMessageStep
from ivr_gateway.steps.config import StepTree, StepBranch, Step
from tests.factories.workflow import workflow_factory


_009_CHARS = "So chars."
_010_CHARS = "Ten chars."
_049_CHARS = "This is such a sentence; wow; amaze; so sentence."
_050_CHARS = "This sentence is the finest sentence ever written."
_100_CHARS = _049_CHARS + " " + _050_CHARS
_159_CHARS = _049_CHARS + " " + _049_CHARS + " " + _049_CHARS + " " + _009_CHARS
_160_CHARS = _100_CHARS + " " + _049_CHARS + " " + _009_CHARS


class TestLiveVoxRequestAdapterExitPaths:

    @pytest.fixture
    def mock_request(self):
        return Mock()

    @pytest.fixture
    def greeting(self, db_session) -> Greeting:
        greeting = Greeting(message='Hi')
        db_session.add(greeting)
        db_session.commit()
        return greeting

    @pytest.fixture
    def sms(self, db_session) -> Contact:
        sms = Contact(global_id=str(uuid4()))
        db_session.add(sms)
        db_session.commit()
        return sms


class TestNonOverwritingExitPath(TestLiveVoxRequestAdapterExitPaths):

    @pytest.fixture
    def workflow(self, db_session: SQLAlchemySession) -> Workflow:
        factory = workflow_factory(db_session, "workflow", step_tree=StepTree(
            branches=[
                StepBranch(
                    name="root",
                    steps=[
                        Step(
                            name="step-1",
                            step_type=PlayMessageStep.get_type_string(),
                            step_kwargs={
                                "template": "Hi, welcome to Avant.",
                            },
                        ),
                        Step(
                            name="step-2",
                            step_type=PlayMessageStep.get_type_string(),
                            step_kwargs={
                                "template": "Hello, welcome (again) to Avant.",
                            },
                            exit_path={
                                "exit_path_type": SMSExitPath.get_type_string(),
                                "exit_path_kwargs": {
                                    "exit_msg": "Thanks for contacting Avant.",
                                }
                            }
                        )
                    ]
                )
            ]
        ))
        return factory.create()

    @pytest.fixture
    def inbound_routing(self, test_client, db_session, workflow: Workflow, greeting: Greeting) -> InboundRouting:
        call_routing = InboundRouting(
            inbound_target="workflow_with_non_overwriting_exit_path",
            workflow=workflow,
            active=True,
            greeting=greeting,
            operating_mode="normal",
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
    def sms_leg(self, db_session, sms: Contact, inbound_routing: InboundRouting, workflow_run: WorkflowRun) -> ContactLeg:
        sms_leg = ContactLeg(
            contact=sms,
            inbound_routing=inbound_routing,
            contact_system="test",
            contact_system_id="test",
            workflow_run=workflow_run
        )
        db_session.add(sms_leg)
        db_session.commit()
        return sms_leg

    def test_non_overwriting_exit_path(self, test_client, db_session, mock_request, sms_leg):
        livevox_adapter = LiveVoxRequestAdapter("livevox", "www.livevox.com", "/api/v1/livevox", db_session)
        response_json = livevox_adapter.process_sms_leg(mock_request, sms_leg)
        assert response_json == \
               {'error': None,
                'text_array': ['Hi, welcome to Avant. Hello, welcome (again) to Avant. Thanks for contacting Avant.'],
                'finished': True}


class TestOverwritingExitPath(TestLiveVoxRequestAdapterExitPaths):

    @pytest.fixture
    def workflow(self, db_session: SQLAlchemySession) -> Workflow:
        factory = workflow_factory(db_session, "workflow", step_tree=StepTree(
            branches=[
                StepBranch(
                    name="root",
                    steps=[
                        Step(
                            name="step-1",
                            step_type=PlayMessageStep.get_type_string(),
                            step_kwargs={
                                "template": "Hi, welcome to Avant.",
                            },
                        ),
                        Step(
                            name="step-2",
                            step_type=PlayMessageStep.get_type_string(),
                            step_kwargs={
                                "template": "Hello, welcome (again) to Avant.",
                            },
                            exit_path={
                                "exit_path_type": SMSExitPath.get_type_string(),
                                "exit_path_kwargs": {
                                    "exit_msg": "Sorry! There was an issue.",
                                    "overwrite_response": True
                                }
                            }
                        )
                    ]
                )
            ]
        ))
        return factory.create()

    @pytest.fixture
    def inbound_routing(self, test_client, db_session, workflow: Workflow, greeting: Greeting) -> InboundRouting:
        call_routing = InboundRouting(
            inbound_target="workflow",
            workflow=workflow,
            active=True,
            greeting=greeting,
            operating_mode="normal",
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
    def sms_leg(self, db_session, sms: Contact, inbound_routing: InboundRouting, workflow_run: WorkflowRun) -> ContactLeg:
        sms_leg = ContactLeg(
            contact=sms,
            inbound_routing=inbound_routing,
            contact_system="test",
            contact_system_id="test",
            workflow_run=workflow_run
        )
        db_session.add(sms_leg)
        db_session.commit()
        return sms_leg

    def test_overwriting_exit_path(self, test_client, db_session, mock_request, sms_leg):
        livevox_adapter = LiveVoxRequestAdapter("livevox", "www.livevox.com", "/api/v1/livevox", db_session)
        response_json = livevox_adapter.process_sms_leg(mock_request, sms_leg)
        assert response_json == \
               {'error': None,
                'text_array': ['Sorry! There was an issue.'],
                'finished': True}


class TestUpdateTextArray:

    @pytest.mark.parametrize("existing_text_array, new_text, start_new_message, expected", [
        ([""], "Hello from Avant.", False, ["Hello from Avant."]),
        ([""], "Hello from Avant.", True, ["Hello from Avant."]),
        (["First message."], "Second message, combined.", False, ["First message. Second message, combined."]),
        (["First message."], "Second message, separate.", True, ["First message.", "Second message, separate."]),
        ([_160_CHARS], _049_CHARS, False, [_160_CHARS, _049_CHARS]),
        ([_159_CHARS], "Some words.", False, [_159_CHARS + " ", "Some words."]),
    ])
    def test_update_text_array(self, db_session, existing_text_array, start_new_message, new_text, expected):
        livevox_adapter = LiveVoxRequestAdapter("livevox", "www.livevox.com", "/api/v1/livevox", db_session)
        assert livevox_adapter.update_text_array(existing_text_array, new_text,
                                                 start_new_message=start_new_message) == expected

    def test_update_text_array_with_end_break(self, db_session):
        livevox_adapter = LiveVoxRequestAdapter("livevox", "www.livevox.com", "/api/v1/livevox", db_session)

        text_array = [_049_CHARS]
        new_text = _050_CHARS
        end_break = True
        expected_result = [_049_CHARS + " " + _050_CHARS, ""]
        assert livevox_adapter.update_text_array(text_array, new_text, end_break=end_break) == expected_result

        new_text = _010_CHARS
        expected_result = [_049_CHARS + " " + _050_CHARS, _010_CHARS]
        assert livevox_adapter.update_text_array(text_array, new_text) == expected_result
