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
from tests.fixtures.step_trees.make_payment import make_payment_step_tree
from tests.fixtures.step_trees.hangup import hangup_step_tree


class TestMakePaymentUpcomingPayment:

    @pytest.fixture
    def workflow(self, db_session: SQLAlchemySession) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "make_payment", step_tree=make_payment_step_tree)
        return workflow_factory.create()

    @pytest.fixture
    def self_service_workflow(self, db_session: SQLAlchemySession) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "Iivr.self_service_menu", step_tree=hangup_step_tree)
        return workflow_factory.create()

    @pytest.fixture
    def queue(self, db_session) -> Queue:
        queue = qf.queue_factory(db_session).create(
            name="test")
        return queue

    @pytest.fixture
    def greeting(self, db_session) -> Greeting:
        greeting = Greeting(message='hello from <phoneme alphabet="ipa" ph="əˈvɑnt">Iivr</phoneme>.')
        db_session.add(greeting)
        db_session.commit()
        return greeting

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
        mock_lookup = Mock()
        mock_lookup.status_code = 200
        mock_lookup.json.return_value = {
            "open_applications": [],
            "open_products": [
                {
                    "id": 2838616,
                    "type": "Loan",
                    "funding_date": "2018-03-21",
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
                "id": 111350673,
                "state_of_residence": "FL",
                "disaster_relief_plan?": False,
                "last_contact": None
            }
        }
        return mock_lookup

    @pytest.fixture
    def mock_init_workflow(self) -> Mock:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "make_payment",
            "state": {
                "product_type": "loan",
                "product_id": 2838616,
                "session_uuid": "70e27419-9ba7-4584-be58-32f616127d62",
                "steps": [
                    "pay_with_bank_account_on_file"
                ],
                "actions": [],
                "session_type_rank": 1,
                "errors": [],
                "originally_late": "false"
            },
            "json_output": {
                "uuid": "70e27419-9ba7-4584-be58-32f616127d62",
                "name": "make_payment",
                "opts": {
                    "multipart": False
                },
                "state": {
                    "product_type": "loan",
                    "product_id": 2838616,
                    "session_uuid": "70e27419-9ba7-4584-be58-32f616127d62",
                    "steps": [
                        "pay_with_bank_account_on_file"
                    ],
                    "actions": [],
                    "session_type_rank": 1,
                    "errors": [],
                    "originally_late": "false"
                },
                "step": {
                    "event": None,
                    "name": "pay_with_bank_account_on_file",
                    "opts": {},
                    "script": "audio:product/make_payment/_use_bank_account_on_file",
                    "error": None,
                    "inputs": [],
                    "errors": [],
                    "actions": [
                        {
                            "displayName": "Yes",
                            "name": "yes",
                            "opts": {
                                "action_type": "yes"
                            },
                            "isFinish": False,
                            "emphasized": None,
                            "secondary": None
                        },
                        {
                            "displayName": "No",
                            "name": "no",
                            "opts": {
                                "action_type": "no"
                            },
                            "isFinish": False,
                            "emphasized": None,
                            "secondary": None
                        }
                    ],
                    "action_to_emphasize": None,
                    "authenticity_token": "",
                    "uuid": "b01eddce-3cb8-4c47-9917-280e91fab37c"
                }
            }
        }

        return mock_response

    @pytest.fixture
    def mock_pay_with_bank_account_on_file(self) -> Mock:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "make_payment",
            "state": {
                "product_type": "loan",
                "product_id": 2838616,
                "steps": [
                    "pay_with_bank_account_on_file",
                    "pay_on_earliest_date"
                ],
                "actions": [
                    "yes"
                ],
                "step_action": "yes",
                "session_uuid": "70e27419-9ba7-4584-be58-32f616127d62",
                "session_type_rank": 1,
                "originally_late": "false",
                "errors": [],
                "method": "ach"
            },
            "json_output": {
                "uuid": "70e27419-9ba7-4584-be58-32f616127d62",
                "name": "make_payment",
                "opts": {
                    "multipart": False
                },
                "state": {
                    "product_type": "loan",
                    "product_id": 2838616,
                    "steps": [
                        "pay_with_bank_account_on_file",
                        "pay_on_earliest_date"
                    ],
                    "actions": [
                        "yes"
                    ],
                    "step_action": "yes",
                    "session_uuid": "70e27419-9ba7-4584-be58-32f616127d62",
                    "session_type_rank": 1,
                    "originally_late": "false",
                    "errors": [],
                    "method": "ach"
                },
                "step": {
                    "event": None,
                    "name": "pay_on_earliest_date",
                    "opts": {},
                    "script": "audio:product/make_payment/_schedule_this_payment_for,date:01202021",
                    "error": None,
                    "inputs": [],
                    "errors": [],
                    "actions": [
                        {
                            "displayName": "Yes",
                            "name": "yes",
                            "opts": {
                                "action_type": "yes"
                            },
                            "isFinish": False,
                            "emphasized": None,
                            "secondary": None
                        },
                        {
                            "displayName": "No",
                            "name": "no",
                            "opts": {
                                "action_type": "no"
                            },
                            "isFinish": False,
                            "emphasized": None,
                            "secondary": None
                        }
                    ],
                    "action_to_emphasize": None,
                    "authenticity_token": "",
                    "uuid": "78d4cfe4-c783-4474-a31d-479f98ab5615"
                }
            }
        }

        return mock_response

    @pytest.fixture
    def mock_pay_on_earliest_date_no(self) -> Mock:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "make_payment",
            "state": {
                "product_type": "loan",
                "product_id": 2838616,
                "method": "ach",
                "steps": [
                    "pay_with_bank_account_on_file",
                    "pay_on_earliest_date",
                    "select_date"
                ],
                "actions": [
                    "yes",
                    "no"
                ],
                "step_action": "no",
                "session_uuid": "70e27419-9ba7-4584-be58-32f616127d62",
                "session_type_rank": 1,
                "originally_late": "false",
                "errors": []
            },
            "json_output": {
                "uuid": "70e27419-9ba7-4584-be58-32f616127d62",
                "name": "make_payment",
                "opts": {
                    "multipart": False
                },
                "state": {
                    "product_type": "loan",
                    "product_id": 2838616,
                    "method": "ach",
                    "steps": [
                        "pay_with_bank_account_on_file",
                        "pay_on_earliest_date",
                        "select_date"
                    ],
                    "actions": [
                        "yes",
                        "no"
                    ],
                    "step_action": "no",
                    "session_uuid": "70e27419-9ba7-4584-be58-32f616127d62",
                    "session_type_rank": 1,
                    "originally_late": "false",
                    "errors": []
                },
                "step": {
                    "event": None,
                    "name": "select_date",
                    "opts": {},
                    "script": "audio:product/make_payment/_select_date,audio:shared/_enter_date",
                    "error": None,
                    "inputs": [
                        {
                            "name": "date",
                            "type": "date",
                            "min": "2021-01-20",
                            "max": "2021-07-17",
                            "required": True,
                            "placeholder": "Please select a date",
                            "readonly": False,
                            "value": None,
                            "__type_for_graphql": "WorkflowDateInput"
                        }
                    ],
                    "errors": [],
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
                    "uuid": "bed7a5bf-a89a-494b-8685-42c744003be5"
                }
            }
        }

        return mock_response

    @pytest.fixture
    def mock_pay_on_select_date_2020_12_12(self) -> Mock:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "make_payment",
            "state": {
                "product_type": "loan",
                "product_id": 2838616,
                "method": "ach",
                "date": None,
                "steps": [
                    "pay_with_bank_account_on_file",
                    "pay_on_earliest_date",
                    "select_date"
                ],
                "actions": [
                    "yes",
                    "no"
                ],
                "step_action": "next",
                "session_uuid": "70e27419-9ba7-4584-be58-32f616127d62",
                "session_type_rank": 1,
                "originally_late": "false",
                "errors": [
                    {
                        "input": "date",
                        "message": "Please select a date must be January 20, 2021, or later."
                    }
                ],
                "error": "_enter_date,date:01202021,_or_later"
            },
            "json_output": {
                "uuid": "70e27419-9ba7-4584-be58-32f616127d62",
                "name": "make_payment",
                "opts": {
                    "multipart": False
                },
                "state": {
                    "product_type": "loan",
                    "product_id": 2838616,
                    "method": "ach",
                    "date": None,
                    "steps": [
                        "pay_with_bank_account_on_file",
                        "pay_on_earliest_date",
                        "select_date"
                    ],
                    "actions": [
                        "yes",
                        "no"
                    ],
                    "step_action": "next",
                    "session_uuid": "70e27419-9ba7-4584-be58-32f616127d62",
                    "session_type_rank": 1,
                    "originally_late": "false",
                    "errors": [
                        {
                            "input": "date",
                            "message": "Please select a date must be January 20, 2021, or later."
                        }
                    ],
                    "error": "_enter_date,date:01202021,_or_later"
                },
                "step": {
                    "event": None,
                    "name": "select_date",
                    "opts": {},
                    "script": "audio:product/make_payment/_select_date,audio:shared/_enter_date",
                    "error": "_enter_date,date:01202021,_or_later",
                    "inputs": [
                        {
                            "name": "date",
                            "type": "date",
                            "min": "2021-01-20",
                            "max": "2021-07-17",
                            "required": True,
                            "placeholder": "Please select a date",
                            "readonly": False,
                            "value": None,
                            "__type_for_graphql": "WorkflowDateInput"
                        }
                    ],
                    "errors": [
                        {
                            "input": "date",
                            "message": "Please select a date must be January 20, 2021, or later."
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
                    "uuid": "3633e001-9b90-4422-9cae-3450e8d0e54b"
                }
            }
        }

        return mock_response

    @pytest.fixture
    def mock_pay_on_select_date_2021_01_22(self) -> Mock:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "make_payment",
            "state": {
                "product_type": "loan",
                "product_id": 2838616,
                "method": "ach",
                "date": "2021-01-22",
                "steps": [
                    "pay_with_bank_account_on_file",
                    "pay_on_earliest_date",
                    "select_date",
                    "select_amount"
                ],
                "actions": [
                    "yes",
                    "no",
                    "next"
                ],
                "step_action": "next",
                "session_uuid": "70e27419-9ba7-4584-be58-32f616127d62",
                "session_type_rank": 1,
                "originally_late": "false",
                "errors": []
            },
            "json_output": {
                "uuid": "70e27419-9ba7-4584-be58-32f616127d62",
                "name": "make_payment",
                "opts": {
                    "multipart": False
                },
                "state": {
                    "product_type": "loan",
                    "product_id": 2838616,
                    "method": "ach",
                    "date": "2021-01-22",
                    "steps": [
                        "pay_with_bank_account_on_file",
                        "pay_on_earliest_date",
                        "select_date",
                        "select_amount"
                    ],
                    "actions": [
                        "yes",
                        "no",
                        "next"
                    ],
                    "step_action": "next",
                    "session_uuid": "70e27419-9ba7-4584-be58-32f616127d62",
                    "session_type_rank": 1,
                    "originally_late": "false",
                    "errors": []
                },
                "step": {
                    "event": None,
                    "name": "select_amount",
                    "opts": {},
                    "script": "audio:product/make_payment/_select_amount,audio:shared/_enter_amount",
                    "error": None,
                    "inputs": [
                        {
                            "name": "amount",
                            "type": "number",
                            "placeholder": "Confirm your payment amount",
                            "required": True,
                            "min": 0.01,
                            "step": 0.01,
                            "min_message": "Value must be 0.01 or more",
                            "readonly": False,
                            "value": None,
                            "__type_for_graphql": "WorkflowNumberInput"
                        }
                    ],
                    "errors": [],
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
                    "uuid": "d0ea24e8-78dc-45ee-a26a-2bb084be501d"
                }
            }
        }

        return mock_response

    @pytest.fixture
    def mock_pay_amount_1_23(self) -> Mock:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "make_payment",
            "state": {
                "product_type": "loan",
                "product_id": 2838616,
                "amount": "1.23",
                "method": "ach",
                "date": "2021-01-22",
                "steps": [
                    "pay_with_bank_account_on_file",
                    "pay_on_earliest_date",
                    "select_date",
                    "select_amount",
                    "confirmation"
                ],
                "actions": [
                    "yes",
                    "no",
                    "next",
                    "next"
                ],
                "step_action": "next",
                "session_uuid": "70e27419-9ba7-4584-be58-32f616127d62",
                "session_type_rank": 1,
                "originally_late": "false",
                "errors": []
            },
            "json_output": {
                "uuid": "70e27419-9ba7-4584-be58-32f616127d62",
                "name": "make_payment",
                "opts": {
                    "multipart": False
                },
                "state": {
                    "product_type": "loan",
                    "product_id": 2838616,
                    "amount": "1.23",
                    "method": "ach",
                    "date": "2021-01-22",
                    "steps": [
                        "pay_with_bank_account_on_file",
                        "pay_on_earliest_date",
                        "select_date",
                        "select_amount",
                        "confirmation"
                    ],
                    "actions": [
                        "yes",
                        "no",
                        "next",
                        "next"
                    ],
                    "step_action": "next",
                    "session_uuid": "70e27419-9ba7-4584-be58-32f616127d62",
                    "session_type_rank": 1,
                    "originally_late": "false",
                    "errors": []
                },
                "step": {
                    "event": None,
                    "name": "confirmation",
                    "opts": {},
                    "script": "audio:product/make_payment/_authorizing,audio:shared/_Iivr,audio:shared/_account_servicer,audio:shared/_one_time_ach_debit,audio:shared/_account_ending_in,digits:4637,audio:shared/_for,currency:1.23,audio:shared/_on,date:01222021,audio:product/make_payment/_also_authorizing,audio:shared/_Iivr,audio:shared/_account_servicer,audio:product/make_payment/_confirmation_email",
                    "error": None,
                    "inputs": [],
                    "errors": [],
                    "actions": [
                        {
                            "displayName": "I agree",
                            "name": "i_agree",
                            "opts": {
                                "action_type": "authorize"
                            },
                            "isFinish": False,
                            "emphasized": None,
                            "secondary": None
                        },
                        {
                            "displayName": "Cancel",
                            "name": "cancel",
                            "opts": {
                                "action_type": "cancel"
                            },
                            "isFinish": False,
                            "emphasized": None,
                            "secondary": None
                        }
                    ],
                    "action_to_emphasize": None,
                    "authenticity_token": "",
                    "uuid": "d4267dd4-0852-4141-8dd4-1b1c5d0dd21f"
                }
            }
        }

        return mock_response

    @pytest.fixture
    def mock_confirmation_agree(self) -> Mock:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "make_payment",
            "state": {
                "product_type": "loan",
                "product_id": 2838616,
                "amount": "1.23",
                "method": "ach",
                "date": "2021-01-22",
                "steps": [
                    "pay_with_bank_account_on_file",
                    "pay_on_earliest_date",
                    "select_date",
                    "select_amount",
                    "confirmation",
                    "end"
                ],
                "actions": [
                    "yes",
                    "no",
                    "next",
                    "next",
                    "i_agree"
                ],
                "step_action": "i_agree",
                "session_uuid": "70e27419-9ba7-4584-be58-32f616127d62",
                "session_type_rank": 1,
                "originally_late": "false",
                "errors": []

            },
            "json_output": {
                "uuid": "803f4b4c-057d-4438-a39f-0e1072f3c88a",
                "name": "make_payment",
                "opts": {
                    "multipart": False
                },
                "state": {
                    "product_type": "loan",
                    "product_id": 2838616,
                    "amount": "1.23",
                    "method": "ach",
                    "date": "2021-01-22",
                    "steps": [
                        "pay_with_bank_account_on_file",
                        "pay_on_earliest_date",
                        "select_date",
                        "select_amount",
                        "confirmation",
                        "end"
                    ],
                    "actions": [
                        "yes",
                        "no",
                        "next",
                        "next",
                        "i_agree"
                    ],
                    "step_action": "i_agree",
                    "session_uuid": "70e27419-9ba7-4584-be58-32f616127d62",
                    "session_type_rank": 1,
                    "originally_late": "false",
                    "errors": []
                },
                "step": {
                    "event": None,
                    "name": "end",
                    "opts": {
                        "end_button_text": {}
                    },
                    "script": "audio:product/make_payment/_payment_thank_you,currency:1.23,audio:product/make_payment/_authorized_on,date:01182021,audio:product/make_payment/_questions_please_call,phone:8007125407",
                    "error": None,
                    "inputs": [],
                    "errors": [],
                    "actions": [
                        {
                            "displayName": "Finish",
                            "name": "finish",
                            "isFinish": True,
                            "opts": {}
                        }
                    ],
                    "action_to_emphasize": None,
                    "authenticity_token": "",
                    "uuid": "6c775776-d65e-469f-9b3d-2c3f91542895"
                }
            }
        }

        return mock_response


class TestSuccessfulPayment(TestMakePaymentUpcomingPayment):

    @time_machine.travel("2020-12-29 19:00")
    def test_successful_payment(self, db_session, workflow, self_service_workflow, greeting, call_routing, test_client,
                                mock_customer_lookup, mock_init_workflow,
                                mock_pay_with_bank_account_on_file,
                                mock_pay_on_earliest_date_no, mock_pay_on_select_date_2020_12_12,
                                mock_pay_on_select_date_2021_01_22,
                                mock_pay_amount_1_23, mock_confirmation_agree):
        with patch.object(requests, "get", side_effect=[mock_customer_lookup]) as mock_get:
            with patch.object(requests, "post",
                              side_effect=[mock_init_workflow, mock_pay_with_bank_account_on_file,
                                           mock_pay_on_earliest_date_no, mock_pay_on_select_date_2020_12_12,
                                           mock_pay_on_select_date_2021_01_22, mock_pay_amount_1_23,
                                           mock_confirmation_agree
                                           ]) as mock_post:
                # start_time = datetime.now()
                init_form = {"CallSid": "test",
                             "To": "+15555555555",
                             "From": "+155555555556",
                             "Digits": "1"}

                yes_form = {"CallSid": "test",
                            "To": "+15555555555",
                            "From": "+155555555556",
                            "Digits": "1"}

                no_form = {"CallSid": "test",
                           "To": "+15555555555",
                           "From": "+155555555556",
                           "Digits": "2"}

                initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
                assert initial_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello from <phoneme alp'
                    b'habet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say><Say>Would you '
                    b'like to make this payment with your bank account on file?</Say><Gather actio'
                    b'n="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout'
                    b'="6"><Say>If yes, press 1. If no, press 2. To hear this again, press 9.'
                    b'</Say></Gather></Response>')

                use_bank_account_response = test_client.post("/api/v1/twilio/continue", data=yes_form)

                assert use_bank_account_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Would you like to sched'
                    b'ule this payment for January 20, 2021?</Say><Gather action="/api/v1/twilio/c'
                    b'ontinue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>If yes, p'
                    b'ress 1. If no, press 2. To hear this again, press 9.'
                    b'</Say></Gather></Response>')

                earliest_date_response = test_client.post("/api/v1/twilio/continue", data=no_form)

                assert earliest_date_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>To select a date for th'
                    b'is payment, please enter the full eight digit date starting with month, day,'
                    b' then year.</Say><Gather action="/api/v1/twilio/continue" actionOnEmptyResul'
                    b't="true" numDigits="8" timeout="6"><Say>For january 2nd, 2016. Enter 0-1-0-2'
                    b'-2-0-1-6.</Say></Gather></Response>')

                date_2020_12_12_from = {"CallSid": "test",
                                        "To": "+15555555555",
                                        "From": "+155555555556",
                                        "Digits": "12122020"}

                date_2020_12_12_response = test_client.post("/api/v1/twilio/continue", data=date_2020_12_12_from)

                assert date_2020_12_12_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You entered December 12'
                    b', 2020</Say><Gather action="/api/v1/twilio/continue" actionOnEmptyResult="tr'
                    b'ue" numDigits="1" timeout="6"><Say>If this is correct, press 1. To try again'
                    b', press 2. To hear this again, press 9.</Say></Gather></Response>')

                # end_time = datetime.now()

                date_2020_12_12_confirmation_response = test_client.post("/api/v1/twilio/continue", data=yes_form)

                assert date_2020_12_12_confirmation_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twil'
                    b'io/continue" actionOnEmptyResult="true" numDigits="8" timeout="6"><Say>pleas'
                    b'e enter a date that is January 20, 2021 or later</Say><Say>For january 2n'
                    b'd, 2016. Enter 0-1-0-2-2-0-1-6.</Say></Gather></Response>')

                date_2021_01_20_from = {"CallSid": "test",
                                        "To": "+15555555555",
                                        "From": "+155555555556",
                                        "Digits": "01202021"}

                date_2020_12_12_response = test_client.post("/api/v1/twilio/continue", data=date_2021_01_20_from)

                assert date_2020_12_12_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You entered January 20'
                    b', 2021</Say><Gather action="/api/v1/twilio/continue" actionOnEmptyResult="tr'
                    b'ue" numDigits="1" timeout="6"><Say>If this is correct, press 1. To try again'
                    b', press 2. To hear this again, press 9.</Say></Gather></Response>')

                # end_time = datetime.now()

                date_2021_01_20_confirmation_response = test_client.post("/api/v1/twilio/continue", data=yes_form)

                assert date_2021_01_20_confirmation_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>How much would you like to pay?</Say><Gather action="/api/v'
                    b'1/twilio/continue" actionOnEmptyResult="true" timeout="6"><Say>Please enter the amount using the numbers on your telephone key pad. Press star for the decimal point.</Say></Gather></Response>')

                payment_amount_form = {"CallSid": "test",
                                       "To": "+15555555555",
                                       "From": "+155555555556",
                                       "Digits": "1*23"}

                payment_amount_response = test_client.post("/api/v1/twilio/continue", data=payment_amount_form)

                assert payment_amount_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You entered $1.23</Say><Gather action="/api/v'
                    b'1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>If this is correct, press 1. To try again, press 2. To hear this again, press 9.'
                    b'</Say></Gather></Response>')

                payment_correct_response = test_client.post("/api/v1/twilio/continue", data=yes_form)

                assert payment_correct_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You are authorizing <pho'
                    b'neme alphabet="ipa" ph="&#601;&#712;v&#593;nt">Avant</phone'
                    b'me>, as the servicer for your account. To initiate a one time A C H debit fro'
                    b'm your account ending in 4 6 3 7 for $1.23 on January 22, 2021. You are also'
                    b' authorizing <phoneme alphabet="ipa" ph="&#601;&#712;v&#593;nt">Avant</phone'
                    b'me> as the servicer for your account to send you confirmation of this transa'
                    b'ction via email.</Say><Gather action="/api/v1/twilio/continue" actionOnEmpty'
                    b'Result="true" numDigits="1" timeout="6"><Say>To authorize this transaction, '
                    b'press 1, to cancel, press 2, to hear this again, press 9.'
                    b'</Say></Gather></Response>')

                confirm_payment_response = test_client.post("/api/v1/twilio/continue", data=yes_form)

                assert confirm_payment_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Thank you for your paym'
                    b'ent of $1.23 authorized on January 18, 2021. If you have any questions, pleas'
                    b'e call us at 800 712 5407. </Say><Hangup /></Response>')

                _, init_kwargs = mock_post.call_args_list[0]
                assert init_kwargs.get("json") == {"state": {"product_id": 2838616}}

                _, select_amount_kwargs = mock_post.call_args_list[5]
                assert select_amount_kwargs.get("json") == {"state": {
                    "product_type": "loan",
                    "product_id": 2838616,
                    "amount": "1.23",
                    "method": "ach",
                    "date": "2021-01-22",
                    "steps": [
                        "pay_with_bank_account_on_file",
                        "pay_on_earliest_date",
                        "select_date",
                        "select_amount"
                    ],
                    "actions": [
                        "yes",
                        "no",
                        "next"
                    ],
                    "step_action": "next",
                    "session_uuid": "70e27419-9ba7-4584-be58-32f616127d62",
                    "session_type_rank": 1,
                    "originally_late": "false",
                    "errors": []
                }}
                assert mock_get.call_count == 1
