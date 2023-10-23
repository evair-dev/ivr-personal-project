import pytest
from sqlalchemy.orm import Session as SQLAlchemySession

from ivr_gateway.exit_paths import HangUpExitPath, WorkflowExitPath
from ivr_gateway.models.contacts import Greeting, InboundRouting, ContactLeg
from ivr_gateway.models.workflows import Workflow
from ivr_gateway.services.calls import CallService
from ivr_gateway.steps.api.v1 import InputStep, PlayMessageStep
from ivr_gateway.steps.config import StepTree, StepBranch, Step
from tests.factories import workflow as wcf


class TestTwilio:

    @pytest.fixture
    def second_workflow(self, db_session: SQLAlchemySession) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "second_workflow", step_tree=StepTree(
            branches=[
                StepBranch(
                    name="root",
                    steps=[
                        Step(
                            name="step-1",
                            step_type=InputStep.get_type_string(),
                            step_kwargs={
                                "name": "enter_number",
                                "input_key": "number",
                                "input_prompt": "Enter a number again, Please enter a number and then press pound",
                            },
                        ),
                        Step(
                            name="step-2",
                            step_type=PlayMessageStep.get_type_string(),
                            step_kwargs={
                                "template": "You input the following value, {{ step_1_input }}. That was a terrible number. Goodbye.",
                                "fieldset": [
                                    ("step[root:step-1].input.value", "step_1_input")
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
        workflow = workflow_factory.create()
        return workflow

    @pytest.fixture
    def workflow(self, db_session: SQLAlchemySession, second_workflow: Workflow) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "main_menu", step_tree=StepTree(
            branches=[
                StepBranch(
                    name="root",
                    steps=[
                        Step(
                            name="step-1",
                            step_type=InputStep.get_type_string(),
                            step_kwargs={
                                "name": "enter_number",
                                "input_key": "number",
                                "input_prompt": "Please enter a number and then press pound",
                            },
                        ),
                        Step(
                            name="step-2",
                            step_type=PlayMessageStep.get_type_string(),
                            step_kwargs={
                                "template": "You input the following value, {{ step_1_input }}. That was a good number. Try again.",
                                "fieldset": [
                                    ("step[root:step-1].input.value", "step_1_input")
                                ]
                            },
                            exit_path={
                                "exit_path_type": WorkflowExitPath.get_type_string(),
                                "exit_path_kwargs": {
                                    "workflow": "second_workflow"
                                }
                            },
                        ),
                    ]
                )

            ]
        ))
        return workflow_factory.create()

    @pytest.fixture
    def greeting(self, db_session) -> Greeting:
        greeting = Greeting(message='hello from <phoneme alphabet="ipa" ph="əˈvɑnt">Iivr</phoneme>.')
        db_session.add(greeting)
        db_session.commit()
        return greeting

    @pytest.fixture
    def call_routing(self, db_session, workflow: Workflow, greeting: Greeting) -> InboundRouting:
        call_routing = InboundRouting(
            inbound_target="15555555555",
            workflow=workflow,
            active=True,
            greeting=greeting,
            operating_mode="normal"
        )
        db_session.add(call_routing)
        db_session.commit()
        return call_routing

    def test_new_call(self, db_session, second_workflow, workflow, greeting, call_routing, test_client):
        form = {"CallSid": "test",
                "To": "+15555555555",
                "Digits": "1234"}
        call_service = CallService(db_session)
        initial_response = test_client.post("/api/v1/twilio/new", data=form)
        assert initial_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello from <phoneme alp' \
                                        b'habet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say><Gather action=' \
                                        b'"/api/v1/twilio/continue" actionOnEmptyResult="true" timeout="6"><Say>Please enter a number and then press p' \
                                        b'ound</Say></Gather></Response>'
        first_call_leg_id = call_service.get_active_call_leg_for_call_system_and_id("twilio", "test").id
        second_response = test_client.post("/api/v1/twilio/continue", data=form)
        assert second_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You input the following ' \
                                       b'value, 1234. That was a good number. Try again.</Say><Gather action="/api/v1/twili' \
                                       b'o/continue" actionOnEmptyResult="true" timeout="6"><Say>Enter a number again, Please enter a number a' \
                                       b'nd then press pound</Say></Gather></Response>'
        second_call_leg_id = call_service.get_active_call_leg_for_call_system_and_id("twilio", "test").id
        first_call_leg = db_session.query(ContactLeg).filter(ContactLeg.id == first_call_leg_id).first()
        assert first_call_leg.disposition_type == WorkflowExitPath.get_type_string()
        assert first_call_leg.disposition_kwargs == {"workflow": "second_workflow"}
        third_response = test_client.post("/api/v1/twilio/continue", data=form)
        assert third_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You input the following' \
                                      b' value, 1234. That was a terrible number. Goodbye.</Say><Hangup /></Response' \
                                      b'>'
        second_call_leg = db_session.query(ContactLeg).filter(ContactLeg.id == second_call_leg_id).first()
        assert second_call_leg.disposition_type == HangUpExitPath.get_type_string()
        assert second_call_leg.disposition_kwargs == {}
