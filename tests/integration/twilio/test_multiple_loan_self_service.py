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


class TestMultipleLoanSelfServiceTwilio:

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
    def customers_queue(self, db_session) -> Queue:
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
                {
                    "id": 3945438,
                    "type": "Loan",
                    "funding_date": "2020-12-18",
                    "active_payoff_quote?": False,
                    "product_type": "installment",
                    "product_subtype": "unsecured",
                    "past_due_amount_cents": 0,
                    "operationally_charged_off?": False,
                    "in_grace_period?": False,
                    "days_late": 0
                }
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
                {
                    "id": 3945439,
                    "type": "Loan",
                    "in_grace_period": False,
                    "can_make_ach_payment": True,
                    "can_run_check_balance_and_quote_payoff": True,
                    "past_due_amount_cents": 21531,
                    "next_payment_date": None,
                    "next_payment_amount": "0.00",
                    "next_payment_method": None
                },
                {
                    "type": "CreditCardAccount",
                    "id": 144162,
                    "activatable?": False,
                    "credit_available_cents": 175442,
                    "past_due_amount_cents": 17178,
                    "operationally_charged_off?": False,
                    "days_late": None
                },
            ]
        }
        mock_summary.status_code = 200
        return mock_summary

    @time_machine.travel("2020-12-29 19:00")
    def test_new_call(self, db_session, workflow, self_service_workflow, greeting, call_routing, test_client,
                      customers_queue, mock_customer_lookup, mock_customer_summary, make_payment_workflow):
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
                b'io/continue" actionOnEmptyResult="true" numDigits="1" timeout="'
                b'6"><Say>To hear your current loan balance and summary of recent payments, pr'
                b'ess 1. To make a payment on your personal unsecured loan, press 2. For all o'
                b'ther questions, press 0. To hear this again, press 9.</Say></Gather></Response>')

            make_payment_form = {"CallSid": "test",
                                 "To": "+15555555555",
                                 "From": "+155555555556",
                                 "Digits": "2"}

            make_payment_response = test_client.post("/api/v1/twilio/continue", data=make_payment_form)
            assert make_payment_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Dial>12345678901</Dial></Re'
                b'sponse>')
            # call_legs = db_session.query(CallLeg).filter(CallLeg.contact_system_id == "test").all()
            # assert len(call_legs) == 2
            # assert call_legs[1].workflow_run.current_queue.name == "AFC.LN.CUS"

    @time_machine.travel("2020-12-29 19:00")
    def test_new_call_press_zero(self, db_session, workflow, self_service_workflow, greeting, call_routing, test_client,
                                 customers_queue, mock_customer_lookup, mock_customer_summary, make_payment_workflow):
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
                b'6"><Say>For questions about your Credit Card, press 1. For questions about y'
                b'our Loan, press 2.</Say></Gather></Response>'
            )

            loan_form = {"CallSid": "test",
                         "To": "+15555555555",
                         "From": "+155555555556",
                         "Digits": "2"}

            loan_response = test_client.post("/api/v1/twilio/continue", data=loan_form)
            assert loan_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twil'
                b'io/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>To he'
                b'ar your current loan balance and summary of recent payments, press 1. To mak'
                b'e a payment on your personal unsecured loan, press 2. For all other question'
                b's, press 0. To hear this again, press 9.</Say></Gather></Response>'
            )

            call_specialist_form = {"CallSid": "test",
                                    "To": "+15555555555",
                                    "From": "+155555555556",
                                    "Digits": "0"}

            call_specialist = test_client.post("/api/v1/twilio/continue", data=call_specialist_form)
            assert call_specialist.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Dial>12345678901</Dial></Re'
                b'sponse>')
