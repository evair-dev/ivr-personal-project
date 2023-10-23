import pytest
import time_machine
from sqlalchemy import orm
from sqlalchemy.orm import Session as SQLAlchemySession

from ivr_gateway.models.contacts import Greeting, InboundRouting
from ivr_gateway.models.queues import Queue
from ivr_gateway.models.workflows import Workflow
from ivr_gateway.services.queues import QueueService

from tests.factories import workflow as wcf
from tests.factories import queues as qf
from tests.factories import call_routings as cr
from tests.fixtures.step_trees.main_menu import main_menu_step_tree


class TestMainMenuTwilio:

    @pytest.fixture
    def workflow(self, db_session: SQLAlchemySession) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "main_menu", step_tree=main_menu_step_tree)
        return workflow_factory.create()

    @pytest.fixture
    def greeting(self, db_session) -> Greeting:
        greeting = Greeting(message='hello from <phoneme alphabet="ipa" ph="əˈvɑnt">Iivr</phoneme>.')
        db_session.add(greeting)
        db_session.commit()
        return greeting

    @pytest.fixture
    def queue_service(self, db_session: orm.Session):
        return QueueService(db_session)

    @pytest.fixture
    def queue(self, db_session, queue_service: QueueService) -> Queue:
        queue = qf.queue_factory(db_session).create(
            name="test")
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

    @pytest.fixture
    def origination_queue(self, db_session, queue_service: QueueService) -> Queue:
        queue = qf.queue_factory(db_session).create(
            name="AFC.LN.ORIG",
            transfer_routings=[
                {
                    "transfer_type": "PSTN",
                    "destination": "12345678902",
                    "destination_system": "CISCO",
                }
            ])
        return queue

    @pytest.fixture
    def banking_queue(self, db_session, queue_service: QueueService) -> Queue:
        queue = qf.queue_factory(db_session).create(
            name="AFC.BANK.CUS",
            transfer_routings=[
                {
                    "transfer_type": "PSTN",
                    "destination": "12345678903",
                    "destination_system": "CISCO",
                }
            ])
        return queue

    @time_machine.travel("2020-12-29 19:00")
    def test_loan_origination_call(self, db_session, workflow, greeting, call_routing,
                                   test_client, origination_queue):
        init_form = {
            "CallSid": "test",
            "To": "+15555555555",
            "From": "+155555555556"
        }

        initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
        assert initial_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello from <phoneme alp'
            b'habet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say><Gather action='
            b'"/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="'
            b'6"><Say>For questions about an application, press 1. For questions about an '
            b'existing product, press 2. If you are calling about a lost or stolen card, p'
            b'ress 3. For general questions, press 0. To hear this again, press 9.</Say></'
            b'Gather></Response>')

        second_form = {"CallSid": "test", "Digits": "1"}
        second_response = test_client.post("/api/v1/twilio/continue", data=second_form)
        assert second_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twil'
            b'io/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>For c'
            b'redit cards, press 1. For personal loans, press 2. For deposit accounts, pr'
            b'ess 3. To hear this again, press 9.</Say></Gather></Response>'
        )

        third_form = {"CallSid": "test", "Digits": "2"}
        third_response = test_client.post("/api/v1/twilio/continue", data=third_form)

        assert third_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Dial>12345678902</Dial></Response>'
        )

    @time_machine.travel("2020-12-29 19:00")
    def test_card_customer_call(self, db_session, workflow, greeting, queue_service, call_routing, test_client):
        qf.queue_factory(db_session).create(
            name="AFC.CC.CUS",
            transfer_routings=[
                {
                    "transfer_type": "PSTN",
                    "destination": "12345678901",
                    "destination_system": "CISCO",
                }
            ])

        init_form = {
            "CallSid": "test",
            "To": "+15555555555",
            "From": "+155555555556"
        }

        initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
        assert initial_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello from <phoneme alp'
            b'habet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say><Gather action='
            b'"/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="'
            b'6"><Say>For questions about an application, press 1. For questions about an '
            b'existing product, press 2. If you are calling about a lost or stolen card, p'
            b'ress 3. For general questions, press 0. To hear this again, press 9.'
            b'</Say></Gather></Response>')

        second_form = {"CallSid": "test", "Digits": "2"}
        second_response = test_client.post("/api/v1/twilio/continue", data=second_form)
        assert second_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twil'
            b'io/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>For c'
            b'redit cards, press 1. For personal loans, press 2. For deposit accounts, pr'
            b'ess 3. To hear this again, press 9.</Say></Gather></Response>'
        )

        third_form = {"CallSid": "test", "Digits": "1"}
        third_response = test_client.post("/api/v1/twilio/continue", data=third_form)

        assert third_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Dial>12345678901</Dial></Response>'
        )

    @time_machine.travel("2020-12-29 19:00")
    def test_lost_card(self, db_session, workflow, greeting, call_routing, test_client):
        init_form = {
            "CallSid": "test",
            "To": "+15555555555",
            "From": "+155555555556"
        }

        initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
        assert initial_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello from <phoneme alp'
            b'habet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say><Gather action='
            b'"/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="'
            b'6"><Say>For questions about an application, press 1. For questions about an '
            b'existing product, press 2. If you are calling about a lost or stolen card, p'
            b'ress 3. For general questions, press 0. To hear this again, press 9.</Say></'
            b'Gather></Response>')

        second_form = {"CallSid": "test", "Digits": "3"}
        second_response = test_client.post("/api/v1/twilio/continue", data=second_form)
        assert second_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Dial>800-880-5076</Dial></Response>'
        )

    @time_machine.travel("2020-12-29 19:00")
    def test_card_call_general_questions(self, db_session, workflow, greeting, queue_service, test_client):
        card_queue = qf.queue_factory(db_session).create(
            name="AFC.CC.CUS",
            transfer_routings=[
                {
                    "transfer_type": "PSTN",
                    "destination": "12345678901",
                    "destination_system": "CISCO",
                }
            ])

        cr.inbound_routing_factory(db_session).create(
            inbound_target="15555555555",
            workflow=workflow,
            greeting=greeting,
            initial_queue=card_queue
        )

        init_form = {
            "CallSid": "test",
            "To": "+15555555555",
            "From": "+155555555556"
        }

        initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
        assert initial_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello from <phoneme alp'
            b'habet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say><Gather action='
            b'"/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="'
            b'6"><Say>For questions about an application, press 1. For questions about an '
            b'existing product, press 2. If you are calling about a lost or stolen card, p'
            b'ress 3. For general questions, press 0. To hear this again, press 9.'
            b'</Say></Gather></Response>')

        second_form = {"CallSid": "test", "Digits": "0"}
        second_response = test_client.post("/api/v1/twilio/continue", data=second_form)
        assert second_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Dial>12345678901</Dial></Response>'
        )

    @time_machine.travel("2020-12-29 19:00")
    def test_application_transfer_to_deposits(self, db_session, workflow, greeting, call_routing,
                                              test_client, banking_queue):
        init_form = {
            "CallSid": "test",
            "To": "+15555555555",
            "From": "+155555555556"
        }

        initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
        assert initial_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello from <phoneme alp'
            b'habet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say><Gather action='
            b'"/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="'
            b'6"><Say>For questions about an application, press 1. For questions about an '
            b'existing product, press 2. If you are calling about a lost or stolen card, p'
            b'ress 3. For general questions, press 0. To hear this again, press 9.</Say></'
            b'Gather></Response>')

        second_form = {"CallSid": "test", "Digits": "1"}
        second_response = test_client.post("/api/v1/twilio/continue", data=second_form)
        assert second_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twil'
            b'io/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>For c'
            b'redit cards, press 1. For personal loans, press 2. For deposit accounts, pr'
            b'ess 3. To hear this again, press 9.</Say></Gather></Response>'
        )

        third_form = {"CallSid": "test", "Digits": "3"}
        third_response = test_client.post("/api/v1/twilio/continue", data=third_form)

        assert third_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Dial>12345678903</Dial></Response>'
        )

    @time_machine.travel("2020-12-29 19:00")
    def test_existing_transfer_to_deposits(self, db_session, workflow, greeting, call_routing,
                                           test_client, banking_queue):
        init_form = {
            "CallSid": "test",
            "To": "+15555555555",
            "From": "+155555555556"
        }

        initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
        assert initial_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello from <phoneme alp'
            b'habet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say><Gather action='
            b'"/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="'
            b'6"><Say>For questions about an application, press 1. For questions about an '
            b'existing product, press 2. If you are calling about a lost or stolen card, p'
            b'ress 3. For general questions, press 0. To hear this again, press 9.</Say></'
            b'Gather></Response>')

        second_form = {"CallSid": "test", "Digits": "2"}
        second_response = test_client.post("/api/v1/twilio/continue", data=second_form)
        assert second_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twil'
            b'io/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>For c'
            b'redit cards, press 1. For personal loans, press 2. For deposit accounts, pr'
            b'ess 3. To hear this again, press 9.</Say></Gather></Response>'
        )

        third_form = {"CallSid": "test", "Digits": "3"}
        third_response = test_client.post("/api/v1/twilio/continue", data=third_form)

        assert third_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Dial>12345678903</Dial></Response>'
        )