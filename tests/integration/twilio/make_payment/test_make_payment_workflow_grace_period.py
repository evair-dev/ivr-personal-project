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


class TestMakePaymentGracePeriod:

    @pytest.fixture
    def workflow(self, db_session: SQLAlchemySession) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "main_menu", step_tree=make_payment_step_tree)
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
    def mock_customer_summary(self) -> Mock:
        mock_lookup = Mock()
        mock_lookup.status_code = 200
        mock_lookup.json.return_value = {
            "open_applications": [],
            "open_products": [
                {
                    "id": 3050541,
                    "type": "Loan",
                    "in_grace_period": True,
                    "can_make_ach_payment": True,
                    "can_run_check_balance_and_quote_payoff": True,
                    "past_due_amount_cents": 9518,
                    "next_payment_date": "2021-03-01",
                    "next_payment_amount": "81.38",
                    "next_payment_method": "ach"
                }
            ]
        }
        return mock_lookup

    @pytest.fixture
    def mock_customer_lookup(self) -> Mock:
        mock_telco = Mock()
        mock_telco.json.return_value = {
            "open_applications": [],
            "open_products": [
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
            "name": "make_payment",
            "state": {
                "product_type": "loan",
                "product_id": 3050541,
                "session_uuid": "b56fcf83-8e09-4cb6-8981-14a13857ee08",
                "steps": [
                    "pay_with_bank_account_on_file"
                ],
                "actions": [],
                "session_type_rank": 1,
                "errors": [],
                "originally_late": "true"
            },
            "json_output": {
                "uuid": "b56fcf83-8e09-4cb6-8981-14a13857ee08",
                "name": "make_payment",
                "opts": {
                    "multipart": False
                },
                "state": {
                    "product_type": "loan",
                    "product_id": 3050541,
                    "session_uuid": "b56fcf83-8e09-4cb6-8981-14a13857ee08",
                    "steps": [
                        "pay_with_bank_account_on_file"
                    ],
                    "actions": [],
                    "session_type_rank": 1,
                    "errors": [],
                    "originally_late": "true"
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
                    "uuid": "37cffe3f-1798-4e32-8247-13935787fa61"
                }
            }
        }
        mock_response.status_code = 200
        return mock_response

    @pytest.fixture
    def mock_end_queue(self) -> Mock:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "make_payment",
            "state": {
                "product_type": "loan",
                "product_id": 3050541,
                "steps": [
                    "pay_with_bank_account_on_file",
                    "end_queue"
                ],
                "actions": [
                    "no"
                ],
                "step_action": "no",
                "session_uuid": "b56fcf83-8e09-4cb6-8981-14a13857ee08",
                "session_type_rank": 1,
                "originally_late": "true",
                "errors": []
            },
            "json_output": {
                "uuid": "b56fcf83-8e09-4cb6-8981-14a13857ee08",
                "name": "make_payment",
                "opts": {
                    "multipart": False
                },
                "state": {
                    "product_type": "loan",
                    "product_id": 3050541,
                    "steps": [
                        "pay_with_bank_account_on_file",
                        "end_queue"
                    ],
                    "actions": [
                        "no"
                    ],
                    "step_action": "no",
                    "session_uuid": "b56fcf83-8e09-4cb6-8981-14a13857ee08",
                    "session_type_rank": 1,
                    "originally_late": "true",
                    "errors": []
                },
                "step": {
                    "event": None,
                    "name": "end_queue",
                    "opts": {},
                    "script": "audio:shared/_silence",
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
                    "uuid": "c659e34c-fc20-4cba-901c-97c0fc74ce0c"
                }
            }
        }
        return mock_response

    @pytest.fixture
    def mock_pay_with_bank_account(self) -> Mock:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "make_payment",
            "state": {
                "product_type": "loan",
                "product_id": 3050541,
                "steps": [
                    "pay_with_bank_account_on_file",
                    "pay_amount_due"
                ],
                "actions": [
                    "yes"
                ],
                "step_action": "yes",
                "session_uuid": "b56fcf83-8e09-4cb6-8981-14a13857ee08",
                "session_type_rank": 1,
                "originally_late": "true",
                "errors": [],
                "method": "ach",
                "date": "2021-01-07"
            },
            "json_output": {
                "uuid": "b56fcf83-8e09-4cb6-8981-14a13857ee08",
                "name": "make_payment",
                "opts": {
                    "multipart": False
                },
                "state": {
                    "product_type": "loan",
                    "product_id": 3050541,
                    "steps": [
                        "pay_with_bank_account_on_file",
                        "pay_amount_due"
                    ],
                    "actions": [
                        "yes"
                    ],
                    "step_action": "yes",
                    "session_uuid": "b56fcf83-8e09-4cb6-8981-14a13857ee08",
                    "session_type_rank": 1,
                    "originally_late": "true",
                    "errors": [],
                    "method": "ach",
                    "date": "2021-01-07"
                },
                "step": {
                    "event": None,
                    "name": "pay_amount_due",
                    "opts": {},
                    "script": "audio:product/make_payment/_past_due_amount_is,currency:92.00,audio:product/make_payment/_pay_that_amount",
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
                    "uuid": "1e662010-2db2-4d38-88db-11a3f8a2cec9"
                }
            }
        }
        return mock_response

    @pytest.fixture
    def mock_pay_amount_due(self) -> Mock:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "make_payment",
            "state": {
                "product_type": "loan",
                "product_id": 3050541,
                "method": "ach",
                "date": "2021-01-07",
                "steps": [
                    "pay_with_bank_account_on_file",
                    "pay_amount_due",
                    "pay_on_earliest_date"
                ],
                "actions": [
                    "yes",
                    "yes"
                ],
                "step_action": "yes",
                "session_uuid": "b56fcf83-8e09-4cb6-8981-14a13857ee08",
                "session_type_rank": 1,
                "originally_late": "true",
                "errors": [],
                "amount": "92.00"
            },
            "json_output": {
                "uuid": "b56fcf83-8e09-4cb6-8981-14a13857ee08",
                "name": "make_payment",
                "opts": {
                    "multipart": False
                },
                "state": {
                    "product_type": "loan",
                    "product_id": 3050541,
                    "method": "ach",
                    "date": "2021-01-07",
                    "steps": [
                        "pay_with_bank_account_on_file",
                        "pay_amount_due",
                        "pay_on_earliest_date"
                    ],
                    "actions": [
                        "yes",
                        "yes"
                    ],
                    "step_action": "yes",
                    "session_uuid": "b56fcf83-8e09-4cb6-8981-14a13857ee08",
                    "session_type_rank": 1,
                    "originally_late": "true",
                    "errors": [],
                    "amount": "92.00"
                },
                "step": {
                    "event": None,
                    "name": "pay_on_earliest_date",
                    "opts": {},
                    "script": "audio:product/make_payment/_schedule_this_payment_for,date:01072021",
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
                    "uuid": "fff0fb34-0d18-4a68-8888-8b65d69b438e"
                }
            }
        }
        return mock_response

    @pytest.fixture
    def mock_pay_on_earliest_date(self) -> Mock:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "make_payment",
            "state": {
                "product_type": "loan",
                "product_id": 3050541,
                "amount": "92.00",
                "method": "ach",
                "date": "2021-01-07",
                "steps": [
                    "pay_with_bank_account_on_file",
                    "pay_amount_due",
                    "pay_on_earliest_date",
                    "confirmation"
                ],
                "actions": [
                    "yes",
                    "yes",
                    "yes"
                ],
                "step_action": "yes",
                "session_uuid": "b56fcf83-8e09-4cb6-8981-14a13857ee08",
                "session_type_rank": 1,
                "originally_late": "true",
                "errors": []
            },
            "json_output": {
                "uuid": "b56fcf83-8e09-4cb6-8981-14a13857ee08",
                "name": "make_payment",
                "opts": {
                    "multipart": False
                },
                "state": {
                    "product_type": "loan",
                    "product_id": 3050541,
                    "amount": "92.00",
                    "method": "ach",
                    "date": "2021-01-07",
                    "steps": [
                        "pay_with_bank_account_on_file",
                        "pay_amount_due",
                        "pay_on_earliest_date",
                        "confirmation"
                    ],
                    "actions": [
                        "yes",
                        "yes",
                        "yes"
                    ],
                    "step_action": "yes",
                    "session_uuid": "b56fcf83-8e09-4cb6-8981-14a13857ee08",
                    "session_type_rank": 1,
                    "originally_late": "true",
                    "errors": []
                },
                "step": {
                    "event": None,
                    "name": "confirmation",
                    "opts": {},
                    "script": "audio:product/make_payment/_authorizing,audio:shared/_Iivr,audio:shared/_account_servicer,audio:shared/_one_time_ach_debit,audio:shared/_account_ending_in,digits:1075,audio:shared/_for,currency:92.00,audio:shared/_on,date:01072021,audio:product/make_payment/_also_authorizing,audio:shared/_Iivr,audio:shared/_account_servicer,audio:product/make_payment/_confirmation_email",
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
                    "uuid": "f9db9c47-107b-4aa5-8d60-c6cff3165ee0"
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
                "product_id": 3050541,
                "amount": "92.00",
                "method": "ach",
                "date": "2021-01-07",
                "steps": [
                    "pay_with_bank_account_on_file",
                    "pay_amount_due",
                    "pay_on_earliest_date",
                    "confirmation",
                    "end"
                ],
                "actions": [
                    "yes",
                    "yes",
                    "yes",
                    "i_agree"
                ],
                "step_action": "i_agree",
                "session_uuid": "b56fcf83-8e09-4cb6-8981-14a13857ee08",
                "session_type_rank": 1,
                "originally_late": "true",
                "errors": []
            },
            "json_output": {
                "uuid": "b56fcf83-8e09-4cb6-8981-14a13857ee08",
                "name": "make_payment",
                "opts": {
                    "multipart": False
                },
                "state": {
                    "product_type": "loan",
                    "product_id": 3050541,
                    "amount": "92.00",
                    "method": "ach",
                    "date": "2021-01-07",
                    "steps": [
                        "pay_with_bank_account_on_file",
                        "pay_amount_due",
                        "pay_on_earliest_date",
                        "confirmation",
                        "end"
                    ],
                    "actions": [
                        "yes",
                        "yes",
                        "yes",
                        "i_agree"
                    ],
                    "step_action": "i_agree",
                    "session_uuid": "b56fcf83-8e09-4cb6-8981-14a13857ee08",
                    "session_type_rank": 1,
                    "originally_late": "true",
                    "errors": []
                },
                "step": {
                    "event": None,
                    "name": "end",
                    "opts": {
                        "end_button_text": {}
                    },
                    "script": "audio:product/make_payment/_payment_thank_you,currency:92.00,audio:product/make_payment/_authorized_on,date:01052021,audio:product/make_payment/_questions_please_call,phone:8007125407",
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

    @pytest.fixture
    def mock_confirmation_cancel(self) -> Mock:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "make_payment",
            "state": {
                "product_type": "loan",
                "product_id": 3050541,
                "amount": "92.00",
                "method": "ach",
                "date": "2021-01-07",
                "steps": [
                    "pay_with_bank_account_on_file",
                    "pay_amount_due",
                    "pay_on_earliest_date",
                    "confirmation",
                    "end_cancel"
                ],
                "actions": [
                    "yes",
                    "yes",
                    "yes",
                    "cancel"
                ],
                "step_action": "cancel",
                "session_uuid": "b56fcf83-8e09-4cb6-8981-14a13857ee08",
                "session_type_rank": 1,
                "originally_late": "true",
                "errors": []
            },
            "json_output": {
                "uuid": "b56fcf83-8e09-4cb6-8981-14a13857ee08",
                "name": "make_payment",
                "opts": {
                    "multipart": False
                },
                "state": {
                    "product_type": "loan",
                    "product_id": 3050541,
                    "amount": "92.00",
                    "method": "ach",
                    "date": "2021-01-07",
                    "steps": [
                        "pay_with_bank_account_on_file",
                        "pay_amount_due",
                        "pay_on_earliest_date",
                        "confirmation",
                        "end_cancel"
                    ],
                    "actions": [
                        "yes",
                        "yes",
                        "yes",
                        "cancel"
                    ],
                    "step_action": "cancel",
                    "session_uuid": "b56fcf83-8e09-4cb6-8981-14a13857ee08",
                    "session_type_rank": 1,
                    "originally_late": "true",
                    "errors": []
                },
                "step": {
                    "event": None,
                    "name": "end_cancel",
                    "opts": {},
                    "script": "audio:product/make_payment/_payment_not_made",
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
                    "uuid": "1dfdc77e-8094-4c93-9751-8f167f66b376"
                }
            }
        }

        return mock_response


class TestSuccessfulPayment(TestMakePaymentGracePeriod):

    @time_machine.travel("2020-12-29 19:00")
    def test_successful_payment(self, db_session, workflow, greeting, call_routing, test_client, mock_customer_summary,
                                mock_customer_lookup, mock_init_workflow, mock_pay_with_bank_account,
                                mock_pay_amount_due, mock_pay_on_earliest_date, mock_confirmation_agree):
        with patch.object(requests, "get", side_effect=[mock_customer_lookup, mock_customer_summary]):
            with patch.object(requests, "post",
                              side_effect=[mock_init_workflow,
                                           mock_pay_with_bank_account, mock_pay_amount_due, mock_pay_on_earliest_date,
                                           mock_confirmation_agree
                                           ]) as mock_post:
                # start_time = datetime.now()
                init_form = {"CallSid": "test",
                             "To": "+15555555555",
                             "From": "+155555555556",
                             "Digits": "1"}

                confirm_form = {"CallSid": "test",
                                "To": "+15555555555",
                                "From": "+155555555556",
                                "Digits": "1"}

                # retry_form = {"CallSid": "test",
                #               "To": "+15555555555",
                #               "From": "+155555555556",
                #               "Digits": "2"}

                replay_form = {"CallSid": "test",
                               "To": "+15555555555",
                               "From": "+155555555556",
                               "Digits": "9"}
                initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
                assert initial_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello from <phoneme alp' \
                                                b'habet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say><Say>Would you ' \
                                                b'like to make this payment with your bank account on file?</Say><Gather actio' \
                                                b'n="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>If yes, press 1. If no' \
                                                b', press 2. To hear this again, press 9.</Say></Gather></Response>'

                bank_account_response = test_client.post("/api/v1/twilio/continue", data=confirm_form)

                assert bank_account_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You have a past due amount of $92.00. Would you like to pay that amount?</Say><Gather actio' \
                                                     b'n="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>If yes, press 1. If no' \
                                                     b', press 2. To hear this again, press 9.</Say></Gather></Response>'

                replay_bank_account_response = test_client.post("/api/v1/twilio/continue", data=replay_form)

                assert replay_bank_account_response.data == bank_account_response.data

                amount_response = test_client.post("/api/v1/twilio/continue", data=confirm_form)

                assert amount_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Would you like to sched' \
                                               b'ule this payment for January 7, 2021?</Say><Gather action="/api/v1/twilio/continue"' \
                                               b' actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>If yes, press 1. If no, press 2. To hear t' \
                                               b'his again, press 9.</Say></Gather></Response>'

                earliest_date_response = test_client.post("/api/v1/twilio/continue", data=confirm_form)

                assert earliest_date_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You are authorizing <pho'
                    b'neme alphabet="ipa" ph="&#601;&#712;v&#593;nt">Avant</phone'
                    b'me>, as the servicer for your account. To initiate a one time A C H debit fro'
                    b'm your account ending in 1 0 7 5 for $92.00 on January 7, 2021. You are also'
                    b' authorizing <phoneme alphabet="ipa" ph="&#601;&#712;v&#593;nt">Avant</phone'
                    b'me> as the servicer for your account to send you confirmation of this transa'
                    b'ction via email.</Say><Gather action="/api/v1/twilio/continue" actionOnEmpty'
                    b'Result="true" numDigits="1" timeout="6"><Say>To authorize this transaction, '
                    b'press 1, to cancel, press 2, to hear this again, press 9.</Say></Gather></Re'
                    b'sponse>')

                # end_time = datetime.now()

                _, init_kwargs = mock_post.call_args_list[0]
                assert init_kwargs.get("json") == {"state": {"product_id": 3050541}}
