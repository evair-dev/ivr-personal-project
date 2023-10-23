import datetime
from datetime import date

import pytest
import time_machine
from sqlalchemy import orm
from sqlalchemy.orm import Session as SQLAlchemySession

from ivr_gateway.exit_paths import HangUpExitPath, QueueExitPath
from ivr_gateway.models.contacts import Greeting, InboundRouting, TransferRouting, ContactLeg
from ivr_gateway.models.enums import TransferType
from ivr_gateway.models.queues import Queue, QueueHoliday
from ivr_gateway.models.workflows import Workflow
from ivr_gateway.services.queues import QueueService
from ivr_gateway.steps.api.v1 import InputActionStep, NoopStep, BranchMapWorkflowStep
from ivr_gateway.steps.config import StepTree, StepBranch, Step
from tests.factories import workflow as wcf
from tests.factories import queues as qf


class TestQueueOperatingModes:

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
    def queue_service(self, db_session: orm.Session):
        return QueueService(db_session)

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
            name="Iivr.LN.ANY", transfer_routings=[])
        return queue

    @pytest.fixture
    def Iivr_any_after_hours_queue(self, db_session, queue_service: QueueService) -> Queue:

        queue = qf.queue_factory(db_session).create(
            name="Iivr.LN.ANY.AH", hours_of_operation=[])
        for i in range(7):
            queue_service.add_hours_of_operations_for_day(queue, i, "0000", "0800")
        return queue

    @pytest.fixture
    def Iivr_any_queue_with_holiday(self, db_session, Iivr_any_queue, queue_service: QueueService):
        traveller = time_machine.travel("2020-12-23 19:00")
        traveller.start()
        queue_service.add_holiday_for_queue(Iivr_any_queue, "Christmas", date(2020, 12, 25))
        traveller.stop()
        return Iivr_any_queue

    @pytest.fixture
    def Iivr_any_queue_with_holiday_with_hours(self, db_session, Iivr_any_queue, queue_service: QueueService):
        traveller = time_machine.travel("2020-12-23 19:00")
        traveller.start()
        queue_service.add_holiday_for_queue(Iivr_any_queue, "Christmas", date(2020, 12, 25),
                                            start_time=datetime.time(10), end_time=datetime.time(20))
        traveller.stop()
        return Iivr_any_queue

    @pytest.fixture
    def Iivr_any_queue_with_holiday_message(self, db_session, Iivr_any_queue):
        queue_holiday = QueueHoliday()
        queue_holiday.name = "Christmas"
        queue_holiday.message = "Merry Christmas, we are closed."
        queue_holiday.date = date(2020, 12, 25)
        queue_holiday.queue = Iivr_any_queue

        Iivr_any_queue.holidays = [queue_holiday]

        db_session.add(queue_holiday)
        db_session.add(Iivr_any_queue)
        db_session.commit()

        return Iivr_any_queue

    @pytest.fixture
    def Iivr_any_queue_emergency_mode_on(self, db_session, Iivr_any_queue) -> Queue:
        Iivr_any_queue.emergency_mode = True
        db_session.add(Iivr_any_queue)
        db_session.commit()
        return Iivr_any_queue

    @pytest.fixture
    def Iivr_any_queue_emergency_on_custom_message(self, db_session, Iivr_any_queue_emergency_mode_on) -> Queue:
        Iivr_any_queue_emergency_mode_on.emergency_message = "There is an emergency."
        db_session.add(Iivr_any_queue_emergency_mode_on)
        db_session.commit()
        return Iivr_any_queue_emergency_mode_on

    @pytest.fixture
    def transfer_secured_routing(self, db_session, Iivr_any_queue: Queue) -> TransferRouting:
        transfer_routing = TransferRouting(
            transfer_type=TransferType.PSTN,
            destination="773-695-2581",
            destination_system="DR Cisco",
            operating_mode="normal",
            queue=Iivr_any_queue
        )
        db_session.add(transfer_routing)
        db_session.commit()
        return transfer_routing

    @pytest.fixture
    def transfer_to_after_hours_queue_routing(self, db_session, Iivr_any_queue: Queue,
                                              Iivr_any_after_hours_queue: Queue) -> TransferRouting:
        transfer_routing = TransferRouting(
            transfer_type=TransferType.QUEUE,
            destination=Iivr_any_after_hours_queue.name,
            destination_system="IVR Gateway",
            operating_mode="normal",
            queue=Iivr_any_queue,
            priority=10
        )
        db_session.add(transfer_routing)
        db_session.commit()
        return transfer_routing

    @pytest.fixture
    def transfer_after_hours_queue_routing(self, db_session, Iivr_any_after_hours_queue: Queue) -> TransferRouting:
        transfer_routing = TransferRouting(
            transfer_type=TransferType.PSTN,
            destination="773-695-2582",
            destination_system="DR Cisco",
            operating_mode="normal",
            queue=Iivr_any_after_hours_queue
        )
        db_session.add(transfer_routing)
        db_session.commit()
        return transfer_routing

    @pytest.fixture
    def Iivr_unsecured_any_queue(self, db_session, queue_service: QueueService) -> Queue:
        queue = qf.queue_factory(db_session).create(
            name="Iivr.unsecured.ANY")
        return queue

    @pytest.fixture
    def transfer_unsecured_routing(self, db_session, Iivr_unsecured_any_queue: Queue) -> TransferRouting:
        transfer_routing = TransferRouting(
            transfer_type=TransferType.PSTN,
            destination="800-480-8576",
            destination_system="DR Cisco",
            operating_mode="normal",
            queue=Iivr_unsecured_any_queue
        )
        db_session.add(transfer_routing)
        db_session.commit()
        return transfer_routing

    @time_machine.travel("2020-12-29 19:00")
    def test_no_transfer_routing(self, db_session, workflow, greeting, call_routing, Iivr_any_queue, test_client):
        call_form = {"CallSid": "test1",
                     "To": "+15555555555",
                     "Digits": "1"}
        test_client.post("/api/v1/twilio/new", data=call_form)
        call_second_response = test_client.post("/api/v1/twilio/continue", data=call_form)
        assert call_second_response.data == (b'<?xml version="1.0" encoding="UTF-8"?><Response>'
                                             b'<Say>I\'m sorry but there\'s been an unrecoverable exception, '
                                             b'Goodbye</Say><Hangup /></Response>')

        call_leg = db_session.query(ContactLeg).filter(ContactLeg.contact_system_id == "test1").first()
        assert call_leg.disposition_type == "ivr_gateway.exit_paths.QueueExitPath"
        assert call_leg.disposition_kwargs == {
            "queue_name": "Iivr.LN.ANY",
            "error": "missing transfer routing"
        }


    @time_machine.travel("2020-12-29 19:00")
    def test_new_call_during_business_hours(self, db_session, workflow, greeting, call_routing,
                                            transfer_secured_routing,
                                            transfer_unsecured_routing, test_client):
        first_call_form = {"CallSid": "test1",
                           "To": "+15555555555",
                           "Digits": "1"}
        first_call_first_response = test_client.post("/api/v1/twilio/new", data=first_call_form)
        assert first_call_first_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello from <phoneme alp'
            b'habet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say><Gather action='
            b'"/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>Please enter a number</Say></Gather></'
            b'Response>')

        second_call_form = {"CallSid": "test2",
                            "To": "+15555555555",
                            "Digits": "2"}
        second_call_first_response = test_client.post("/api/v1/twilio/new", data=second_call_form)
        assert first_call_first_response.data == second_call_first_response.data
        first_call_second_response = test_client.post("/api/v1/twilio/continue", data=first_call_form)
        assert first_call_second_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Dial>773-695-2581</Dial></Re' \
                                                  b'sponse>'
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

        call_leg = db_session.query(ContactLeg).filter(ContactLeg.contact_system_id == "test1").first()
        assert call_leg.disposition_type == "ivr_gateway.exit_paths.QueueExitPath"
        assert call_leg.disposition_kwargs == {
            "queue_name": "Iivr.LN.ANY",
            "operating_mode": "normal"
        }

    @time_machine.travel("2020-12-30 02:00")
    def test_new_after_hours_call(self, db_session, workflow, greeting, call_routing, transfer_secured_routing,
                                  transfer_unsecured_routing, test_client):
        first_call_form = {"CallSid": "test1",
                           "To": "+15555555555",
                           "Digits": "1"}
        first_call_first_response = test_client.post("/api/v1/twilio/new", data=first_call_form)
        assert first_call_first_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello from <phoneme alp'
            b'habet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say><Gather action='
            b'"/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>Please enter a number</Say></Gather></'
            b'Response>')

        first_call_second_response = test_client.post("/api/v1/twilio/continue", data=first_call_form)
        assert first_call_second_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Say><break time="500ms" /> We are currently close'
            b'd. Please try us back during our normal business hours of 7am-10pm central time. We '
            b'apologize for this inconvenience and look forward to speaking with you then.'
            b'</Say><Hangup /></Response>')

        call_leg = db_session.query(ContactLeg).filter(ContactLeg.contact_system_id == "test1").first()
        assert call_leg.disposition_type == "ivr_gateway.exit_paths.QueueExitPath"
        assert call_leg.disposition_kwargs == {
            "queue_name": "Iivr.LN.ANY",
            "operating_mode": "closed"
        }

    @time_machine.travel("2020-12-29 19:00")
    def test_system_emergency_call(self, monkeypatch, db_session, workflow, greeting, call_routing,
                                   transfer_secured_routing,
                                   transfer_unsecured_routing, Iivr_any_queue, test_client):

        monkeypatch.setenv("IVR_IVR_SYSTEM_EMERGENCY_MODE", "true")
        call_form = {"CallSid": "test1",
                     "To": "+15555555555",
                     "Digits": "1"}
        response = test_client.post("/api/v1/twilio/new", data=call_form)
        assert response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Say> Due to unforeseen circumstances'
            b' our customer support center is currently closed and we\'re unable to take your call.'
            b' We apologize for any inconvenience this may have caused you. Please check our website'
            b' at www.Iivr.com for further updates or try your call again later. </Say><Hangup /></Response>')

    @time_machine.travel("2020-12-29 19:00")
    def test_emergency_call_no_custom_message(self, db_session, workflow, greeting, call_routing,
                                              transfer_secured_routing, transfer_unsecured_routing,
                                              test_client, Iivr_any_queue_emergency_mode_on):
        call_form = {"CallSid": "test1",
                     "To": "+15555555555",
                     "Digits": "1"}
        test_client.post("/api/v1/twilio/new", data=call_form)
        call_second_response = test_client.post("/api/v1/twilio/continue", data=call_form)
        assert call_second_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Say> Due to unforeseen circumstances'
            b' our customer support center is currently closed and we\'re unable to take your call. '
            b'We apologize for any inconvenience this may have caused you. Please check our website at '
            b'www.Iivr.com for further updates or try your call again later. </Say><Hangup /></Response>')

        call_leg = db_session.query(ContactLeg).filter(ContactLeg.contact_system_id == "test1").first()
        assert call_leg.disposition_type == "ivr_gateway.exit_paths.QueueExitPath"
        assert call_leg.disposition_kwargs == {
            "queue_name": "Iivr.LN.ANY",
            "operating_mode": "emergency"
        }

    @time_machine.travel("2020-12-29 19:00")
    def test_emergency_call_custom_message(self, db_session, workflow, greeting, call_routing,
                                           transfer_secured_routing, transfer_unsecured_routing,
                                           test_client, Iivr_any_queue_emergency_on_custom_message):
        call_form = {"CallSid": "test1",
                     "To": "+15555555555",
                     "Digits": "1"}
        test_client.post("/api/v1/twilio/new", data=call_form)
        call_second_response = test_client.post("/api/v1/twilio/continue", data=call_form)
        assert call_second_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>There is an emergency.</Say><Hangup /></Response>')

        call_leg = db_session.query(ContactLeg).filter(ContactLeg.contact_system_id == "test1").first()
        assert call_leg.disposition_type == "ivr_gateway.exit_paths.QueueExitPath"
        assert call_leg.disposition_kwargs == {
            "queue_name": "Iivr.LN.ANY",
            "operating_mode": "emergency"
        }

    def test_holiday_mode(self, db_session, workflow, greeting, call_routing, transfer_secured_routing,
                          transfer_unsecured_routing, Iivr_any_queue_with_holiday, test_client):

        traveller = time_machine.travel("2020-12-25 19:00")
        traveller.start()
        first_call_form = {"CallSid": "test1",
                           "To": "+15555555555",
                           "Digits": "1"}
        test_client.post("/api/v1/twilio/new", data=first_call_form)
        first_call_second_response = test_client.post("/api/v1/twilio/continue", data=first_call_form)
        traveller.stop()

        assert first_call_second_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Say><break time="500ms" /> We are currently' \
            b' closed. Please try us back during our normal business hours of 7am-10pm central time.' \
            b' We apologize for this inconvenience and look forward to speaking with you then.' \
            b'</Say><Hangup /></Response>')

        call_leg = db_session.query(ContactLeg).filter(ContactLeg.contact_system_id == "test1").first()
        assert call_leg.disposition_type == "ivr_gateway.exit_paths.QueueExitPath"
        assert call_leg.disposition_kwargs == {
            "queue_name": "Iivr.LN.ANY",
            "operating_mode": "holiday"
        }

    @time_machine.travel("2020-12-25 19:00")
    def test_holiday_mode_with_message(self, db_session, workflow, greeting, call_routing, transfer_secured_routing,
                                       transfer_unsecured_routing, Iivr_any_queue_with_holiday_message, test_client):

        call_form = {"CallSid": "test1",
                     "To": "+15555555555",
                     "Digits": "1"}
        test_client.post("/api/v1/twilio/new", data=call_form)
        call_second_response = test_client.post("/api/v1/twilio/continue", data=call_form)

        assert call_second_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Merry Christmas, we are closed.</Say><Hangup /></Response>'

        call_leg = db_session.query(ContactLeg).filter(ContactLeg.contact_system_id == "test1").first()
        assert call_leg.disposition_type == "ivr_gateway.exit_paths.QueueExitPath"
        assert call_leg.disposition_kwargs == {
            "queue_name": "Iivr.LN.ANY",
            "operating_mode": "holiday"
        }

    @time_machine.travel("2020-12-30 09:00")
    def test_new_after_hours_call_with_after_hours_queue_open(self, db_session, workflow, greeting, call_routing,
                                                              transfer_secured_routing,
                                                              transfer_unsecured_routing,
                                                              transfer_to_after_hours_queue_routing,
                                                              transfer_after_hours_queue_routing, test_client):
        first_call_form = {"CallSid": "test1",
                           "To": "+15555555555",
                           "Digits": "1"}
        first_call_first_response = test_client.post("/api/v1/twilio/new", data=first_call_form)
        assert first_call_first_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello from <phoneme alp'
            b'habet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say><Gather action='
            b'"/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>Please enter a number</Say></Gather></'
            b'Response>')

        first_call_second_response = test_client.post("/api/v1/twilio/continue", data=first_call_form)
        assert first_call_second_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Dial>773-695-2582</Dial></Re'
            b'sponse>')

        call_leg = db_session.query(ContactLeg).filter(ContactLeg.contact_system_id == "test1").first()
        assert call_leg.disposition_type == "ivr_gateway.exit_paths.QueueExitPath"
        assert call_leg.disposition_kwargs == {
            "queue_name": "Iivr.LN.ANY",
            "operating_mode": "closed",
            "final_queue": "Iivr.LN.ANY.AH"
        }

    @time_machine.travel("2020-12-30 02:00")
    def test_new_after_hours_call_with_after_hours_queue_closed(self, db_session, workflow, greeting, call_routing,
                                                                transfer_secured_routing,
                                                                transfer_unsecured_routing,
                                                                transfer_to_after_hours_queue_routing,
                                                                transfer_after_hours_queue_routing, test_client):
        first_call_form = {"CallSid": "test1",
                           "To": "+15555555555",
                           "Digits": "1"}
        first_call_first_response = test_client.post("/api/v1/twilio/new", data=first_call_form)
        assert first_call_first_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello from <phoneme alp'
            b'habet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say><Gather action='
            b'"/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>Please enter a number</Say></Gather></'
            b'Response>')

        first_call_second_response = test_client.post("/api/v1/twilio/continue", data=first_call_form)
        assert first_call_second_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Say><break time="500ms" /> We are currently close'
            b'd. Please try us back during our normal business hours of 7am-10pm central time. We '
            b'apologize for this inconvenience and look forward to speaking with you then.'
            b'</Say><Hangup /></Response>')

        call_leg = db_session.query(ContactLeg).filter(ContactLeg.contact_system_id == "test1").first()
        assert call_leg.disposition_type == "ivr_gateway.exit_paths.QueueExitPath"
        assert call_leg.disposition_kwargs == {
            "queue_name": "Iivr.LN.ANY",
            "operating_mode": "closed"
        }

    @time_machine.travel("2020-12-30 19:00")
    def test_new_normal_hours_call_with_after_hours_queue(self, db_session, workflow, greeting, call_routing,
                                                          transfer_secured_routing,
                                                          transfer_unsecured_routing,
                                                          transfer_to_after_hours_queue_routing,
                                                          transfer_after_hours_queue_routing, test_client):
        first_call_form = {"CallSid": "test1",
                           "To": "+15555555555",
                           "Digits": "1"}
        first_call_first_response = test_client.post("/api/v1/twilio/new", data=first_call_form)
        assert first_call_first_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello from <phoneme alp'
            b'habet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say><Gather action='
            b'"/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>Please enter a number</Say></Gather></'
            b'Response>')

        first_call_second_response = test_client.post("/api/v1/twilio/continue", data=first_call_form)
        assert first_call_second_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Dial>773-695-2581</Dial></Re'
            b'sponse>')

        call_leg = db_session.query(ContactLeg).filter(ContactLeg.contact_system_id == "test1").first()
        assert call_leg.disposition_type == "ivr_gateway.exit_paths.QueueExitPath"
        assert call_leg.disposition_kwargs == {
            "queue_name": "Iivr.LN.ANY",
            "operating_mode": "normal"
        }
