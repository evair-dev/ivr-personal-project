import datetime

import pytest
import time_machine
from sqlalchemy.orm import Session as SQLAlchemySession

from ivr_gateway.exit_paths import CurrentQueueExitPath
from ivr_gateway.models.contacts import Greeting, InboundRouting, Contact, ContactLeg
from ivr_gateway.models.queues import Queue
from ivr_gateway.models.workflows import Workflow
from tests.factories import queues as qf
from ivr_gateway.steps.api.v1 import InputStep, PlayMessageStep
from ivr_gateway.steps.config import StepTree, StepBranch, Step
from tests.factories import workflow as wcf


class TestTwilioEnqueue:

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
                                "exit_path_type": CurrentQueueExitPath.get_type_string(),
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
    def queue(self, db_session) -> Queue:
        queue = qf.queue_factory(db_session).create(
            name="test",
            transfer_routings=[{
                "transfer_type": "INTERNAL",
                "destination": "WW12345678901",
                "destination_system": "twilio"
            }]
        )
        return queue

    @pytest.fixture
    def call_routing(self, db_session, workflow: Workflow, greeting: Greeting, queue: Queue) -> InboundRouting:
        call_routing = InboundRouting(
            inbound_target="15555555555",
            workflow=workflow,
            active=True,
            greeting=greeting,
            operating_mode="normal",
            initial_queue=queue
        )
        db_session.add(call_routing)
        db_session.commit()
        return call_routing


    @time_machine.travel("2020-12-29 19:00")
    def test_unknown_customer_call(self, db_session, workflow, greeting, call_routing, test_client):
        form = {"CallSid": "test",
                "To": "+15555555555",
                "Digits": "1234"}
        initial_response = test_client.post("/api/v1/twilio/new", data=form)
        assert initial_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello from <phoneme alp' \
                                        b'habet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say><Gather action=' \
                                        b'"/api/v1/twilio/continue" actionOnEmptyResult="true" timeout="6"><Say>Please enter a number and then press p' \
                                        b'ound</Say></Gather></Response>'

        call: Contact = db_session.query(Contact).first()
        call.device_identifier = '19999999999'
        db_session.commit()

        second_response = test_client.post("/api/v1/twilio/continue", data=form)
        assert second_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You input the following value, 1234. That was a '
            b'good number. Goodbye.</Say><Enqueue workflowSid="WW12345678901"><Task>{"customers": {'
            b'"customer_label_1": null}, "secure_key": null, "queue_name": "test", "screenpop": '
            b'"https://csp.amount.com/us", "type": "inbound", "name": "+19999999999"}</Task></Enqueue></Response>')
        call_leg = db_session.query(ContactLeg).order_by(ContactLeg.end_time.desc()).first()
        assert call_leg.disposition_type == "ivr_gateway.exit_paths.CurrentQueueExitPath"
        assert call_leg.disposition_kwargs == {"operating_mode": "normal"}

    @time_machine.travel("2020-12-29 19:00")
    def test_known_customer_call(self, db_session, workflow, greeting, call_routing, test_client):
        form = {"CallSid": "test",
                "To": "+15555555555",
                "Digits": "1234"}
        initial_response = test_client.post("/api/v1/twilio/new", data=form)
        assert initial_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello from <phoneme alp' \
                                        b'habet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say><Gather action=' \
                                        b'"/api/v1/twilio/continue" actionOnEmptyResult="true" timeout="6"><Say>Please enter a number and then press p' \
                                        b'ound</Say></Gather></Response>'
        call: Contact = db_session.query(Contact).first()
        call.customer_id = 'test_user'
        call.device_identifier = '19999999999'
        db_session.commit()

        second_response = test_client.post("/api/v1/twilio/continue", data=form)
        assert second_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You input the following value, 1234. That was a '
            b'good number. Goodbye.</Say><Enqueue workflowSid="WW12345678901"><Task>{"customers": {'
            b'"customer_label_1": "test_user"}, "secure_key": null, "queue_name": "test", "screenpop": '
            b'"https://csp.amount.com/us/customers/test_user/customer_details", "type": "inbound", '
            b'"name": "+19999999999"}</Task></Enqueue></Response>')
        call_leg = db_session.query(ContactLeg).order_by(ContactLeg.end_time.desc()).first()
        assert call_leg.disposition_type == "ivr_gateway.exit_paths.CurrentQueueExitPath"
        assert call_leg.disposition_kwargs == {"operating_mode": "normal"}

    @time_machine.travel("2020-12-29 19:00")
    def test_secured_customer_call(self, db_session, workflow, greeting, call_routing, test_client):
        form = {"CallSid": "test",
                "To": "+15555555555",
                "Digits": "1234"}
        initial_response = test_client.post("/api/v1/twilio/new", data=form)
        assert initial_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello from <phoneme alp' \
                                        b'habet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say><Gather action=' \
                                        b'"/api/v1/twilio/continue" actionOnEmptyResult="true" timeout="6"><Say>Please enter a number and then press p' \
                                        b'ound</Say></Gather></Response>'
        call: Contact = db_session.query(Contact).first()

        call.customer_id = 'test_user'
        call.secured = datetime.datetime.now()
        call.secured_key = 'test_key'
        call.device_identifier = '19999999999'
        db_session.commit()

        second_response = test_client.post("/api/v1/twilio/continue", data=form)
        assert second_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You input the following value, 1234. That was a '
            b'good number. Goodbye.</Say><Enqueue workflowSid="WW12345678901"><Task>{"customers": {'
            b'"customer_label_1": "test_user"}, "secure_key": "test_key", "queue_name": "test", "screenpop": '
            b'"https://csp.amount.com/us/customers/test_user/workflow/secure_call?key=test_key", "type": "inbound", '
            b'"name": "+19999999999"}</Task></Enqueue></Response>')
        call_leg = db_session.query(ContactLeg).order_by(ContactLeg.end_time.desc()).first()
        assert call_leg.disposition_type == "ivr_gateway.exit_paths.CurrentQueueExitPath"
        assert call_leg.disposition_kwargs == {"operating_mode": "normal"}
