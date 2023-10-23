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
from tests.fixtures.step_trees.ingress import ingress_step_tree


class TestNoCustomerIngressTwilio:

    @pytest.fixture
    def workflow(self, db_session: SQLAlchemySession) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "ingress", step_tree=ingress_step_tree)
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
            name="AFC.CC.PAY.INT")
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
            "error": "Customer with phone number 5555555555 not found."
        }
        mock_telco.status_code = 200
        return mock_telco

    @time_machine.travel("2020-12-29 19:00")
    def test_new_call(self, db_session, workflow, greeting, call_routing, test_client,
                      mock_customer_lookup, queue):
        with patch.object(requests, "get", return_value=mock_customer_lookup):
            init_form = {"CallSid": "test",
                         "To": "+15555555555",
                         "From": "+155555555556",
                         "Digits": "1234"}

            initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
            assert initial_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello from <phoneme alp'
                b'habet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say><Dial>12345678901</Dial></Response>')

            call_legs = db_session.query(ContactLeg).filter(ContactLeg.contact_system_id == "test").all()
            assert len(call_legs) == 1
            assert call_legs[0].workflow_run.current_queue.name == "AFC.CC.PAY.INT"
