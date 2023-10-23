import pytest
import time_machine
from sqlalchemy.orm import Session as SQLAlchemySession

from ivr_gateway.models.contacts import Greeting, InboundRouting
from ivr_gateway.models.queues import Queue
from ivr_gateway.models.workflows import Workflow, WorkflowRun

from tests.factories import workflow as wcf
from tests.factories import queues as qf
from step_trees.shared.ivr.noop_queue_transfer import noop_queue_transfer_step_tree
from tests.factories.helper_functions import compare_step_branches


class HandleIncomingDepositsFixtures:

    @pytest.fixture
    def workflow(self, db_session: SQLAlchemySession) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "noop_queue_transfer",
                                                step_tree=noop_queue_transfer_step_tree)
        return workflow_factory.create()

    @pytest.fixture
    def greeting(self, db_session) -> Greeting:
        greeting = Greeting(message='Thank you for calling <phoneme alphabet="ipa" ph="əˈvɑnt">Iivr</phoneme>.  '
                                    'Please be advised that your call will be monitored or recorded for quality and '
                                    'training purposes.')
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


class TestNoopQueueTransfer(HandleIncomingDepositsFixtures):

    @time_machine.travel("2020-12-29 19:00")
    def test_handle_incoming_call(self, db_session, call_routing, test_client):
        init_form = {"CallSid": "test",
                     "To": "+15555555555",
                     "Digits": ""}

        initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
        assert initial_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Thank you for calling <'
            b'phoneme alphabet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.  Please b'
            b'e advised that your call will be monitored or recorded for quality and train'
            b'ing purposes.</Say><Dial>12345678901</Dial></Response>'
        )

        correct_branch_sequence = [
            "root"
        ]
        workflow_run: WorkflowRun = db_session.query(WorkflowRun).first()
        compare_step_branches(correct_branch_sequence, workflow_run)

    @time_machine.travel("2020-12-29 23:00")
    def test_handle_incoming_call_closed(self, db_session, call_routing, test_client):
        init_form = {"CallSid": "test",
                     "To": "+15555555555",
                     "Digits": ""}

        initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
        assert initial_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Thank you for calling <'
            b'phoneme alphabet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.  Please b'
            b'e advised that your call will be monitored or recorded for quality and train'
            b'ing purposes.</Say><Say><break time="500ms" /> We are currently closed. Plea'
            b'se try us back during our normal business hours of 7am-10pm central time. We'
            b' apologize for this inconvenience and look forward to speaking with you then'
            b'.</Say><Hangup /></Response>'
        )

        correct_branch_sequence = [
            "root"
        ]
        workflow_run: WorkflowRun = db_session.query(WorkflowRun).first()
        compare_step_branches(correct_branch_sequence, workflow_run)
