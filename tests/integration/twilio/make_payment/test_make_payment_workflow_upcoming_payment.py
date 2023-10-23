from unittest.mock import Mock, patch

import pytest
import requests
import time_machine
from sqlalchemy.orm import Session as SQLAlchemySession

from ivr_gateway.models.contacts import Greeting, InboundRouting
from ivr_gateway.models.queues import Queue
from ivr_gateway.models.workflows import Workflow
from tests.factories import queues as qf
from ivr_gateway.services.workflows.fields import CustomerLookupFieldLookupService
from tests.factories import workflow as wcf
from tests.fixtures.step_trees.make_payment import make_payment_step_tree
from tests.fixtures.step_trees.hangup import hangup_step_tree


class TestMakePaymentUpcomingPayment:

    @pytest.fixture
    def workflow(self, db_session: SQLAlchemySession) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "main_menu", step_tree=make_payment_step_tree)
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
    def mock_init_workflow(self) -> Mock:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "make_payment",
            "state": {
                "product_type": "loan",
                "product_id": 3942467,
                "session_uuid": "803f4b4c-057d-4438-a39f-0e1072f3c88a",
                "steps": [
                    "apply_to_future_installments"
                ],
                "actions": [],
                "session_type_rank": 1,
                "errors": [],
                "originally_late": "false"
            },
            "json_output": {
                "uuid": "803f4b4c-057d-4438-a39f-0e1072f3c88a",
                "name": "make_payment",
                "opts": {
                    "multipart": False
                },
                "state": {
                    "product_type": "loan",
                    "product_id": 3942467,
                    "session_uuid": "803f4b4c-057d-4438-a39f-0e1072f3c88a",
                    "steps": [
                        "apply_to_future_installments"
                    ],
                    "actions": [],
                    "session_type_rank": 1,
                    "errors": [],
                    "originally_late": "false"
                },
                "step": {
                    "event": None,
                    "name": "apply_to_future_installments",
                    "opts": {},
                    "script": "audio:product/make_payment/_payment_for_installment,date:01252021",
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
                            "secondary": True
                        }
                    ],
                    "action_to_emphasize": None,
                    "authenticity_token": "",
                    "uuid": "102ff1b3-2dc5-4852-8ca3-af632d3df309"
                }
            }
        }

        return mock_response

    @pytest.fixture
    def mock_apply_to_future_installments(self) -> Mock:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "make_payment",
            "state": {
                "product_type": "loan",
                "product_id": 3942467,
                "steps": [
                    "apply_to_future_installments",
                    "pay_with_bank_account_on_file"
                ],
                "actions": [
                    "yes"
                ],
                "step_action": "yes",
                "session_uuid": "803f4b4c-057d-4438-a39f-0e1072f3c88a",
                "session_type_rank": 1,
                "originally_late": "false",
                "errors": [],
                "apply_to_future_installments": "true"
            },
            "json_output": {
                "uuid": "803f4b4c-057d-4438-a39f-0e1072f3c88a",
                "name": "make_payment",
                "opts": {
                    "multipart": False
                },
                "state": {
                    "product_type": "loan",
                    "product_id": 3942467,
                    "steps": [
                        "apply_to_future_installments",
                        "pay_with_bank_account_on_file"
                    ],
                    "actions": [
                        "yes"
                    ],
                    "step_action": "yes",
                    "session_uuid": "803f4b4c-057d-4438-a39f-0e1072f3c88a",
                    "session_type_rank": 1,
                    "originally_late": "false",
                    "errors": [],
                    "apply_to_future_installments": "true"
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
                    "uuid": "b4d58ea5-2cda-4150-821e-c6e75c5f69f3"
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
                "product_id": 3942467,
                "apply_to_future_installments": "true",
                "steps": [
                    "apply_to_future_installments",
                    "pay_with_bank_account_on_file",
                    "pay_on_earliest_date"
                ],
                "actions": [
                    "yes",
                    "yes"
                ],
                "step_action": "yes",
                "session_uuid": "803f4b4c-057d-4438-a39f-0e1072f3c88a",
                "session_type_rank": 1,
                "originally_late": "false",
                "errors": [],
                "method": "ach"
            },
            "json_output": {
                "uuid": "803f4b4c-057d-4438-a39f-0e1072f3c88a",
                "name": "make_payment",
                "opts": {
                    "multipart": False
                },
                "state": {
                    "product_type": "loan",
                    "product_id": 3942467,
                    "apply_to_future_installments": "true",
                    "steps": [
                        "apply_to_future_installments",
                        "pay_with_bank_account_on_file",
                        "pay_on_earliest_date"
                    ],
                    "actions": [
                        "yes",
                        "yes"
                    ],
                    "step_action": "yes",
                    "session_uuid": "803f4b4c-057d-4438-a39f-0e1072f3c88a",
                    "session_type_rank": 1,
                    "originally_late": "false",
                    "errors": [],
                    "method": "ach"
                },
                "step": {
                    "event": None,
                    "name": "pay_on_earliest_date",
                    "opts": {},
                    "script": "audio:product/make_payment/_schedule_this_payment_for,date:01112021",
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
                    "uuid": "e0affe86-6ee7-4b54-8efb-92b4bada2666"
                }
            }
        }

        return mock_response

    @pytest.fixture
    def mock_pay_on_earliest_date_yes(self) -> Mock:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "make_payment",
            "state": {
                "product_type": "loan",
                "product_id": 3942467,
                "method": "ach",
                "apply_to_future_installments": "true",
                "steps": [
                    "apply_to_future_installments",
                    "pay_with_bank_account_on_file",
                    "pay_on_earliest_date",
                    "pay_amount_due"
                ],
                "actions": [
                    "yes",
                    "yes",
                    "yes"
                ],
                "step_action": "yes",
                "session_uuid": "803f4b4c-057d-4438-a39f-0e1072f3c88a",
                "session_type_rank": 1,
                "originally_late": "false",
                "errors": [],
                "date": "2021-01-11"
            },
            "json_output": {
                "uuid": "803f4b4c-057d-4438-a39f-0e1072f3c88a",
                "name": "make_payment",
                "opts": {
                    "multipart": False
                },
                "state": {
                    "product_type": "loan",
                    "product_id": 3942467,
                    "method": "ach",
                    "apply_to_future_installments": "true",
                    "steps": [
                        "apply_to_future_installments",
                        "pay_with_bank_account_on_file",
                        "pay_on_earliest_date",
                        "pay_amount_due"
                    ],
                    "actions": [
                        "yes",
                        "yes",
                        "yes"
                    ],
                    "step_action": "yes",
                    "session_uuid": "803f4b4c-057d-4438-a39f-0e1072f3c88a",
                    "session_type_rank": 1,
                    "originally_late": "false",
                    "errors": [],
                    "date": "2021-01-11"
                },
                "step": {
                    "event": None,
                    "name": "pay_amount_due",
                    "opts": {},
                    "script": "audio:product/make_payment/_next_payment_amount_is,currency:114.82,audio:product/make_payment/_pay_that_amount",
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
                    "uuid": "5d09602d-4e0a-41ca-8353-eeaf4e3de52d"
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
                "product_id": 3942467,
                "method": "ach",
                "apply_to_future_installments": "true",
                "steps": [
                    "apply_to_future_installments",
                    "pay_with_bank_account_on_file",
                    "pay_on_earliest_date",
                    "select_date"
                ],
                "actions": [
                    "yes",
                    "yes",
                    "no"
                ],
                "step_action": "no",
                "session_uuid": "5d09602d-4e0a-41ca-8353-eeaf4e3de52d",
                "session_type_rank": 1,
                "originally_late": "false",
                "errors": []
            },
            "json_output": {
                "uuid": "5d09602d-4e0a-41ca-8353-eeaf4e3de52d",
                "name": "make_payment",
                "opts": {
                    "multipart": False
                },
                "state": {
                    "product_type": "loan",
                    "product_id": 3942467,
                    "method": "ach",
                    "apply_to_future_installments": "true",
                    "steps": [
                        "apply_to_future_installments",
                        "pay_with_bank_account_on_file",
                        "pay_on_earliest_date",
                        "select_date"
                    ],
                    "actions": [
                        "yes",
                        "yes",
                        "no"
                    ],
                    "step_action": "no",
                    "session_uuid": "5d09602d-4e0a-41ca-8353-eeaf4e3de52d",
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
                            "min": "2021-01-11",
                            "max": "2021-07-06",
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
                    "uuid": "5d09602d-4e0a-41ca-8353-eeaf4e3de52d"
                }
            }
        }

        return mock_response

    @pytest.fixture
    def mock_pay_amount_due_yes(self) -> Mock:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "make_payment",
            "state": {
                "product_type": "loan",
                "product_id": 3942467,
                "method": "ach",
                "date": "2021-01-11",
                "apply_to_future_installments": "true",
                "steps": [
                    "apply_to_future_installments",
                    "pay_with_bank_account_on_file",
                    "pay_on_earliest_date",
                    "pay_amount_due",
                    "confirmation"
                ],
                "actions": [
                    "yes",
                    "yes",
                    "yes",
                    "yes"
                ],
                "step_action": "yes",
                "session_uuid": "803f4b4c-057d-4438-a39f-0e1072f3c88a",
                "session_type_rank": 1,
                "originally_late": "false",
                "errors": [],
                "amount": "114.82"
            },
            "json_output": {
                "uuid": "803f4b4c-057d-4438-a39f-0e1072f3c88a",
                "name": "make_payment",
                "opts": {
                    "multipart": False
                },
                "state": {
                    "product_type": "loan",
                    "product_id": 3942467,
                    "method": "ach",
                    "date": "2021-01-11",
                    "apply_to_future_installments": "true",
                    "steps": [
                        "apply_to_future_installments",
                        "pay_with_bank_account_on_file",
                        "pay_on_earliest_date",
                        "pay_amount_due",
                        "confirmation"
                    ],
                    "actions": [
                        "yes",
                        "yes",
                        "yes",
                        "yes"
                    ],
                    "step_action": "yes",
                    "session_uuid": "803f4b4c-057d-4438-a39f-0e1072f3c88a",
                    "session_type_rank": 1,
                    "originally_late": "false",
                    "errors": [],
                    "amount": "114.82"
                },
                "step": {
                    "event": None,
                    "name": "confirmation",
                    "opts": {},
                    "script": "audio:product/make_payment/_authorizing,audio:shared/_Iivr,audio:shared/_account_servicer,audio:shared/_one_time_ach_debit,audio:shared/_account_ending_in,digits:8546,audio:shared/_for,currency:114.82,audio:shared/_on,date:01112021,audio:product/make_payment/_also_authorizing,audio:shared/_Iivr,audio:shared/_account_servicer,audio:product/make_payment/_confirmation_email",
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
                    "uuid": "c0e0b43a-b1e5-4087-9f83-e8ac769ed0de"
                }
            }
        }

        return mock_response

    @pytest.fixture
    def mock_pay_amount_due_no(self) -> Mock:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "make_payment",
            "state": {
                "product_type": "loan",
                "product_id": 3942467,
                "method": "ach",
                "date": "2021-01-11",
                "apply_to_future_installments": "true",
                "steps": [
                    "apply_to_future_installments",
                    "pay_with_bank_account_on_file",
                    "pay_on_earliest_date",
                    "pay_amount_due",
                    "select_amount"
                ],
                "actions": [
                    "yes",
                    "yes",
                    "yes",
                    "no"
                ],
                "step_action": "no",
                "session_uuid": "803f4b4c-057d-4438-a39f-0e1072f3c88a",
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
                    "product_id": 3942467,
                    "method": "ach",
                    "date": "2021-01-11",
                    "apply_to_future_installments": "true",
                    "steps": [
                        "apply_to_future_installments",
                        "pay_with_bank_account_on_file",
                        "pay_on_earliest_date",
                        "pay_amount_due",
                        "select_amount"
                    ],
                    "actions": [
                        "yes",
                        "yes",
                        "yes",
                        "no"
                    ],
                    "step_action": "no",
                    "session_uuid": "803f4b4c-057d-4438-a39f-0e1072f3c88a",
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
                    "uuid": "346f723a-8d88-4702-8766-529f88b6f141"
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
                "product_id": 3942467,
                "amount": "1.23",
                "method": "ach",
                "date": "2021-01-11",
                "apply_to_future_installments": "true",
                "steps": [
                    "apply_to_future_installments",
                    "pay_with_bank_account_on_file",
                    "pay_on_earliest_date",
                    "pay_amount_due",
                    "select_amount",
                    "confirmation"
                ],
                "actions": [
                    "yes",
                    "yes",
                    "yes",
                    "no",
                    "next"
                ],
                "step_action": "next",
                "session_uuid": "803f4b4c-057d-4438-a39f-0e1072f3c88a",
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
                    "product_id": 3942467,
                    "amount": "1.23",
                    "method": "ach",
                    "date": "2021-01-11",
                    "apply_to_future_installments": "true",
                    "steps": [
                        "apply_to_future_installments",
                        "pay_with_bank_account_on_file",
                        "pay_on_earliest_date",
                        "pay_amount_due",
                        "select_amount",
                        "confirmation"
                    ],
                    "actions": [
                        "yes",
                        "yes",
                        "yes",
                        "no",
                        "next"
                    ],
                    "step_action": "next",
                    "session_uuid": "803f4b4c-057d-4438-a39f-0e1072f3c88a",
                    "session_type_rank": 1,
                    "originally_late": "false",
                    "errors": []
                },
                "step": {
                    "event": None,
                    "name": "confirmation",
                    "opts": {},
                    "script": "audio:product/make_payment/_authorizing,audio:shared/_Iivr,audio:shared/_account_servicer,audio:shared/_one_time_ach_debit,audio:shared/_account_ending_in,digits:8546,audio:shared/_for,currency:1.23,audio:shared/_on,date:01112021,audio:product/make_payment/_also_authorizing,audio:shared/_Iivr,audio:shared/_account_servicer,audio:product/make_payment/_confirmation_email",
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
                    "uuid": "8516f655-66c2-4769-99c6-dd397cb3eac3"
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
                "product_id": 3942467,
                "amount": "1.23",
                "method": "ach",
                "date": "2021-01-11",
                "apply_to_future_installments": "true",
                "steps": [
                    "apply_to_future_installments",
                    "pay_with_bank_account_on_file",
                    "pay_on_earliest_date",
                    "pay_amount_due",
                    "select_amount",
                    "confirmation",
                    "end"
                ],
                "actions": [
                    "yes",
                    "yes",
                    "yes",
                    "no",
                    "next",
                    "i_agree"
                ],
                "step_action": "i_agree",
                "session_uuid": "803f4b4c-057d-4438-a39f-0e1072f3c88a",
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
                    "script": "audio:product/make_payment/_payment_thank_you,currency:1.23,audio:product/make_payment/_authorized_on,date:01112021,audio:product/make_payment/_questions_please_call,phone:8007125407",
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
                                mock_apply_to_future_installments, mock_init_workflow,
                                mock_pay_with_bank_account_on_file,
                                mock_pay_amount_due_no, mock_pay_amount_1_23, mock_pay_on_earliest_date_yes,
                                mock_confirmation_agree):
        with patch.object(CustomerLookupFieldLookupService, "get_field_by_lookup_key", side_effect=[71568378, 3050541]):
            with patch.object(requests, "post",
                              side_effect=[mock_init_workflow, mock_apply_to_future_installments,
                                           mock_pay_with_bank_account_on_file, mock_pay_on_earliest_date_yes,
                                           mock_pay_amount_due_no, mock_pay_amount_1_23,
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

                replay_form = {"CallSid": "test",
                               "To": "+15555555555",
                               "From": "+155555555556",
                               "Digits": "9"}
                initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
                assert initial_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello from <phoneme alp' \
                                                b'habet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say><Say>Is this pa' \
                                                b'yment for your upcoming installment due on: January 25, 2021?</Say><Gather a' \
                                                b'ction="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>If yes, pre' \
                                                b'ss 1. If no, press 2. To hear this again, press 9.</Say></Gather></Response>'

                upcoming_payment_response = test_client.post("/api/v1/twilio/continue", data=yes_form)

                assert upcoming_payment_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Would you like to make ' \
                                                         b'this payment with your bank account on file?</Say><Gather action="/api/v1/tw' \
                                                         b'ilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>If yes, press 1. If no, pres' \
                                                         b's 2. To hear this again, press 9.</Say></Gather></Response>'

                replay_bank_account_response = test_client.post("/api/v1/twilio/continue", data=replay_form)

                assert replay_bank_account_response.data == upcoming_payment_response.data

                bank_response = test_client.post("/api/v1/twilio/continue", data=yes_form)

                assert bank_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Would you like to schedule'
                    b' this payment for January 11, 2021?</Say><Gather action="/api'
                    b'/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>If yes, press 1. If no'
                    b', press 2. To hear this again, press 9.</Say></Gather></Response>')

                earliest_date_response = test_client.post("/api/v1/twilio/continue", data=yes_form)

                assert earliest_date_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Your next payment amoun'
                    b't is $114.82. Would you like to pay that amount?</Say><Gather action="/api/v'
                    b'1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>If yes, press 1. If no, '
                    b'press 2. To hear this again, press 9.</Say></Gather></Response>')

                # end_time = datetime.now()

                next_payment_response = test_client.post("/api/v1/twilio/continue", data=no_form)

                assert next_payment_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>How much would you like to pay?</Say><Gather action="/api/v'
                    b'1/twilio/continue" actionOnEmptyResult="true" timeout="6"><Say>Please enter the amount using the numbers on your telephone key pad. Press star for the decimal point.</Say></Gather></Response>')

                payment_amount_form = {"CallSid": "test",
                                       "To": "+15555555555",
                                       "From": "+155555555556",
                                       "Digits": "1*23"}

                payment_amount_response = test_client.post("/api/v1/twilio/continue", data=payment_amount_form)

                assert payment_amount_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You entered $1.23</Say><Gather action="/api/v'
                    b'1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>If this is correct, press 1. To try again, press 2. To hear this again, press 9.</Say></Gather></Response>')

                payment_correct_response = test_client.post("/api/v1/twilio/continue", data=yes_form)

                assert payment_correct_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You are authorizing <pho'
                    b'neme alphabet="ipa" ph="&#601;&#712;v&#593;nt">Avant</phone'
                    b'me>, as the servicer for your account. To initiate a one time A C H debit fro'
                    b'm your account ending in 8 5 4 6 for $1.23 on January 11, 2021. You are also'
                    b' authorizing <phoneme alphabet="ipa" ph="&#601;&#712;v&#593;nt">Avant</phone'
                    b'me> as the servicer for your account to send you confirmation of this transa'
                    b'ction via email.</Say><Gather action="/api/v1/twilio/continue" actionOnEmpty'
                    b'Result="true" numDigits="1" timeout="6"><Say>To authorize this transaction, '
                    b'press 1, to cancel, press 2, to hear this again, press 9.</Say></Gather></Response>')

                confirm_payment_response = test_client.post("/api/v1/twilio/continue", data=yes_form)

                assert confirm_payment_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Thank you for your paym'
                    b'ent of $1.23 authorized on January 11, 2021. If you have any questions, pleas'
                    b'e call us at 800 712 5407. </Say><Hangup /></Response>')

                _, init_kwargs = mock_post.call_args_list[0]
                assert init_kwargs.get("json") == {"state": {"product_id": 3050541}}
