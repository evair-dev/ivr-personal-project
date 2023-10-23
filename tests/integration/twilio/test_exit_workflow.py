import pytest
import time_machine
from sqlalchemy.orm import Session as SQLAlchemySession

from ivr_gateway.exit_paths import HangUpExitPath, QueueExitPath
from ivr_gateway.models.contacts import Greeting, InboundRouting, Contact
from ivr_gateway.models.queues import Queue
from ivr_gateway.models.workflows import Workflow
from tests.factories import queues as qf
from ivr_gateway.steps.api.v1 import InputActionStep, NoopStep, BranchMapWorkflowStep
from ivr_gateway.steps.config import StepTree, StepBranch, Step
from tests.factories import workflow as wcf


class TestTwilio:

    @pytest.fixture
    def workflow(self, db_session: SQLAlchemySession) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "main_menu", step_tree=StepTree(
            branches=[
                StepBranch(
                    name="root",
                    steps=[
                        Step(
                            name="step-1",
                            step_type=InputActionStep.get_type_string(),
                            step_kwargs={
                                "name": "enter_number",
                                "input_key": "number",
                                "input_prompt": "Please enter a number",
                                "expected_length": 1,
                                "actions": [{
                                    "name": "opt-1", "display_name": "Option 1"
                                }, {
                                    "name": "opt-2", "display_name": "Option 2"
                                }, {
                                    "name": "opt-3", "display_name": "Option 3"
                                }],
                            },
                        ),
                        Step(
                            name="step-2",
                            step_type=BranchMapWorkflowStep.get_type_string(),
                            step_kwargs={
                                "field": "step[root:step-1].input.value",
                                "on_error_reset_to_step": "step-2",
                                "branches": {
                                    "opt-1": "branch-1",
                                    "opt-2": "branch-2",
                                    "opt-3": "branch-3",
                                },
                            },
                        ),
                    ]
                ),
                StepBranch(
                    name="branch-1",
                    steps=[
                        Step(
                            name="step-2",
                            step_type=NoopStep.get_type_string(),
                            step_kwargs={
                            },
                            exit_path={
                                "exit_path_type": QueueExitPath.get_type_string(),
                                "exit_path_kwargs": {
                                    "queue_name": "Iivr.LN.ANY",
                                }
                            },
                        )]
                ),
                StepBranch(
                    name="branch-2",
                    steps=[
                        Step(
                            name="step-2",
                            step_type=NoopStep.get_type_string(),
                            step_kwargs={
                            },
                            exit_path={
                                "exit_path_type": QueueExitPath.get_type_string(),
                                "exit_path_kwargs": {
                                    "queue_name": "Iivr.unsecured.ANY",
                                }
                            },
                        )]
                ),
                StepBranch(
                    name="branch-3",
                    steps=[
                        Step(
                            name="step-2",
                            step_type=NoopStep.get_type_string(),
                            step_kwargs={
                            },
                            exit_path={
                                "exit_path_type": HangUpExitPath.get_type_string(),
                            },
                        )]
                ),
            ]
        ))
        return workflow_factory.create()

    @pytest.fixture
    def greeting(self, db_session) -> Greeting:
        greeting = Greeting(message='hello from <phoneme alphabet="ipa" ph="əˈvɑnt">Iivr</phoneme>.')
        db_session.add(greeting)
        db_session.commit()
        return greeting

    @pytest.fixture
    def call_routing(self, db_session, workflow: Workflow, greeting: Greeting) -> InboundRouting:
        call_routing = InboundRouting(
            inbound_target="15555555555",
            workflow=workflow,
            active=True,
            greeting=greeting,
            operating_mode="normal"
        )
        db_session.add(call_routing)
        db_session.commit()
        return call_routing

    @pytest.fixture
    def Iivr_any_queue(self, db_session) -> Queue:
        queue = qf.queue_factory(db_session).create(
            name="Iivr.LN.ANY",
            transfer_routings=[{
                "transfer_type": "PSTN",
                "destination": "773-695-2581",
                "destination_system": "DR Cisco"
            }]
        )
        return queue

    @pytest.fixture
    def Iivr_unsecured_any_queue(self, db_session) -> Queue:
        queue = qf.queue_factory(db_session).create(
            name="Iivr.unsecured.ANY",
            transfer_routings=[{
                "transfer_type": "PSTN",
                "destination": "800-480-8576",
                "destination_system": "DR Cisco"
            }]
        )
        return queue


    @time_machine.travel("2020-12-29 19:00")
    def test_new_call(self, db_session, workflow, greeting, call_routing, Iivr_any_queue,
                      Iivr_unsecured_any_queue, test_client):
        first_call_form = {"CallSid": "test1",
                "To": "+15555555555",
                "Digits": "1"}
        first_call_first_response = test_client.post("/api/v1/twilio/new", data=first_call_form)
        assert first_call_first_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello from <phoneme alp' \
                                                 b'habet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say><Gather action=' \
                                                 b'"/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>Please enter a number</Say></Gather></' \
                                                 b'Response>'
        second_call_form = {"CallSid": "test2",
                "To": "+15555555555",
                "Digits": "2"}
        second_call_first_response = test_client.post("/api/v1/twilio/new", data=second_call_form)
        assert first_call_first_response.data == second_call_first_response.data
        first_call_second_response = test_client.post("/api/v1/twilio/continue", data=first_call_form)
        assert first_call_second_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Dial>773-695-2581</Dial></Re' \
                                       b'sponse>'
        call = db_session.query(Contact).filter(Contact.global_id == "twilio:test1").first()
        first_workflow_run = call.contact_legs[0].workflow_run
        assert first_workflow_run.exit_path_type == QueueExitPath.get_type_string()
        assert first_workflow_run.exit_path_kwargs == {'queue_name': 'Iivr.LN.ANY'}
        third_call_form = {"CallSid": "test3",
                            "To": "+15555555555",
                            "Digits": "3"}
        third_call_first_response = test_client.post("/api/v1/twilio/new", data=third_call_form)
        assert third_call_first_response.data == second_call_first_response.data
        second_call_second_response = test_client.post("/api/v1/twilio/continue", data=second_call_form)
        assert second_call_second_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Dial>800-480-8576</Dial></Re' \
                                                   b'sponse>'
        third_call_second_response = test_client.post("/api/v1/twilio/continue", data=third_call_form)
        assert third_call_second_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Hangup /></Response>'
