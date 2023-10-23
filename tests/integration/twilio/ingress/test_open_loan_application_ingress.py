from unittest.mock import Mock, patch

import pytest
import requests
import time_machine
from sqlalchemy.orm import Session as SQLAlchemySession

from ivr_gateway.models.contacts import Greeting, InboundRouting, ContactLeg
from ivr_gateway.models.queues import Queue
from ivr_gateway.models.workflows import Workflow
from tests.factories import queues as qf

from tests.factories import workflow as wcf
from tests.fixtures.step_trees.secure_call import secure_call_step_tree
from tests.fixtures.step_trees.ingress import ingress_step_tree


class TestOpenLoanApplicationIngressTwilio:

    @pytest.fixture
    def workflow(self, db_session: SQLAlchemySession) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "ingress", step_tree=ingress_step_tree)
        return workflow_factory.create()

    @pytest.fixture
    def secure_call_workflow(self, db_session: SQLAlchemySession) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "Iivr.secure_call", step_tree=secure_call_step_tree)
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
    def originations_queue(self, db_session) -> Queue:
        queue = qf.queue_factory(db_session).create(
            name="AFC.LN.ORIG",
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
            "open_applications": [{
                "id": 1234,
                "type": "Loan"
            }],
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
                    "id": 3050541,
                    "type": "Loan",
                    "funding_date": "2018-03-21",
                    "active_payoff_quote?": False,
                    "product_type": "installment",
                    "product_subtype": "unsecured",
                    "past_due_amount_cents": 9518,
                    "operationally_charged_off?": False,
                    "in_grace_period?": True,
                    "days_late": 0
                }
            ],
            "customer_information": {
                "id": 111350673,
                "state_of_residence": "FL",
                "disaster_relief_plan?": False,
                "last_contact": None
            }
        }
        mock_telco.status_code = 200
        return mock_telco

    @pytest.fixture
    def mock_init_workflow(self) -> Mock:
        mock_response = Mock()
        mock_response.json.return_value = {
            "name": "secure_call_ivr",
            "state": {
                "customer_id": 71568378,
                "session_uuid": "58aec38d-f08a-40a8-9b3b-210af64e7f5d",
                "action_to_take": "NOT_SECURED",
                "steps": [
                    "enter_dob"
                ],
                "actions": [],
                "session_type_rank": 1,
                "errors": [
                    {
                        "input": None,
                        "message": "Use error to provide a non-repeating preamble for the script"
                    }
                ],
                "error": "_for_security"
            },
            "json_output": {
                "uuid": "58aec38d-f08a-40a8-9b3b-210af64e7f5d",
                "name": "secure_call_ivr",
                "opts": {
                    "multipart": False
                },
                "state": {
                    "customer_id": 71568378,
                    "session_uuid": "58aec38d-f08a-40a8-9b3b-210af64e7f5d",
                    "action_to_take": "NOT_SECURED",
                    "steps": [
                        "enter_dob"
                    ],
                    "actions": [],
                    "session_type_rank": 1,
                    "errors": [
                        {
                            "input": None,
                            "message": "Use error to provide a non-repeating preamble for the script"
                        }
                    ],
                    "error": "_for_security"
                },
                "step": {
                    "event": None,
                    "name": "enter_dob",
                    "opts": {},
                    "script": "audio:ivr/secure_call/_enter_dob",
                    "error": "_for_security",
                    "inputs": [
                        {
                            "name": "dob",
                            "type": "date",
                            "required": True,
                            "value": None,
                            "__type_for_graphql": "WorkflowDateInput"
                        }
                    ],
                    "errors": [
                        {
                            "input": None,
                            "message": "Use error to provide a non-repeating preamble for the script"
                        }
                    ],
                    "actions": [
                        {
                            "displayName": "Next",
                            "name": "next",
                            "opts": {
                                "action_type": "confirm"
                            },
                            "isFinish": False,
                            "emphasized": None,
                            "secondary": None
                        }
                    ],
                    "action_to_emphasize": None,
                    "authenticity_token": "",
                    "uuid": "95fb36a4-0a81-420e-8a27-61797ae0f676"
                }
            }
        }
        mock_response.status_code = 200
        return mock_response

    @time_machine.travel("2020-12-29 19:00")
    def test_new_call(self, db_session, workflow, secure_call_workflow, greeting, call_routing, test_client,
                      mock_customer_lookup, mock_init_workflow, originations_queue):
        with patch.object(requests, "get", return_value=mock_customer_lookup):
            with patch.object(requests, "post",
                              return_value=mock_init_workflow):
                init_form = {"CallSid": "test",
                             "To": "+15555555555",
                             "From": "+155555555556",
                             "Digits": "1234"}

                initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
                assert initial_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello from <phoneme alp'
                    b'habet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say><Say>For securi'
                    b'ty and faster service, we would like to verify some information.</Say><Gathe'
                    b'r action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="8" '
                    b'timeout="6"><Say>Please enter your full 8-digit date of birth.</Say></Gather'
                    b'></Response>')

                call_legs = db_session.query(ContactLeg).filter(ContactLeg.contact_system_id == "test").all()
                assert len(call_legs) == 2
                assert call_legs[1].workflow_run.current_queue.name == "AFC.LN.ORIG"
