import os
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
import requests

from ivr_gateway.models.contacts import Contact, ContactLeg
from ivr_gateway.models.queues import Queue
from ivr_gateway.services.amount.telco import TelcoService
from tests.factories import queues as qf


class TestTelcoService:

    @pytest.fixture
    def Iivr_any_queue(self, db_session) -> Queue:
        queue = qf.queue_factory(db_session).create(
            name="Iivr.LN.ANY")
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
    def call_without_partner(self, db_session) -> Contact:
        call = Contact(global_id=str(uuid4()), session={}, device_identifier="6637469789")
        db_session.add(call)
        db_session.commit()
        return call

    @pytest.fixture
    def telco_response(self) -> str:
        return """<?xml version="1.0" encoding="UTF-8"?>
                <result>
                    <success>true</success>
                    <customer_id>123456789</customer_id>
                    <queue>customers</queue>
                    <screen_pop>https://admin.Iivr.com/us/customers/181157761/</screen_pop>
                    <product_id>3942467</product_id>
                    <product_type>loan</product_type>
                    <product_status>late</product_status>
                </result>"""

    @pytest.fixture
    def telco_fail_response(self) -> str:
        return """<?xml version="1.0" encoding="UTF-8"?>
                <result>
                    <success>false</success>
                </result>"""

    def test_customer_search(self, db_session, monkeypatch, call, call_leg, telco_response):
        monkeypatch.setenv("IVR_AMOUNT_BASE_URL", "www.amount.Iivr.com")
        monkeypatch.setenv("TELCO_API_PATH", "api/path")

        mock_telco = Mock()
        mock_telco.text = telco_response
        with patch.object(requests, "post", return_value=mock_telco) as mock_post:
            telco_service = TelcoService(db_session, call)
            customer_id = telco_service.search_client_info(call)
            assert customer_id == "123456789"
            assert call.customer_id == '123456789'
            assert call.session["telco"]["customer_id"] == "123456789"
            product_id = telco_service.field_lookup(call, "product_id")
            assert product_id == "3942467"
            assert mock_post.call_count == 1
            assert mock_post.call_args[1].get("headers") == {"Client-Version": os.getenv('IVR_AMOUNT_CLIENT_VERSION'),
                                                             "Client-Install": os.getenv('IVR_AMOUNT_CLIENT_INSTALL')}

    def test_customer_search_fail(self, db_session, monkeypatch, call, call_leg, telco_fail_response):
        monkeypatch.setenv("IVR_AMOUNT_BASE_URL", "www.amount.Iivr.com")
        monkeypatch.setenv("TELCO_API_PATH", "api/path")

        mock_telco = Mock()
        mock_telco.text = telco_fail_response
        with patch.object(requests, "post", return_value=mock_telco) as mock_post:
            telco_service = TelcoService(db_session, call)
            customer_id = telco_service.search_client_info(call)
            assert customer_id is None
            assert call.customer_id is None
            assert call.session["telco"].get("customer_id") is None
            product_id = telco_service.field_lookup(call, "product_id")
            assert product_id is None
            assert mock_post.call_count == 1

    def test_customer_search_no_partner(self, db_session, monkeypatch, call_without_partner):
        with pytest.raises(TypeError, match="No partner associated with this contact."):
            TelcoService(db_session, call_without_partner)

    def test_customer_search_no_base_url_environment_variable(self, db_session, monkeypatch, call, call_leg):
        monkeypatch.delenv("IVR_AMOUNT_BASE_URL")
        with pytest.raises(TypeError, match="Environment variable IVR_AMOUNT_BASE_URL not found."):
            TelcoService(db_session, call)
