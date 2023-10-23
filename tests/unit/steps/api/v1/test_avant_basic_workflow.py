from typing import Dict

import pytest

from ivr_gateway.steps.api.v1 import AvantBasicWorkflowStep
from tests.unit.steps import BaseStepTestMixin


class TestAvantBasicWorkflowStep(BaseStepTestMixin):

    @pytest.fixture
    def workflow_response(self) -> Dict:
        return {
            "name": "make_payment",
            "state": {
                "product_type": "loan",
                "product_id": 3124394,
                "amount": "1.23",
                "method": "ach",
                "date": "2021-02-02",
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
                "session_uuid": "27608ae0-9330-4985-b4bd-251003a5bad2",
                "session_type_rank": 1,
                "originally_late": "true",
                "errors": []
            },
            "json_output": {
                "uuid": "27608ae0-9330-4985-b4bd-251003a5bad2",
                "name": "make_payment",
                "opts": {
                    "multipart": False
                },
                "state": {
                    "product_type": "loan",
                    "product_id": 3124394,
                    "amount": "1.23",
                    "method": "ach",
                    "date": "2021-02-02",
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
                    "session_uuid": "27608ae0-9330-4985-b4bd-251003a5bad2",
                    "session_type_rank": 1,
                    "originally_late": "true",
                    "errors": []
                },
                "step": {
                    "event": None,
                    "name": "confirmation",
                    "opts": {},
                    "script": "audio:product/make_payment/_authorizing,audio:shared/_Iivr,audio:shared/_account_servicer,audio:shared/_one_time_ach_debit,audio:shared/_account_ending_in,digits:5930,audio:shared/_for,currency:1.23,audio:shared/_on,date:02032021,audio:product/make_payment/_also_authorizing,audio:shared/_Iivr,audio:shared/_account_servicer,audio:product/make_payment/_confirmation_email",
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
                    "uuid": "9c1c2fb8-c571-496f-9fa0-4a89cb4eddb9"
                }
            }
        }

    @pytest.fixture
    def error_response(self) -> Dict:
        return {
            "name": "make_payment",
            "state": {
                "product_type": "loan",
                "product_id": 2838616,
                "amount": "500000.00",
                "method": "ach",
                "date": "2021-02-08",
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
                "session_uuid": "186739f3-12ab-4022-b149-5cb230810cb5",
                "session_type_rank": 1,
                "originally_late": "false",
                "errors": [
                    {
                        "input": None,
                        "message": "You cannot make a payment greater than your payoff amount."
                    }
                ],
                "error": "_enter_amount,currency:100.19,_or_less"
            },
            "json_output": {
                "uuid": "186739f3-12ab-4022-b149-5cb230810cb5",
                "name": "make_payment",
                "opts": {
                    "multipart": False
                },
                "state": {
                    "product_type": "loan",
                    "product_id": 2838616,
                    "amount": "500000.00",
                    "method": "ach",
                    "date": "2021-02-08",
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
                    "session_uuid": "186739f3-12ab-4022-b149-5cb230810cb5",
                    "session_type_rank": 1,
                    "originally_late": "false",
                    "errors": [
                        {
                            "input": None,
                            "message": "You cannot make a payment greater than your payoff amount."
                        }
                    ],

                },
                "step": {
                    "event": None,
                    "name": "select_amount",
                    "opts": {},
                    "script": "audio:product/make_payment/_select_amount,audio:shared/_enter_amount",
                    "error": "_enter_amount,currency:100.19,_or_less",
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
                            "value": "500000.00",
                            "__type_for_graphql": "WorkflowNumberInput"
                        }
                    ],
                    "errors": [
                        {
                            "input": None,
                            "message": "You cannot make a payment greater than your payoff amount."
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
                    "uuid": "a9bc2ef6-cf3e-4ac9-9699-7ecec18b1122"
                }
            }
        }

    def test_parse_step(self, workflow_response):
        results = AvantBasicWorkflowStep.parse_step(workflow_response)
        assert results == {
            "Iivr_basic_step_name": "confirmation",
            "confirmation_digits": "5930",
            "confirmation_currency": 123,
            "confirmation_date": "2021-02-03"
        }

    def test_parse_error(self, error_response):
        max_currency = AvantBasicWorkflowStep.parse_error("_enter_amount,currency:100.19,_or_less")
        assert max_currency == "please enter an amount that is $100.19 or less"
        earlier_date = AvantBasicWorkflowStep.parse_error("_enter_date,date:07312021,_or_earlier")
        assert earlier_date == "please enter a date that is July 31, 2021 or earlier"
        not_business_day = AvantBasicWorkflowStep.parse_error("date:02072021,_is_not_a_business_day,_enter_date,_a_business_day")
        assert not_business_day == "February 7, 2021 is not a business day please enter a date that is a business day"
