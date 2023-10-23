from typing import Dict
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
import requests
from datetime import timedelta
from json import JSONDecodeError

from ivr_gateway.models.contacts import Contact, ContactLeg
from ivr_gateway.models.queues import Queue
from ivr_gateway.services.amount.customer_lookup import CustomerLookupService
from tests.factories import queues as qf


class TestCustomerLookupService:

    @pytest.fixture
    def Iivr_any_queue(self, db_session) -> Queue:
        queue = qf.queue_factory(db_session).create(
            name="Iivr.LN.ANY")
        return queue

    @pytest.fixture
    def call(self, db_session) -> Contact:
        call = Contact(global_id=str(uuid4()), session={}, device_identifier="6637469788")
        call.customer_id = "181204026"
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
    def customer_product_dict(self) -> Dict:
        return {
            'open_applications': [],
            'open_products': [
                {
                    "id": 126,
                    "type": "Loan",
                    "funding_date": "2021-06-01",
                    "active_payoff_quote?": False,
                    "product_type": "installment",
                    "product_subtype": "unsecured",
                    "past_due_amount_cents": 18792,
                    "operationally_charged_off?": False,
                    "in_grace_period?": False,
                    "days_late": 112
                },
                {
                    "type": "CreditCardAccount",
                    "id": 144162,
                    "activatable?": False,
                    "credit_available_cents": 175442,
                    "past_due_amount_cents": 17178,
                    "operationally_charged_off?": False,
                    "days_late": None
                },
                {
                    "type": "CreditCardAccount",
                    "id": 144179,
                    "activatable?": False,
                    "credit_available_cents": 36181,
                    "past_due_amount_cents": 0,
                    "operationally_charged_off?": False,
                    "days_late": None
                }
            ]
        }

    @pytest.fixture
    def customer_application_dict(self) -> Dict:
        return {
            'open_applications': [
                {
                    'id': 123025289,
                    'type': 'installment'
                }
            ],
            'open_products': []
        }

    @pytest.fixture
    def empty_customer_dict(self) -> Dict:
        return {
            'open_applications': [],
            'open_products': []
        }

    @pytest.fixture
    def mock_amount_wrong_response_content_type(self) -> Mock:
        mock_response = Mock()
        mock_response.reason = "OK"
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.data = '<!doctype html>'
        mock_response.elapsed = timedelta(seconds=1, milliseconds=500)
        mock_response.json.side_effect = JSONDecodeError(msg="Not jsonable", doc="<!doctype html>", pos=0)
        return mock_response

    def test_customer_search(self, db_session, call, call_leg, customer_product_dict):
        mock_customer = Mock()
        mock_customer.json.return_value = customer_product_dict
        mock_customer.status_code = 200
        with patch.object(requests, "get", return_value=mock_customer) as mock_get:
            customer_lookup_service = CustomerLookupService(db_session, call)
            customer_lookup_service.get_customer_info(call, service_overrides=None, workflow_run=None)
            product_count = customer_lookup_service.open_product_count(call)
            assert product_count == 3
            loan_count = customer_lookup_service.open_product_count(call, product_type="Loan")
            assert loan_count == 1
            card_count = customer_lookup_service.open_product_count(call, product_type="CreditCardAccount")
            assert card_count == 2
            application_count = customer_lookup_service.open_application_count(call)
            assert application_count == 0
            product_id = customer_lookup_service.product_field_lookup(call, "id")
            assert product_id == 126
            loan_days_late = customer_lookup_service.product_field_lookup(call, "days_late", product_type="Loan")
            assert loan_days_late == 112
            card_id = customer_lookup_service.product_field_lookup(call, "id", product_type="CreditCardAccount")
            assert card_id == 144162
            application_id = customer_lookup_service.application_field_lookup(call, "id")
            assert application_id is None
            assert mock_get.call_count == 1

    def test_application_search(self, db_session, call, call_leg, customer_application_dict):
        mock_customer = Mock()
        mock_customer.json.return_value = customer_application_dict
        mock_customer.status_code = 200
        with patch.object(requests, "get", return_value=mock_customer) as mock_get:
            customer_lookup_service = CustomerLookupService(db_session, call)
            product_count = customer_lookup_service.get_customer_info(call, service_overrides=None, workflow_run=None)
            assert product_count == 0
            application_count = customer_lookup_service.open_application_count(call)
            assert application_count == 1
            product_id = customer_lookup_service.product_field_lookup(call, "id")
            assert product_id is None
            application_id = customer_lookup_service.application_field_lookup(call, "id")
            assert application_id == 123025289
            assert mock_get.call_count == 1

    def test_missing_customer_info_search(self, db_session, call, call_leg, empty_customer_dict):
        mock_customer = Mock()
        mock_customer.json.return_value = empty_customer_dict
        mock_customer.status_code = 200
        with patch.object(requests, "get", return_value=mock_customer) as mock_get:
            customer_lookup_service = CustomerLookupService(db_session, call)
            product_count = customer_lookup_service.get_customer_info(call, service_overrides=None, workflow_run=None)
            assert product_count == 0
            application_count = customer_lookup_service.open_application_count(call)
            assert application_count == 0
            product_id = customer_lookup_service.product_field_lookup(call, "id")
            assert product_id is None
            application_id = customer_lookup_service.application_field_lookup(call, "id")
            assert application_id is None
            assert mock_get.call_count == 1

    def test_customer_info_search_non_json_response(self, db_session, call, call_leg, empty_customer_dict,
                                                    mock_amount_wrong_response_content_type):
        with patch.object(requests, "get", side_effect=[mock_amount_wrong_response_content_type]) as mock_get:
            customer_lookup_service = CustomerLookupService(db_session, call)
            product_count = customer_lookup_service.get_customer_info(call, service_overrides=None, workflow_run=None)
            assert product_count == 0
            application_count = customer_lookup_service.open_application_count(call)
            assert application_count == 0
            product_id = customer_lookup_service.product_field_lookup(call, "id")
            assert product_id is None
            application_id = customer_lookup_service.application_field_lookup(call, "id")
            assert application_id is None
            assert mock_get.call_count == 1

    def test_timeout(self, db_session, call, call_leg, customer_application_dict):
        mock_customer = Mock()
        mock_customer.json.return_value = customer_application_dict
        mock_customer.status_code = 200
        request_exception = requests.exceptions.Timeout()
        with patch.object(requests, "get", side_effect=[request_exception, mock_customer]) as mock_get:
            customer_lookup_service = CustomerLookupService(db_session, call)
            product_count = customer_lookup_service.get_customer_info(call, service_overrides=None, workflow_run=None)
            assert product_count == 0
            application_count = customer_lookup_service.open_application_count(call)
            assert application_count == 0
            product_id = customer_lookup_service.product_field_lookup(call, "id")
            assert product_id is None
            application_id = customer_lookup_service.application_field_lookup(call, "id")
            assert application_id is None
            assert mock_get.call_count == 1
            product_count = customer_lookup_service.get_customer_info(call, service_overrides=None, workflow_run=None)
            assert product_count == 0
            application_count = customer_lookup_service.open_application_count(call)
            assert application_count == 1
            product_id = customer_lookup_service.product_field_lookup(call, "id")
            assert product_id is None
            application_id = customer_lookup_service.application_field_lookup(call, "id")
            assert application_id == 123025289
            assert mock_get.call_count == 2
