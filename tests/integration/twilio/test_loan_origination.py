from unittest.mock import patch

import pytest
import time_machine
from sqlalchemy.orm import Session as SQLAlchemySession

from ivr_gateway.models.contacts import Greeting, InboundRouting
from ivr_gateway.models.queues import Queue
from ivr_gateway.models.workflows import Workflow
from tests.factories import queues as qf
from ivr_gateway.services.workflows.fields import CustomerLookupFieldLookupService

from tests.factories import workflow as wcf
from tests.fixtures.step_trees.loan_origination import loan_origination_step_tree


class TestLoanOriginationTwilio:

    @pytest.fixture
    def workflow(self, db_session: SQLAlchemySession) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "loan_origination", step_tree=loan_origination_step_tree)
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
            name="test")
        return queue

    @pytest.fixture
    def origination_queue(self, db_session) -> Queue:
        queue = qf.queue_factory(db_session).create(
            name="AFC.LN.ORIG",
            transfer_routings=[{
                "transfer_type": "PSTN",
                "destination": "12345678902",
                "destination_system": "CISCO"
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
    def test_no_input(self, db_session, workflow, origination_queue,
                      greeting, call_routing, test_client):
        with patch.object(CustomerLookupFieldLookupService, "get_field_by_lookup_key", return_value=71568378):
            init_form = {"CallSid": "test",
                         "To": "+15555555555",
                         "From": "+155555555556",
                         "Digits": ""}

            initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
            assert initial_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello from <phoneme alp'
                b'habet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say><Say>Please be '
                b'sure to check your email and customer dashboard at W W W dot <phoneme alphab'
                b'et="ipa" ph="&#601;&#712;v&#593;nt">Avant</phoneme> dot com for updates on y'
                b'our application status. To speak with a specialist regarding your account, p'
                b'ress 0.</Say><Gather action="/api/v1/twilio/continue" actionOnEmptyResult="t'
                b'rue" numDigits="1" timeout="6"><Say> </Say></Gather></Response>')

            second_response = test_client.post("/api/v1/twilio/continue", data=init_form)
            assert second_response.data == (b'<?xml version="1.0" encoding="UTF-8"?><Response><Hangup /></Response>')

    @time_machine.travel("2020-12-29 19:00")
    def test_no_digits_input(self, db_session, workflow, origination_queue,
                             greeting, call_routing, test_client):
        with patch.object(CustomerLookupFieldLookupService, "get_field_by_lookup_key", return_value=71568378):
            init_form = {"CallSid": "test",
                         "To": "+15555555555",
                         "From": "+155555555556"}

            initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
            assert initial_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello from <phoneme alp'
                b'habet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say><Say>Please be '
                b'sure to check your email and customer dashboard at W W W dot <phoneme alphab'
                b'et="ipa" ph="&#601;&#712;v&#593;nt">Avant</phoneme> dot com for updates on y'
                b'our application status. To speak with a specialist regarding your account, p'
                b'ress 0.</Say><Gather action="/api/v1/twilio/continue" actionOnEmptyResult="t'
                b'rue" numDigits="1" timeout="6"><Say> </Say></Gather></Response>')

            second_response = test_client.post("/api/v1/twilio/continue", data=init_form)
            assert second_response.data == (b'<?xml version="1.0" encoding="UTF-8"?><Response><Hangup /></Response>')

    @time_machine.travel("2020-12-29 19:00")
    def test_wrong_key_input(self, db_session, workflow, origination_queue,
                             greeting, call_routing, test_client):
        with patch.object(CustomerLookupFieldLookupService, "get_field_by_lookup_key", return_value=71568378):
            init_form = {"CallSid": "test",
                         "To": "+15555555555",
                         "From": "+155555555556",
                         "Digits": "2"}

            initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
            assert initial_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello from <phoneme alp'
                b'habet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say><Say>Please be '
                b'sure to check your email and customer dashboard at W W W dot <phoneme alphab'
                b'et="ipa" ph="&#601;&#712;v&#593;nt">Avant</phoneme> dot com for updates on y'
                b'our application status. To speak with a specialist regarding your account, p'
                b'ress 0.</Say><Gather action="/api/v1/twilio/continue" actionOnEmptyResult="t'
                b'rue" numDigits="1" timeout="6"><Say> </Say></Gather></Response>')

            second_response = test_client.post("/api/v1/twilio/continue", data=init_form)
            assert second_response.data == (b'<?xml version="1.0" encoding="UTF-8"?><Response><Hangup /></Response>')

    @time_machine.travel("2020-12-29 19:00")
    def test_new_call(self, db_session, workflow, greeting, call_routing, test_client, origination_queue):
        with patch.object(CustomerLookupFieldLookupService, "get_field_by_lookup_key", return_value=71568378):
            init_form = {"CallSid": "test",
                         "To": "+15555555555",
                         "From": "+155555555556",
                         "Digits": "1"}

            initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
            assert initial_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello from <phoneme alp'
                b'habet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say><Say>Please be '
                b'sure to check your email and customer dashboard at W W W dot <phoneme alphab'
                b'et="ipa" ph="&#601;&#712;v&#593;nt">Avant</phoneme> dot com for updates on y'
                b'our application status. To speak with a specialist regarding your account, p'
                b'ress 0.</Say><Gather action="/api/v1/twilio/continue" actionOnEmptyResult="t'
                b'rue" numDigits="1" timeout="6"><Say> </Say></Gather></Response>')

            second_response = test_client.post("/api/v1/twilio/continue", data=init_form)
            assert second_response.data == (
                # b'<?xml version="1.0" encoding="UTF-8"?><Response><Dial>12345678902</Dial></Response>')
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Dial>12345678902</Dial></Response>'
            )
