import pytest
import time_machine
from sqlalchemy.orm import Session as SQLAlchemySession

from ivr_gateway.models.contacts import Greeting, InboundRouting
from ivr_gateway.models.queues import Queue
from ivr_gateway.models.workflows import Workflow, WorkflowRun

from tests.factories import workflow as wcf
from tests.factories import queues as qf
from tests.fixtures.step_trees.ingress import ingress_step_tree
from tests.fixtures.step_trees.main_menu import main_menu_step_tree
from step_trees.shared.ivr.banking_menu import banking_menu_step_tree
from tests.factories.helper_functions import compare_step_branches


class HandleIncomingDepositsFixtures:

    @pytest.fixture
    def workflow(self, db_session: SQLAlchemySession) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "shared.ivr.banking_menu",
                                                step_tree=banking_menu_step_tree)
        return workflow_factory.create()

    @pytest.fixture
    def ingress_workflow(self, db_session: SQLAlchemySession) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "Iivr.ingress", step_tree=ingress_step_tree)
        return workflow_factory.create()

    @pytest.fixture
    def main_menu_workflow(self, db_session: SQLAlchemySession) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "Iivr.main_menu", step_tree=main_menu_step_tree)
        return workflow_factory.create()

    @pytest.fixture
    def greeting(self, db_session) -> Greeting:
        greeting = Greeting(message='Thank you for calling <phoneme alphabet="ipa" ph="əˈvɑnt">Iivr</phoneme>.  '
                                    'Please be advised that your call will be monitored or recorded for quality and '
                                    'training purposes.')
        db_session.add(greeting)
        db_session.commit()
        return greeting

    @pytest.fixture
    def card_queue(self, db_session) -> Queue:
        queue = qf.queue_factory(db_session).create(
            name="AFC.CC.ORIG")
        return queue

    @pytest.fixture
    def loan_queue(self, db_session) -> Queue:
        queue = qf.queue_factory(db_session).create(
            name="AFC.LN.ORIG")
        return queue

    @pytest.fixture
    def bank_queue(self, db_session) -> Queue:
        queue = qf.queue_factory(db_session).create(
            name="AFC.BANK.CUS")
        return queue

    @pytest.fixture
    def card_call_routing(self, db_session, workflow: Workflow, greeting: Greeting,
                          card_queue: Queue) -> InboundRouting:
        call_routing = InboundRouting(
            inbound_target="15555555555",
            workflow=workflow,
            active=True,
            greeting=greeting,
            operating_mode="normal",
            initial_queue=card_queue
        )
        db_session.add(call_routing)
        db_session.commit()
        return call_routing

    @pytest.fixture
    def loan_call_routing(self, db_session, workflow: Workflow, greeting: Greeting,
                          loan_queue: Queue) -> InboundRouting:
        call_routing = InboundRouting(
            inbound_target="15555555555",
            workflow=workflow,
            active=True,
            greeting=greeting,
            operating_mode="normal",
            initial_queue=loan_queue
        )
        db_session.add(call_routing)
        db_session.commit()
        return call_routing

    @pytest.fixture
    def bank_call_routing(self, db_session, workflow: Workflow, greeting: Greeting,
                          bank_queue: Queue) -> InboundRouting:
        call_routing = InboundRouting(
            inbound_target="15555555555",
            workflow=workflow,
            active=True,
            greeting=greeting,
            operating_mode="normal",
            initial_queue=bank_queue
        )
        db_session.add(call_routing)
        db_session.commit()
        return call_routing


class TestHandleIncomingDeposits(HandleIncomingDepositsFixtures):

    @time_machine.travel("2020-12-29 19:00")
    def test_handle_incoming_deposit(self, db_session, bank_call_routing, test_client):
        init_form = {"CallSid": "test",
                     "To": "+15555555555",
                     "Digits": ""}

        initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
        assert initial_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Thank you for calling <'
            b'phoneme alphabet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.  Please b'
            b'e advised that your call will be monitored or recorded for quality and train'
            b'ing purposes.</Say><Gather action="/api/v1/twilio/continue" actionOnEmptyRes'
            b'ult="true" numDigits="1" timeout="6"><Say>For questions about your Deposits '
            b'Account, press 1. For questions about your <phoneme alphabet="ipa" ph="&#601'
            b';&#712;v&#593;nt">Iivr</phoneme> Card, press 2. For questions about your Lo'
            b'an, press 3. To hear this again, press 9.</Say></Gather></Response>'
        )

        banking_form = {"CallSid": "test",
                        "To": "+15555555555",
                        "Digits": "1"}

        transfer_response = test_client.post("/api/v1/twilio/continue", data=banking_form)
        assert transfer_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Dial>12345678901</Dial></Re'
            b'sponse>'
        )

        correct_branch_sequence = [
            "root",
            "transfer_to_banking_queue"
        ]
        workflow_run: WorkflowRun = db_session.query(WorkflowRun).first()
        compare_step_branches(correct_branch_sequence, workflow_run)

    @time_machine.travel("2020-12-29 19:00")
    def test_handle_incoming_deposit_repeat(self, db_session, bank_call_routing, test_client):
        init_form = {"CallSid": "test",
                     "To": "+15555555555",
                     "Digits": ""}

        initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
        assert initial_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Thank you for calling <'
            b'phoneme alphabet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.  Please b'
            b'e advised that your call will be monitored or recorded for quality and train'
            b'ing purposes.</Say><Gather action="/api/v1/twilio/continue" actionOnEmptyRes'
            b'ult="true" numDigits="1" timeout="6"><Say>For questions about your Deposits '
            b'Account, press 1. For questions about your <phoneme alphabet="ipa" ph="&#601'
            b';&#712;v&#593;nt">Iivr</phoneme> Card, press 2. For questions about your Lo'
            b'an, press 3. To hear this again, press 9.</Say></Gather></Response>'
        )

        repeat_form = {"CallSid": "test",
                       "To": "+15555555555",
                       "Digits": "9"}

        repeat_response = test_client.post("/api/v1/twilio/continue", data=repeat_form)
        assert repeat_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twil'
            b'io/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>For q'
            b'uestions about your Deposits Account, press 1. For questions about your <pho'
            b'neme alphabet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme> Card, press 2'
            b'. For questions about your Loan, press 3. To hear this again, press 9.</Say>'
            b'</Gather></Response>'
        )

    @time_machine.travel("2020-12-29 19:00")
    def test_handle_incoming_deposit_transfer(self, db_session, bank_call_routing, test_client):
        init_form = {"CallSid": "test",
                     "To": "+15555555555",
                     "Digits": ""}

        initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
        assert initial_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Thank you for calling <'
            b'phoneme alphabet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.  Please b'
            b'e advised that your call will be monitored or recorded for quality and train'
            b'ing purposes.</Say><Gather action="/api/v1/twilio/continue" actionOnEmptyRes'
            b'ult="true" numDigits="1" timeout="6"><Say>For questions about your Deposits '
            b'Account, press 1. For questions about your <phoneme alphabet="ipa" ph="&#601'
            b';&#712;v&#593;nt">Iivr</phoneme> Card, press 2. For questions about your Lo'
            b'an, press 3. To hear this again, press 9.</Say></Gather></Response>'
        )

        transfer_form = {"CallSid": "test",
                       "To": "+15555555555",
                       "Digits": "0"}

        transfer_response = test_client.post("/api/v1/twilio/continue", data=transfer_form)
        assert transfer_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Dial>12345678901</Dial></Re'
            b'sponse>'
        )

    @time_machine.travel("2020-12-29 19:00")
    def test_handle_incoming_card(self, db_session, card_call_routing, test_client, ingress_workflow,
                                  main_menu_workflow):
        init_form = {"CallSid": "test",
                     "To": "+15555555555",
                     "Digits": ""}

        initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
        assert initial_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Thank you for calling <'
            b'phoneme alphabet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.  Please b'
            b'e advised that your call will be monitored or recorded for quality and train'
            b'ing purposes.</Say><Gather action="/api/v1/twilio/continue" actionOnEmptyRes'
            b'ult="true" numDigits="1" timeout="6"><Say>For questions about your Deposits '
            b'Account, press 1. For questions about your <phoneme alphabet="ipa" ph="&#601'
            b';&#712;v&#593;nt">Iivr</phoneme> Card, press 2. For questions about your Lo'
            b'an, press 3. To hear this again, press 9.</Say></Gather></Response>'
        )

        banking_form = {"CallSid": "test",
                        "To": "+15555555555",
                        "Digits": "2"}

        transfer_response = test_client.post("/api/v1/twilio/continue", data=banking_form)
        assert transfer_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Dial>12345678901</Dial></Re'
            b'sponse>'
        )

    @time_machine.travel("2020-12-29 19:00")
    def test_handle_incoming_loan(self, db_session, loan_call_routing, test_client, ingress_workflow,
                                  main_menu_workflow):
        init_form = {"CallSid": "test",
                     "To": "+15555555555",
                     "Digits": ""}

        initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
        assert initial_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Thank you for calling <'
            b'phoneme alphabet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.  Please b'
            b'e advised that your call will be monitored or recorded for quality and train'
            b'ing purposes.</Say><Gather action="/api/v1/twilio/continue" actionOnEmptyRes'
            b'ult="true" numDigits="1" timeout="6"><Say>For questions about your Deposits '
            b'Account, press 1. For questions about your <phoneme alphabet="ipa" ph="&#601'
            b';&#712;v&#593;nt">Iivr</phoneme> Card, press 2. For questions about your Lo'
            b'an, press 3. To hear this again, press 9.</Say></Gather></Response>'
        )

        banking_form = {"CallSid": "test",
                        "To": "+15555555555",
                        "Digits": "3"}

        transfer_response = test_client.post("/api/v1/twilio/continue", data=banking_form)
        assert transfer_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Dial>12345678901</Dial></Re'
            b'sponse>'
        )

    @time_machine.travel("2020-12-29 23:00")
    def test_handle_incoming_deposit_office_closed(self, db_session, bank_call_routing, test_client):
        init_form = {"CallSid": "test",
                     "To": "+15555555555",
                     "Digits": ""}

        initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
        assert initial_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Thank you for calling <'
            b'phoneme alphabet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.  Please b'
            b'e advised that your call will be monitored or recorded for quality and train'
            b'ing purposes.</Say><Gather action="/api/v1/twilio/continue" actionOnEmptyRes'
            b'ult="true" numDigits="1" timeout="6"><Say>For questions about your Deposits '
            b'Account, press 1. For questions about your <phoneme alphabet="ipa" ph="&#601'
            b';&#712;v&#593;nt">Iivr</phoneme> Card, press 2. For questions about your Lo'
            b'an, press 3. To hear this again, press 9.</Say></Gather></Response>'
        )

        banking_form = {"CallSid": "test",
                        "To": "+15555555555",
                        "Digits": "1"}

        closed_message_response = test_client.post("/api/v1/twilio/continue", data=banking_form)
        assert closed_message_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Say><break time="500ms" /> '
            b'We are currently closed. Please try us back during our normal business hours'
            b' of 7am-10pm central time. We apologize for this inconvenience and look forw'
            b'ard to speaking with you then.</Say><Hangup /></Response>'
        )

        correct_branch_sequence = [
            "root",
            "transfer_to_banking_queue"
        ]
        workflow_run: WorkflowRun = db_session.query(WorkflowRun).first()
        compare_step_branches(correct_branch_sequence, workflow_run)
