from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session as SQLAlchemySession
from twilio.twiml.voice_response import VoiceResponse

from ivr_gateway.adapters.twilio import TwilioRequestAdapter, nest_say_in_response
from ivr_gateway.exit_paths import HangUpExitPath
from ivr_gateway.models.contacts import Greeting, InboundRouting, ContactLeg, Contact
from ivr_gateway.models.workflows import Workflow, WorkflowRun
from ivr_gateway.steps.api.v1 import InputStep, PlayMessageStep
from ivr_gateway.steps.config import StepTree, StepBranch, Step
from ivr_gateway.api.exceptions import MissingInboundRoutingException
from tests.factories import workflow as wcf


class TestTwilioAdapter:

    @pytest.fixture
    def mock_request(self):
        mock = Mock()
        mock.form = {"CallSid": "test",
                     "To": "+15555555555"}
        mock.url = "ivr-gateway.test.global.Iivr.com/api/v1/twilio/new"
        mock.headers = {"X-Twilio-Signature": "incorrect"}
        return mock

    @pytest.fixture
    def call(self, db_session) -> Contact:
        call = Contact(global_id=str(uuid4()))
        db_session.add(call)
        db_session.commit()
        return call

    @pytest.fixture
    def workflow(self, db_session: SQLAlchemySession) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "main_menu", step_tree=StepTree(
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
                            step_type=InputStep.get_type_string(),
                            step_kwargs={
                                "name": "enter_number",
                                "input_key": "number",
                                "input_prompt": "Please enter a number and then press pound",
                            },
                        ),
                        Step(
                            name="step-3",
                            step_type=PlayMessageStep.get_type_string(),
                            step_kwargs={
                                "template": "You input the folowing value, {{ step_2_input }}. That was a good number. Goodbye.",
                                "fieldset": [
                                    ("step[root:step-2].result.step_input", "step_2_input")
                                ]
                            },
                            exit_path={
                                "exit_path_type": HangUpExitPath.get_type_string(),
                            },
                        ),
                    ]
                )

            ]
        ))
        return workflow_factory.create()

    @pytest.fixture
    def greeting(self, db_session) -> Greeting:
        greeting = Greeting(message="test greeting")
        db_session.add(greeting)
        db_session.commit()
        return greeting

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



    @pytest.fixture
    def twilio_adapter(self, db_session) -> TwilioRequestAdapter:
        return TwilioRequestAdapter("twilio", "www.twilio.com", "/api/v1/twilio", db_session)

    def test_process_new_call(self, call_leg, call_routing, mock_request, twilio_adapter, workflow_run):
        response = twilio_adapter.process_new_call(call_leg, call_routing, mock_request)
        assert str(response) == '<?xml version="1.0" encoding="UTF-8"?><Response><Say>test greeting</Say><Say>Hello from Iivr</Say><Gather action="/api/v1/twilio/continue" actionOnEmptyResult="true" timeout="6"><Say>Please enter a number and then press pound</Say></Gather></Response>'

    def test_call_id(self, db_session, mock_request, twilio_adapter):
        assert twilio_adapter.get_call_id(mock_request) == "test"

    def test_nest_say(self, db_session, mock_request, twilio_adapter):
        response = VoiceResponse()
        nest_say_in_response(response, "hello")
        assert str(response) == '<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello</Say></Response>'

    def test_verify_call_specific_account_auth(self, monkeypatch, twilio_adapter):
        monkeypatch.setenv("TELEPHONY_AUTHENTICATION_REQUIRED", "true")
        monkeypatch.setenv("TWILIO_test_AUTH_TOKEN", "test_token")
        call_form = {"CallSid": "test1",
                     "From": "+11235813213",
                     "To": "+15555555555",
                     "Digits": "1234",
                     "AccountSid": "test"}
        mock_request = Mock()
        mock_request.form = call_form
        mock_request.url = "https://www.test.com"
        mock_request.headers = {"X-Twilio-Signature": "E5/FsVTkfSaBayWrALCsF+7BPR8="}
        twilio_adapter.verify_call_auth(mock_request)  # throws an error if invalid
        assert True

    def test_verify_call_no_account_auth(self, monkeypatch, twilio_adapter):
        monkeypatch.setenv("TELEPHONY_AUTHENTICATION_REQUIRED", "true")
        monkeypatch.setenv("TWILIO_AUTH_TOKEN", "test_token")
        call_form = {"CallSid": "test1",
                     "From": "+11235813213",
                     "To": "+15555555555",
                     "Digits": "1234",
                     "AccountSid": "test"}
        mock_request = Mock()
        mock_request.form = call_form
        mock_request.url = "https://www.test.com"
        mock_request.headers = {"X-Twilio-Signature": "E5/FsVTkfSaBayWrALCsF+7BPR8="}
        twilio_adapter.verify_call_auth(mock_request)  # throws an error if invalid
        assert True

    def test_missing_call_routing_error(self, mock_request, twilio_adapter):
        with pytest.raises(MissingInboundRoutingException) as err:
            twilio_adapter.new_call(mock_request)
        assert err.value.status_code == 404
