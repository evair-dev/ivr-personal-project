from unittest.mock import Mock, patch

import pytest
import time_machine
from sqlalchemy.orm import Session as SQLAlchemySession

from ivr_gateway.models.contacts import Greeting, InboundRouting
from ivr_gateway.models.queues import Queue
from ivr_gateway.models.steps import StepState
from ivr_gateway.models.workflows import Workflow, WorkflowRun
from ivr_gateway.services.amount.workflow_runner import WorkflowRunnerService
from ivr_gateway.services.workflows.fields import CustomerLookupFieldLookupService
from tests.factories import workflow as wcf
from tests.fixtures.step_trees.secure_call import secure_call_step_tree
from tests.factories import queues as qf


class TestStepStatesCanBeReferencedFromWorkflowStepRuns:
    @pytest.fixture
    def workflow(self, db_session: SQLAlchemySession) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "secure_call", step_tree=secure_call_step_tree)
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

    @time_machine.travel("2020-12-29 19:00")
    def test_bad_inputs(self, db_session, workflow, greeting, call_routing, test_client, mock_init_workflow):
        with patch.object(CustomerLookupFieldLookupService, "get_field_by_lookup_key", return_value=71568378):
            with patch.object(WorkflowRunnerService, "run_step", return_value=mock_init_workflow.json()):
                init_form = {"CallSid": "bad_input_test",
                             "To": "+15555555555",
                             "From": "+155555555556"}
                test_client.post("/api/v1/twilio/new", data=init_form)

                expected_bday1 = "11222100"
                expected_bday2 = "11222200"
                expected_bday3 = "11222300"
                birthday_form = {"CallSid": "bad_input_test",
                                  "To": "+15555555555",
                                  "From": "+155555555556",
                                  "Digits": expected_bday1}
                test_client.post("/api/v1/twilio/continue", data=birthday_form)
                birthday_form["Digits"] = expected_bday2
                test_client.post("/api/v1/twilio/continue", data=birthday_form)
                birthday_form["Digits"] = expected_bday3
                test_client.post("/api/v1/twilio/continue", data=birthday_form)

                workflow_run: WorkflowRun = db_session.query(WorkflowRun).first()
                assert len(workflow_run.workflow_step_runs) == 4
                step_state_resp_1: StepState = workflow_run.workflow_step_runs[1].step_state
                step_state_resp_2 = workflow_run.workflow_step_runs[2].step_state
                step_state_resp_3 = workflow_run.workflow_step_runs[3].step_state
                assert step_state_resp_1.input["value"] == expected_bday1
                assert step_state_resp_2.input["value"] == expected_bday2
                assert step_state_resp_3.input["value"] == expected_bday3

