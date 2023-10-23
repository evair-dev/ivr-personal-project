from datetime import datetime
from unittest.mock import Mock, patch

import pytest
import requests
import time_machine
from sqlalchemy.orm import Session as SQLAlchemySession

from ivr_gateway.models.contacts import Greeting, InboundRouting, ContactLeg
from ivr_gateway.models.queues import Queue
from ivr_gateway.models.steps import StepRun
from ivr_gateway.models.workflows import Workflow
from ivr_gateway.services.amount.workflow_runner import WorkflowRunnerService
from ivr_gateway.services.calls import CallService
from tests.factories import queues as qf
from ivr_gateway.services.workflows.fields import CustomerLookupFieldLookupService

from tests.factories import workflow as wcf
from tests.fixtures.step_trees.secure_call import secure_call_step_tree
from tests.fixtures.step_trees.hangup import hangup_step_tree
from tests.fixtures.step_trees.main_menu import main_menu_step_tree


class TestSecureCallTwilio:

    @pytest.fixture
    def workflow(self, db_session: SQLAlchemySession) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "secure_call", step_tree=secure_call_step_tree)
        return workflow_factory.create()

    @pytest.fixture
    def self_service_workflow(self, db_session: SQLAlchemySession) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "Iivr.self_service_menu", step_tree=hangup_step_tree)
        return workflow_factory.create()

    @pytest.fixture
    def main_menu_workflow(self, db_session: SQLAlchemySession) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "Iivr.main_menu", step_tree=main_menu_step_tree)
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

    @pytest.fixture
    def mock_enter_dob(self) -> Mock:
        mock_response = Mock()
        mock_response.json.return_value = {
            "name": "secure_call_ivr",
            "state": {
                "customer_id": 71568378,
                "action_to_take": "NOT_SECURED",
                "steps": [
                    "enter_dob",
                    "enter_ssn"
                ],
                "actions": [
                    "next"
                ],
                "step_action": "next",
                "session_uuid": "58aec38d-f08a-40a8-9b3b-210af64e7f5d",
                "session_type_rank": 1,
                "errors": [
                    {
                        "input": None,
                        "message": "Use error to provide a non-repeating preamble for the script"
                    }
                ],
                "key": "632776ab",
                "error": "_one_more_step",
            },
            "json_output": {
                "uuid": "58aec38d-f08a-40a8-9b3b-210af64e7f5d",
                "name": "secure_call_ivr",
                "opts": {
                    "multipart": False
                },
                "state": {
                    "customer_id": 71568378,
                    "action_to_take": "NOT_SECURED",
                    "steps": [
                        "enter_dob",
                        "enter_ssn"
                    ],
                    "actions": [
                        "next"
                    ],
                    "step_action": "next",
                    "session_uuid": "58aec38d-f08a-40a8-9b3b-210af64e7f5d",
                    "session_type_rank": 1,
                    "errors": [
                        {
                            "input": None,
                            "message": "Use error to provide a non-repeating preamble for the script"
                        }
                    ],
                    "key": "632776ab",
                    "error": "_one_more_step"
                },
                "step": {
                    "event": None,
                    "name": "enter_ssn",
                    "opts": {},
                    "script": "audio:shared/_enter_ssn_last_4",
                    "error": "_one_more_step",
                    "inputs": [
                        {
                            "name": "ssn",
                            "type": "text",
                            "length": 4,
                            "match": "(?-mix:\\A\\d{4}\\z)",
                            "min_length": 4,
                            "max_length": 4,
                            "required": True,
                            "value": None,
                            "__type_for_graphql": "WorkflowTextInput"
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
                            "isFinish": None,
                            "emphasized": None,
                            "secondary": None
                        }
                    ],
                    "action_to_emphasize": None,
                    "authenticity_token": "",
                    "uuid": "619aab3f-28cf-4816-844f-5f4b2829bc5a"
                }
            }
        }
        mock_response.status_code = 200
        return mock_response

    @pytest.fixture
    def mock_enter_ssn(self) -> Mock:
        mock_response = Mock()
        mock_response.json.return_value = {
            "name": "secure_call_ivr",
            "state": {
                "customer_id": 71568378,
                "action_to_take": "632776ab",
                "steps": [
                    "enter_dob",
                    "enter_ssn",
                    "end"
                ],
                "actions": [
                    "next",
                    "next"
                ],
                "step_action": "next",
                "session_uuid": "58aec38d-f08a-40a8-9b3b-210af64e7f5d",
                "session_type_rank": 1,
                "errors": [],
                "key": "632776ab"
            },
            "json_output": {
                "session_uuid": "58aec38d-f08a-40a8-9b3b-210af64e7f5d",
                "name": "secure_call_ivr",
                "opts": {
                    "multipart": False
                },
                "state": {
                    "customer_id": 71568378,
                    "dob": "1954-11-22",
                    "action_to_take": "NOT_SECURED",
                    "steps": [
                        "enter_dob",
                        "enter_ssn",
                        "end"
                    ],
                    "actions": [
                        "next",
                        "next"
                    ],
                    "step_action": "next",
                    "session_uuid": "58aec38d-f08a-40a8-9b3b-210af64e7f5d",
                    "session_type_rank": 1,
                    "errors": [],
                    "key": "632776ab"
                },
                "step": {
                    "event": None,
                    "name": "end",
                    "opts": {},
                    "error": None,
                    "inputs": [],
                    "errors": [],
                    "actions": [
                        {
                            "displayName": "Finish",
                            "name": "finish",
                            "isFinish": None,
                            "opts": {}
                        }
                    ],
                    "action_to_emphasize": None,
                    "authenticity_token": "",
                    "uuid": "c88f78c2-15ee-44f4-965c-e90a4162bd30"
                }
            }
        }
        mock_response.status_code = 200
        return mock_response


class TestTwilioValidSecureCall(TestSecureCallTwilio):

    @time_machine.travel("2020-12-29 19:00")
    def test_new_call(self, db_session, workflow, self_service_workflow, main_menu_workflow,
                      greeting, call_routing, test_client,
                      mock_init_workflow, mock_enter_dob, mock_enter_ssn):
        with patch.object(CustomerLookupFieldLookupService, "get_field_by_lookup_key", return_value=71568378):
            with patch.object(requests, "post",
                              side_effect=[mock_init_workflow, mock_enter_dob,
                                           mock_enter_ssn]) as mock_post:
                start_time = datetime.now()
                init_form = {"CallSid": "test",
                             "To": "+15555555555",
                             "From": "+155555555556",
                             "Digits": "1234"}

                confirm_form = {"CallSid": "test",
                                "To": "+15555555555",
                                "From": "+155555555556",
                                "Digits": "1"}

                replay_form = {"CallSid": "test",
                               "To": "+15555555555",
                               "From": "+155555555556",
                               "Digits": "9"}
                initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
                assert initial_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello from <phoneme alp'
                    b'habet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say><Say>For securi'
                    b'ty and faster service, we would like to verify some information.</Say><Gathe'
                    b'r action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="8" '
                    b'timeout="6"><Say>Please enter your full 8-digit date of birth.</Say></Gather'
                    b'></Response>')

                birthday_form = {"CallSid": "test",
                                 "To": "+15555555555",
                                 "From": "+155555555556",
                                 "Digits": "11221954"}

                birthday_response = test_client.post("/api/v1/twilio/continue", data=birthday_form)

                assert birthday_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You entered November 22' \
                                                 b', 1954</Say><Gather action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><S' \
                                                 b'ay>If this is correct, press 1. To try again, press 2. To hear this again, p' \
                                                 b'ress 9.</Say></Gather></Response>'

                replay_birthday_response = test_client.post("/api/v1/twilio/continue", data=replay_form)

                assert replay_birthday_response.data == birthday_response.data

                confirm_birthday_response = test_client.post("/api/v1/twilio/continue", data=confirm_form)

                assert confirm_birthday_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Just one more step.</Sa'
                    b'y><Gather action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDig'
                    b'its="4" timeout="6"><Say>Please enter the last four digits of your social se'
                    b'curity number.</Say></Gather></Response>')

                ssn_form = {"CallSid": "test",
                            "To": "+15555555555",
                            "From": "+155555555556",
                            "Digits": "1689"}

                ssn_response = test_client.post("/api/v1/twilio/continue", data=ssn_form)

                assert ssn_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You entered 1 6 8 9' \
                                            b'</Say><Gather action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say' \
                                            b'>If this is correct, press 1. To try again, press 2. To hear this again,' \
                                            b' press 9.</Say></Gather></Response>'

                confirm_ssn_response = test_client.post("/api/v1/twilio/continue", data=confirm_form)

                assert confirm_ssn_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Hangup /></Response>'

                end_time = datetime.now()

                _, init_kwargs = mock_post.call_args_list[0]
                assert init_kwargs.get("json") == {"state": {"customer_id": 71568378}}

                _, dob_kwargs = mock_post.call_args_list[1]
                assert dob_kwargs["json"] == {
                    "state": {
                        "customer_id": 71568378,
                        "session_uuid": "58aec38d-f08a-40a8-9b3b-210af64e7f5d",
                        "action_to_take": "NOT_SECURED",
                        "step_action": "next",
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
                        "error": "_for_security",
                        "dob": "1954-11-22"
                    }
                }

                _, ssn_kwargs = mock_post.call_args_list[2]
                assert ssn_kwargs["json"] == {
                    "state": {
                        "customer_id": 71568378,
                        "session_uuid": "58aec38d-f08a-40a8-9b3b-210af64e7f5d",
                        "action_to_take": "NOT_SECURED",
                        "step_action": "next",
                        "steps": [
                            "enter_dob",
                            "enter_ssn"
                        ],
                        "actions": [
                            "next"
                        ],
                        "session_type_rank": 1,
                        "errors": [
                            {
                                "input": None,
                                "message": "Use error to provide a non-repeating preamble for the script"
                            }
                        ],
                        "error": "_one_more_step",
                        "ssn": "1689",
                        "key": "632776ab"
                    }
                }

                call_service = CallService(db_session)
                assert call_service.get_active_call_leg_for_call_system_and_id("twilio", "test") is None
                call_leg = (db_session.query(ContactLeg)
                            .filter(ContactLeg.contact_system == "twilio")
                            .filter(ContactLeg.contact_system_id == "test")
                            .first())
                contact = call_leg.contact
                assert contact.secured_key == "632776ab"
                assert contact.secured > start_time
                assert contact.secured < end_time


class TestTwilioRetrySecureCall(TestSecureCallTwilio):

    @time_machine.travel("2020-12-29 19:00")
    def test_retry(self, db_session, workflow, self_service_workflow, main_menu_workflow, greeting,
                   call_routing, test_client,
                   mock_init_workflow, mock_enter_dob, mock_enter_ssn):
        with patch.object(CustomerLookupFieldLookupService, "get_field_by_lookup_key", return_value=71568378):
            with patch.object(requests, "post",
                              side_effect=[mock_init_workflow, mock_enter_dob,
                                           mock_enter_ssn]) as mock_post:
                start_time = datetime.now()
                init_form = {"CallSid": "test",
                             "To": "+15555555555",
                             "From": "+155555555556",
                             "Digits": "1234"}

                confirm_form = {"CallSid": "test",
                                "To": "+15555555555",
                                "From": "+155555555556",
                                "Digits": "1"}

                retry_form = {"CallSid": "test",
                              "To": "+15555555555",
                              "From": "+155555555556",
                              "Digits": "2"}

                initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
                assert initial_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello from <phoneme alp'
                    b'habet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say><Say>For securi'
                    b'ty and faster service, we would like to verify some information.</Say><Gathe'
                    b'r action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="8" '
                    b'timeout="6"><Say>Please enter your full 8-digit date of birth.</Say></Gather'
                    b'></Response>')

                first_birthday_form = {"CallSid": "test",
                                       "To": "+15555555555",
                                       "From": "+155555555556",
                                       "Digits": "10211945"}

                first_birthday_response = test_client.post("/api/v1/twilio/continue", data=first_birthday_form)

                assert first_birthday_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You entered October 21' \
                                                       b', 1945</Say><Gather action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><S' \
                                                       b'ay>If this is correct, press 1. To try again, press 2. To hear this again, p' \
                                                       b'ress 9.</Say></Gather></Response>'

                retry_birthday_response = test_client.post("/api/v1/twilio/continue", data=retry_form)

                assert retry_birthday_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action=' \
                                                       b'"/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="8" timeout="6"><Say>Plea' \
                                                       b'se enter your full 8-digit date of birth.</Say></Gather></Respo' \
                                                       b'nse>'

                birthday_form = {"CallSid": "test",
                                 "To": "+15555555555",
                                 "From": "+155555555556",
                                 "Digits": "11221954"}

                birthday_response = test_client.post("/api/v1/twilio/continue", data=birthday_form)

                assert birthday_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You entered November 22' \
                                                 b', 1954</Say><Gather action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><S' \
                                                 b'ay>If this is correct, press 1. To try again, press 2. To hear this again, p' \
                                                 b'ress 9.</Say></Gather></Response>'

                confirm_birthday_response = test_client.post("/api/v1/twilio/continue", data=confirm_form)

                assert confirm_birthday_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Just one more step.</Sa'
                    b'y><Gather action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDig'
                    b'its="4" timeout="6"><Say>Please enter the last four digits of your social se'
                    b'curity number.</Say></Gather></Response>')

                ssn_form = {"CallSid": "test",
                            "To": "+15555555555",
                            "From": "+155555555556",
                            "Digits": "1689"}

                ssn_response = test_client.post("/api/v1/twilio/continue", data=ssn_form)

                assert ssn_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You entered 1 6 8 9' \
                                            b'</Say><Gather action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say' \
                                            b'>If this is correct, press 1. To try again, press 2. To hear this again,' \
                                            b' press 9.</Say></Gather></Response>'

                confirm_ssn_response = test_client.post("/api/v1/twilio/continue", data=confirm_form)

                assert confirm_ssn_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Hangup /></Response>'

                end_time = datetime.now()

                _, init_kwargs = mock_post.call_args_list[0]
                assert init_kwargs.get("json") == {"state": {"customer_id": 71568378}}

                _, dob_kwargs = mock_post.call_args_list[1]
                assert dob_kwargs["json"] == {
                    "state": {
                        "customer_id": 71568378,
                        "session_uuid": "58aec38d-f08a-40a8-9b3b-210af64e7f5d",
                        "action_to_take": "NOT_SECURED",
                        "step_action": "next",
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
                        "error": "_for_security",
                        "dob": "1954-11-22"
                    }
                }

                _, ssn_kwargs = mock_post.call_args_list[2]
                assert ssn_kwargs["json"] == {
                    "state": {
                        "customer_id": 71568378,
                        "session_uuid": "58aec38d-f08a-40a8-9b3b-210af64e7f5d",
                        "action_to_take": "NOT_SECURED",
                        "step_action": "next",
                        "steps": [
                            "enter_dob",
                            "enter_ssn"
                        ],
                        "actions": [
                            "next"
                        ],
                        "session_type_rank": 1,
                        "errors": [
                            {
                                "input": None,
                                "message": "Use error to provide a non-repeating preamble for the script"
                            }
                        ],
                        "error": "_one_more_step",
                        "ssn": "1689",
                        "key": "632776ab"
                    }
                }

                call_service = CallService(db_session)
                assert call_service.get_active_call_leg_for_call_system_and_id("twilio", "test") is None
                call_leg = (db_session.query(ContactLeg)
                            .filter(ContactLeg.contact_system == "twilio")
                            .filter(ContactLeg.contact_system_id == "test")
                            .first())
                contact = call_leg.contact
                assert contact.secured_key == "632776ab"
                assert contact.secured > start_time
                assert contact.secured < end_time


class TestTwilioBadInputs(TestSecureCallTwilio):
    @time_machine.travel("2020-12-29 19:00")
    def test_bad_inputs(self, db_session, workflow, greeting, call_routing, test_client,
                        mock_init_workflow, mock_enter_dob, mock_enter_ssn):
        with patch.object(CustomerLookupFieldLookupService, "get_field_by_lookup_key", return_value=71568378):
            with patch.object(WorkflowRunnerService, "run_step", return_value=mock_init_workflow.json()):
                init_form = {"CallSid": "bad_input_test",
                             "To": "+15555555555",
                             "From": "+155555555556"}
                initial_response = test_client.post("/api/v1/twilio/new", data=init_form)

                assert initial_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello from <phoneme alp'
                    b'habet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say><Say>For securi'
                    b'ty and faster service, we would like to verify some information.</Say><Gathe'
                    b'r action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="8" '
                    b'timeout="6"><Say>Please enter your full 8-digit date of birth.</Say></Gather'
                    b'></Response>')

                birthday_form = {"CallSid": "bad_input_test",
                                 "To": "+15555555555",
                                 "From": "+155555555556",
                                 "Digits": "11222100"}

                second_response = test_client.post("/api/v1/twilio/continue", data=birthday_form)

                assert second_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/cont'
                    b'inue" actionOnEmptyResult="true" numDigits="8" timeout="6"><Say>Unfortunately we did not receive a re'
                    b'sponse or were unable to process your request.</Say><Say>Please enter your '
                    b'full 8-digit date of birth.</Say></Gather></Response>')
                # Testing Encrypted state and error handling
                sr: StepRun = db_session.query(StepRun).order_by(StepRun.created_at.desc()).first()
                assert sr.workflow_run.session is not None
                # TODO: Check customer id?
                assert sr.state.error
                assert sr.state.retryable

                third_response = test_client.post("/api/v1/twilio/continue", data=birthday_form)

                assert third_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/cont'
                    b'inue" actionOnEmptyResult="true" numDigits="8" timeout="6"><Say>Unfortunately we did not receive a re'
                    b'sponse or were unable to process your request.</Say><Say>Please enter your '
                    b'full 8-digit date of birth.</Say></Gather></Response>')

                fourth_response = test_client.post("/api/v1/twilio/continue", data=birthday_form)

                assert fourth_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Dial>12345678901</Dial></R' \
                                               b'esponse>'
