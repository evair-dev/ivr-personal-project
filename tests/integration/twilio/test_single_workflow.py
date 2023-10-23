import pytest
from sqlalchemy.orm import Session as SQLAlchemySession

from ivr_gateway.exit_paths import HangUpExitPath
from ivr_gateway.models.contacts import Greeting, InboundRouting, Contact, ContactLeg
from ivr_gateway.models.steps import StepRun
from ivr_gateway.models.workflows import Workflow, WorkflowRun
from ivr_gateway.steps.api.v1 import InputStep, PlayMessageStep
from ivr_gateway.steps.config import StepTree, StepBranch, Step
from tests.factories import workflow as wcf


class TestTwilio:

    @pytest.fixture
    def workflow(self, db_session: SQLAlchemySession) -> Workflow:
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
                                "template": "You input the following value, {{ session.number }}. That was a good number. Goodbye.",
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

    def test_new_call(self, db_session, workflow, greeting, call_routing, test_client):
        form = {"CallSid": "test",
                "To": "+15555555555",
                "Digits": "1234"}
        initial_response = test_client.post("/api/v1/twilio/new", data=form)
        assert initial_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello from <phoneme alp' \
                                        b'habet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say><Gather action=' \
                                        b'"/api/v1/twilio/continue" actionOnEmptyResult="true" timeout="6"><Say>Please enter a number and then press p' \
                                        b'ound</Say></Gather></Response>'
        call: Contact = db_session.query(Contact).first()
        # Encryption tests to be removed after migration
        assert call.encryption_key_fingerprint is not None
        assert len(call.contact_legs) == 1
        cl: ContactLeg = call.contact_legs[0]
        wr: WorkflowRun = cl.workflow_run
        wr_id = wr.id
        assert wr.step_run_count == 1
        second_response = test_client.post("/api/v1/twilio/continue", data=form)
        assert second_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You input the following' \
                                       b' value, 1234. That was a good number. Goodbye.</Say><Hangup /></Response>'
        # Encryption tests to be removed after migration
        wr = db_session.query(WorkflowRun).filter(WorkflowRun.id == wr_id).first()
        call: Contact = db_session.query(Contact).first()
        assert wr.step_run_count == 2
        sr: StepRun = wr.step_runs[0]
        assert sr.state.input["value"] == "1234" and \
               sr.state.encryption_key_fingerprint is not None
        assert wr.exit_path_type == HangUpExitPath.get_type_string()
        assert wr.exit_path_kwargs == {}
        assert cl.disposition_type == HangUpExitPath.get_type_string()
        assert cl.disposition_kwargs == {}
