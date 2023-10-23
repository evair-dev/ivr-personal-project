from unittest.mock import Mock, patch
from uuid import uuid4
import time_machine

import pytest
import requests
from sqlalchemy.orm import Session as SQLAlchemySession

from ivr_gateway.models.contacts import Contact, ContactLeg, Greeting, InboundRouting, TransferRouting
from ivr_gateway.models.enums import TransferType
from ivr_gateway.models.queues import Queue
from ivr_gateway.models.workflows import Workflow, WorkflowRun
from tests.factories import queues as qf

from tests.factories import workflow as wcf
from step_trees.shared.ivr.telco_customer_lookup import ivr_telco_customer_lookup


class TestIVRTelcoCustomerLookup:

    @pytest.fixture
    def workflow(self, db_session: SQLAlchemySession) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "ivr_customer_lookup", step_tree=ivr_telco_customer_lookup)
        return workflow_factory.create()

    @pytest.fixture
    def Iivr_any_queue(self, db_session) -> Queue:
        queue = qf.queue_factory(db_session).create(
            name="Iivr.LN.ANY", transfer_routings=[])
        return queue

    @pytest.fixture
    def call(self, db_session) -> Contact:
        call = Contact(global_id=str(uuid4()), session={}, device_identifier="6637469788")
        db_session.add(call)
        db_session.commit()
        return call

    @pytest.fixture
    def call_leg(self, db_session, call: Contact, Iivr_any_queue: Queue) -> ContactLeg:
        call_leg = ContactLeg(
            contact=call,
            ani="6637469788",
            contact_system="test",
            contact_system_id="test",
            initial_queue=Iivr_any_queue
        )
        db_session.add(call_leg)
        db_session.commit()
        return call_leg

    @pytest.fixture
    def greeting(self, db_session) -> Greeting:
        greeting = Greeting(message='hello from <phoneme alphabet="ipa" ph="əˈvɑnt">Iivr</phoneme>.')
        db_session.add(greeting)
        db_session.commit()
        return greeting

    @pytest.fixture
    def call_routing(self, db_session, workflow: Workflow, greeting: Greeting, Iivr_any_queue: Queue) -> InboundRouting:
        call_routing = InboundRouting(
            inbound_target="15555555555",
            workflow=workflow,
            active=True,
            greeting=greeting,
            operating_mode="normal",
            initial_queue=Iivr_any_queue
        )
        db_session.add(call_routing)
        db_session.commit()
        return call_routing

    @pytest.fixture
    def transfer_to_any_queue_routing(self, db_session, Iivr_any_queue: Queue) -> TransferRouting:
        transfer_routing = TransferRouting(
            transfer_type=TransferType.QUEUE,
            destination=Iivr_any_queue.name,  # this transfer routing actually transfers to itself
            destination_system="ivr-gateway",
            operating_mode="normal",
            queue=Iivr_any_queue,
            priority=10
        )
        db_session.add(transfer_routing)
        db_session.commit()
        return transfer_routing

    @pytest.fixture
    def mock_telco_customer_lookup(self) -> Mock:
        mock_lookup = Mock()
        mock_lookup.text = """<?xml version="1.0" encoding="UTF-8"?>
                              <result>
                                  <success>true</success>
                                  <customer_id>123456789</customer_id>
                                  <queue>customers</queue>
                                  <screen_pop>https://admin.Iivr.com/us/customers/123456789/</screen_pop>
                                  <product_id>3942467</product_id>
                                  <product_type>loan</product_type>
                                  <product_status>late</product_status>
                              </result>"""
        return mock_lookup

    @time_machine.travel("2020-12-29 19:00")
    def test_ivr_telco_customer_lookup(self, db_session, monkeypatch, test_client, workflow,
                                       Iivr_any_queue, call, transfer_to_any_queue_routing,
                                       call_leg, call_routing, greeting, mock_telco_customer_lookup):
        monkeypatch.setenv("IVR_AMOUNT_BASE_URL", "www.amount.Iivr.com")
        monkeypatch.setenv("TELCO_API_PATH", "api/path")

        with patch.object(requests, "post", side_effect=[mock_telco_customer_lookup]):
            init_form = {"CallSid": "test",
                         "To": "+15555555555",
                         "From": "+16637469788"}

            initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
            workflow_run: WorkflowRun = db_session.query(WorkflowRun).first()
            assert workflow_run.session["customer_id"] == "123456789"
            assert initial_response.data == \
                   b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello from <phoneme alphab' \
                   b'et="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say></Response>'
