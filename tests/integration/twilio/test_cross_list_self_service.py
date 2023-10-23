from unittest.mock import Mock, patch

import pytest
import requests
import time_machine
from sqlalchemy.orm import Session as SQLAlchemySession

from ivr_gateway.models.contacts import Greeting, InboundRouting
from ivr_gateway.models.queues import Queue
from ivr_gateway.models.workflows import Workflow
from tests.factories import queues as qf

from tests.factories import workflow as wcf
from tests.fixtures.step_trees.customer_lookup_self_service_wrapper import \
    customer_lookup_self_service_wrapper_step_tree
from tests.fixtures.step_trees.make_payment import make_payment_step_tree
from tests.fixtures.step_trees.self_service_menu import self_service_step_tree


class TestCrossListSelfServiceTwilio:

    @pytest.fixture
    def workflow(self, db_session: SQLAlchemySession) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "intro",
                                                step_tree=customer_lookup_self_service_wrapper_step_tree)
        return workflow_factory.create()

    @pytest.fixture
    def self_service_workflow(self, db_session: SQLAlchemySession) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "Iivr.self_service",
                                                step_tree=self_service_step_tree)
        return workflow_factory.create()

    @pytest.fixture
    def make_payment_workflow(self, db_session: SQLAlchemySession) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "Iivr.make_payment",
                                                step_tree=make_payment_step_tree)
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
    def loan_customers_queue(self, db_session) -> Queue:
        queue = qf.queue_factory(db_session).create(
            name="AFC.LN.CUS",
            transfer_routings=[{
                "transfer_type": "PSTN",
                "destination": "12345678902",
                "destination_system": "CISCO"
            }]
        )
        return queue

    @pytest.fixture
    def card_customers_queue(self, db_session) -> Queue:
        queue = qf.queue_factory(db_session).create(
            name="AFC.CC.CUS",
            transfer_routings=[{
                "transfer_type": "PSTN",
                "destination": "98765432102",
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

    @pytest.fixture
    def mock_customer_lookup(self) -> Mock:
        mock_telco = Mock()
        mock_telco.json.return_value = {
            "open_applications": [],
            "open_products": [
                {
                    "type": "CreditCardAccount",
                    "id": 144162,
                    "activatable?": False,
                    "credit_available_cents": 175442,
                    "past_due_amount_cents": 17178,
                    "operationally_charged_off?": False,
                    "days_late": None
                },
                {
                    "id": 3945439,
                    "type": "Loan",
                    "funding_date": "2020-12-18",
                    "active_payoff_quote?": False,
                    "product_type": "installment",
                    "product_subtype": "refinance",
                    "past_due_amount_cents": 21531,
                    "operationally_charged_off?": False,
                    "in_grace_period?": True,
                    "days_late": 3
                },
            ],
            "customer_information": {
                "id": 181205226,
                "state_of_residence": "AL",
                "disaster_relief_plan?": False,
                "last_contact": None
            }
        }
        mock_telco.status_code = 200
        return mock_telco

    @pytest.fixture
    def mock_customer_summary(self) -> Mock:
        mock_summary = Mock()
        mock_summary.json.return_value = {
            "open_applications": [],
            "open_products": [
                {
                    "type": "CreditCardAccount",
                    "id": 144162,
                    "activatable?": False,
                    "credit_available_cents": 175442,
                    "past_due_amount_cents": 17178,
                    "operationally_charged_off?": False,
                    "days_late": None
                },
                {
                    "id": 2838616,
                    "type": "Loan",
                    "in_grace_period": False,
                    "can_make_ach_payment": True,
                    "can_run_check_balance_and_quote_payoff": True,
                    "past_due_amount_cents": 0,
                    "next_payment_date": None,
                    "next_payment_amount": "0.00",
                    "next_payment_method": None
                },
            ]
        }
        mock_summary.status_code = 200
        return mock_summary

    @time_machine.travel("2020-12-29 19:00")
    def test_select_loan(self, db_session, workflow, self_service_workflow, greeting, call_routing, test_client,
                         loan_customers_queue, mock_customer_lookup, mock_customer_summary, make_payment_workflow):
        with patch.object(requests, "get", side_effect=[mock_customer_lookup, mock_customer_summary]):
            init_form = {"CallSid": "test",
                         "To": "+15555555555",
                         "From": "+155555555556",
                         "Digits": ""}

            initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
            assert initial_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello from <phoneme alp'
                b'habet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say><Gather action='
                b'"/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="'
                b'6"><Say>For questions about your Credit Card, press 1. For questions about your Loan, press '
                b'2.</Say></Gather></Response>')

            select_product_form = {"CallSid": "test",
                                   "To": "+15555555555",
                                   "From": "+155555555556",
                                   "Digits": "2"}
            select_product_response = test_client.post("/api/v1/twilio/continue", data=select_product_form)
            assert select_product_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twil'
                b'io/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>To he'
                b'ar your current loan balance and summary of recent payments, press 1. To mak'
                b'e a payment on your personal unsecured loan, press 2. For all other question'
                b's, press 0. To hear this again, press 9.</Say></Gather></Response>')

            make_payment_form = {"CallSid": "test",
                                 "To": "+15555555555",
                                 "From": "+155555555556",
                                 "Digits": "1"}

            make_payment_response = test_client.post("/api/v1/twilio/continue", data=make_payment_form)
            assert make_payment_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Dial>12345678902</Dial></Re'
                b'sponse>')

    @time_machine.travel("2020-12-29 19:00")
    def test_select_card(self, db_session, workflow, self_service_workflow, greeting, call_routing, test_client,
                         mock_customer_lookup, mock_customer_summary):
        with patch.object(requests, "get", side_effect=[mock_customer_lookup, mock_customer_summary]):
            init_form = {"CallSid": "test",
                         "To": "+15555555555",
                         "From": "+155555555556",
                         "Digits": ""}

            initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
            assert initial_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello from <phoneme alp'
                b'habet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say><Gather action='
                b'"/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="'
                b'6"><Say>For questions about your Credit Card, press 1. For questions about your Loan, press '
                b'2.</Say></Gather></Response>')

            select_product_form = {"CallSid": "test",
                                   "To": "+15555555555",
                                   "From": "+155555555556",
                                   "Digits": "1"}
            select_product_response = test_client.post("/api/v1/twilio/continue", data=select_product_form)
            assert select_product_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twil'
                b'io/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>To he'
                b'ar your card balance and statement information, press 1. To make a payment o'
                b'n your credit card balance, press 2. If you&#8217;re calling about a lost or'
                b' stolen card, press 3. For all other questions, press 0. To hear this again,'
                b' press 9.</Say></Gather></Response>')

            lost_card_form = {"CallSid": "test",
                              "To": "+15555555555",
                              "From": "+155555555556",
                              "Digits": "3"}

            lost_card_response = test_client.post("/api/v1/twilio/continue", data=lost_card_form)
            assert lost_card_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Dial>800-880-5076</Dial></R'
                b'esponse>')

    @time_machine.travel("2020-12-29 19:00")
    def test_bad_input_to_queue(self, db_session, workflow, self_service_workflow, greeting, call_routing, test_client,
                                loan_customers_queue, mock_customer_lookup, mock_customer_summary):
        with patch.object(requests, "get", side_effect=[mock_customer_lookup, mock_customer_summary]):
            init_form = {"CallSid": "test",
                         "To": "+15555555555",
                         "From": "+155555555556",
                         "Digits": ""}

            initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
            assert initial_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello from <phoneme alp'
                b'habet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say><Gather action='
                b'"/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="'
                b'6"><Say>For questions about your Credit Card, press 1. For questions about your Loan, press '
                b'2.</Say></Gather></Response>')

            select_product_form = {"CallSid": "test",
                                   "To": "+15555555555",
                                   "From": "+155555555556",
                                   "Digits": "3"}
            select_product_response = test_client.post("/api/v1/twilio/continue", data=select_product_form)
            assert select_product_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twil'
                b'io/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>Unfor'
                b'tunately we did not receive a response or were unable to process your reques'
                b't.</Say><Say>For questions about your Credit Card, press 1. For questions about your Loan, p'
                b'ress 2.</Say></Gather></Response>')

            retry_product_form = {"CallSid": "test",
                                  "To": "+15555555555",
                                  "From": "+155555555556",
                                  "Digits": "7"}
            retry_product_response = test_client.post("/api/v1/twilio/continue", data=retry_product_form)
            assert retry_product_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twil'
                b'io/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>Unfor'
                b'tunately we did not receive a response or were unable to process your reques'
                b't.</Say><Say>For questions about your Credit Card, press 1. For questions ab'
                b'out your Loan, press 2.</Say></Gather></Response>')

            retry_product_form = {"CallSid": "test",
                                  "To": "+15555555555",
                                  "From": "+155555555556",
                                  "Digits": "6"}

            retry_product_response = test_client.post("/api/v1/twilio/continue", data=retry_product_form)
            assert retry_product_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Dial>12345678901</Dial></Re'
                b'sponse>'
            )

    @time_machine.travel("2020-12-29 19:00")
    def test_bad_input_recovery(self, db_session, workflow, self_service_workflow, greeting, call_routing, test_client,
                                card_customers_queue, mock_customer_lookup, mock_customer_summary):
        with patch.object(requests, "get", side_effect=[mock_customer_lookup, mock_customer_summary]):
            init_form = {"CallSid": "test",
                         "To": "+15555555555",
                         "From": "+155555555556",
                         "Digits": ""}

            initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
            assert initial_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello from <phoneme alp'
                b'habet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say><Gather action='
                b'"/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="'
                b'6"><Say>For questions about your Credit Card, press 1. For questions about your Loan, press '
                b'2.</Say></Gather></Response>')

            select_product_form = {"CallSid": "test",
                                   "To": "+15555555555",
                                   "From": "+155555555556",
                                   "Digits": "3"}
            select_product_response = test_client.post("/api/v1/twilio/continue", data=select_product_form)
            assert select_product_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twil'
                b'io/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>Unfor'
                b'tunately we did not receive a response or were unable to process your reques'
                b't.</Say><Say>For questions about your Credit Card, press 1. For questions about your Loan, p'
                b'ress 2.</Say></Gather></Response>')

            retry_product_form = {"CallSid": "test",
                                  "To": "+15555555555",
                                  "From": "+155555555556",
                                  "Digits": "5"}
            retry_product_response = test_client.post("/api/v1/twilio/continue", data=retry_product_form)
            assert retry_product_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twil'
                b'io/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>Unfor'
                b'tunately we did not receive a response or were unable to process your reques'
                b't.</Say><Say>For questions about your Credit Card, press 1. For questions about your Loan, p'
                b'ress 2.</Say></Gather></Response>')

            select_product_form = {"CallSid": "test",
                                   "To": "+15555555555",
                                   "From": "+155555555556",
                                   "Digits": "1"}
            select_product_response = test_client.post("/api/v1/twilio/continue", data=select_product_form)
            assert select_product_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twil'
                b'io/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>To he'
                b'ar your card balance and statement information, press 1. To make a payment o'
                b'n your credit card balance, press 2. If you&#8217;re calling about a lost or'
                b' stolen card, press 3. For all other questions, press 0. To hear this again,'
                b' press 9.</Say></Gather></Response>')

            make_payment_form = {"CallSid": "test",
                                 "To": "+15555555555",
                                 "From": "+155555555556",
                                 "Digits": "2"}

            make_payment_response = test_client.post("/api/v1/twilio/continue", data=make_payment_form)
            assert make_payment_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Dial>98765432102</Dial></Re'
                b'sponse>')
