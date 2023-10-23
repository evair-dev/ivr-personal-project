from unittest.mock import Mock, patch

import pytest
import requests
from datetime import timedelta
from uuid import uuid4
from json import JSONDecodeError

from ivr_gateway.models.contacts import Contact, ContactLeg
from ivr_gateway.models.queues import Queue
from ivr_gateway.models.workflows import WorkflowRun
from ivr_gateway.services.amount.card_activation import CardActivationService
from ivr_gateway.services.vendors import VendorService

from tests.factories import queues as qf


class CallExternalServiceFixtures:

    @pytest.fixture
    def queue(self, db_session) -> Queue:
        queue = qf.queue_factory(db_session).create(
            name="test")
        return queue

    @pytest.fixture
    def contact(self, db_session) -> Contact:
        contact = Contact(global_id=str(uuid4()), session={}, device_identifier="6637469788")
        contact.customer_id = "181204026"
        db_session.add(contact)
        db_session.commit()
        return contact

    @pytest.fixture
    def contact_leg(self, db_session, contact: Contact, queue: Queue) -> ContactLeg:
        contact_leg = ContactLeg(
            contact=contact,
            ani="6637469788",
            contact_system="test",
            contact_system_id="test",
            initial_queue=queue
        )
        db_session.add(contact_leg)
        db_session.commit()
        return contact_leg

    @pytest.fixture
    def mock_amount_token_response(self) -> Mock:
        mock_response = Mock()
        mock_response.json.return_value = {
            "token_type": "Bearer",
            "access_token": "abc",
            "expiration": 11111
        }
        mock_response.reason = "OK"
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.elapsed = timedelta(seconds=1, milliseconds=500)
        return mock_response

    @pytest.fixture
    def mock_amount_response(self) -> Mock:
        mock_response = Mock()
        mock_response.json.return_value = {
            "message": "ok"
        }
        mock_response.reason = "OK"
        mock_response.headers = {"content-type": "application/json"}
        mock_response.elapsed = timedelta(seconds=1, milliseconds=500)
        mock_response.status_code = 200
        return mock_response

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

    @pytest.fixture
    def mock_amount_wrong_ssn_response(self) -> Mock:
        mock_response = Mock()
        mock_response.text = '{"message":"ssn_last_4 does not match"}'
        mock_response.headers = {"content-type": "application/json"}
        mock_response.elapsed = timedelta(seconds=1, milliseconds=500)
        mock_response.status_code = 400
        return mock_response

    @pytest.fixture
    def mock_amount_wrong_card_last_4_response(self) -> Mock:
        mock_response = Mock()
        mock_response.text = '{"message":"card_last_4 does not match"}'
        mock_response.headers = {"content-type": "application/json"}
        mock_response.elapsed = timedelta(seconds=1, milliseconds=500)
        mock_response.status_code = 400
        return mock_response

    @pytest.fixture
    def mock_amount_wrong_ssn_and_card_last_4_response(self) -> Mock:
        mock_response = Mock()
        mock_response.text = '{"message":"card_last_4 does not match, ssn_last_4 does not match"}'
        mock_response.headers = {"content-type": "application/json"}
        mock_response.elapsed = timedelta(seconds=1, milliseconds=500)
        mock_response.status_code = 400
        return mock_response

    @pytest.fixture
    def mock_amount_wrong_credit_card_account_id_response(self) -> Mock:
        mock_response = Mock()
        mock_response.text = '{"message":"Data error - Body format incorrect"}'
        mock_response.headers = {"content-type": "application/json"}
        mock_response.elapsed = timedelta(seconds=1, milliseconds=500)
        mock_response.status_code = 400
        return mock_response

    @pytest.fixture
    def mock_env_card_activation_secret(self, monkeypatch):
        monkeypatch.setenv("IVR_AMOUNT_CARD_ACTIVATION_SECRET", "not_null")


class TestExternalServiceCalls(CallExternalServiceFixtures):

    def test_wrong_amount_get_authentication_token_response_content_type(self, db_session, contact, contact_leg,
                                                                         mock_amount_wrong_response_content_type,
                                                                         mock_env_card_activation_secret):
        with patch.object(requests, "post", side_effect=[mock_amount_wrong_response_content_type]):
            service = CardActivationService(db_session, contact)
            workflow = WorkflowRun()

            workflow.session = {
                "credit_card_account_id": 1,
                "ssn_last_4": "1235",
                "card_last_4": "1234"
            }

            success, msg = service(workflow)
            assert not success
            assert msg == "Card activation failed"

            vendor_service = VendorService(db_session)
            vendor_error_response = vendor_service.get_vendor_error_responses_by_name("amount")[0]
            assert vendor_error_response.status_code == 400
            assert vendor_error_response.error == "Error encountered fetching authentication token. Expected JSON " \
                                                  "format back. Got text/html instead."

    def test_wrong_amount_card_activation_response_content_type(self, db_session, contact, contact_leg,
                                                                mock_amount_token_response,
                                                                mock_amount_wrong_response_content_type,
                                                                mock_env_card_activation_secret):
        with patch.object(requests, "post", side_effect=[mock_amount_token_response,
                                                         mock_amount_wrong_response_content_type]):
            service = CardActivationService(db_session, contact)
            workflow = WorkflowRun()

            workflow.session = {
                "credit_card_account_id": 1,
                "ssn_last_4": "1235",
                "card_last_4": "1234"
            }

            success, msg = service(workflow)
            assert not success
            assert msg == "Card activation failed"

            vendor_service = VendorService(db_session)
            vendor_error_response = vendor_service.get_vendor_error_responses_by_name("amount")[0]
            assert vendor_error_response.status_code == 400
            assert vendor_error_response.error == "Error encountered activating card." \
                                                  " Expected JSON format back. Got text/html instead."

    def test_wrong_ssn_input(self, db_session, contact, contact_leg, mock_amount_token_response,
                             mock_amount_wrong_ssn_response,
                             mock_env_card_activation_secret):
        with patch.object(requests, "post", side_effect=[mock_amount_token_response,
                                                         mock_amount_wrong_ssn_response]):
            service = CardActivationService(db_session, contact)
            workflow = WorkflowRun()

            workflow.session = {
                "credit_card_account_id": 1,
                "ssn_last_4": "1235",
                "card_last_4": "1234"
            }

            success, msg = service(workflow)
            assert not success
            assert msg == "Card activation failed"

            vendor_service = VendorService(db_session)
            vendor_error_response = vendor_service.get_vendor_error_responses_by_name("amount")[0]
            assert vendor_error_response.status_code == 400
            assert vendor_error_response.error == '{"message":"ssn_last_4 does not match"}'

    def test_wrong_card_last_4_input(self, db_session, contact, contact_leg, mock_amount_token_response,
                                     mock_amount_wrong_card_last_4_response, mock_env_card_activation_secret):
        with patch.object(requests, "post", side_effect=[mock_amount_token_response,
                                                         mock_amount_wrong_card_last_4_response]):
            service = CardActivationService(db_session, contact)
            workflow = WorkflowRun()

            workflow.session = {
                "credit_card_account_id": 1,
                "ssn_last_4": "1234",
                "card_last_4": "1235"
            }

            success, msg = service(workflow)
            assert not success
            assert msg == "Card activation failed"

            vendor_service = VendorService(db_session)
            vendor_error_response = vendor_service.get_vendor_error_responses_by_name("amount")[0]
            assert vendor_error_response.status_code == 400
            assert vendor_error_response.error == '{"message":"card_last_4 does not match"}'

    def test_wrong_ssn_and_card_last_4_input(self, db_session, contact, contact_leg, mock_amount_token_response,
                                             mock_amount_wrong_ssn_and_card_last_4_response,
                                             mock_env_card_activation_secret):
        with patch.object(requests, "post", side_effect=[mock_amount_token_response,
                                                         mock_amount_wrong_ssn_and_card_last_4_response]):
            service = CardActivationService(db_session, contact)
            workflow = WorkflowRun()

            workflow.session = {
                "credit_card_account_id": 1,
                "ssn_last_4": "1235",
                "card_last_4": "1235"
            }

            success, msg = service(workflow)
            assert not success
            assert msg == "Card activation failed"

            vendor_service = VendorService(db_session)
            vendor_error_response = vendor_service.get_vendor_error_responses_by_name("amount")[0]
            assert vendor_error_response.status_code == 400
            assert vendor_error_response.error == '{"message":"card_last_4 does not match, ssn_last_4 does not match"}'

    def test_wrong_card_account_id(self, db_session, contact, contact_leg, mock_amount_token_response,
                                   mock_amount_wrong_credit_card_account_id_response,
                                   mock_env_card_activation_secret):
        with patch.object(requests, "post", side_effect=[mock_amount_token_response,
                                                         mock_amount_wrong_credit_card_account_id_response]):
            service = CardActivationService(db_session, contact)
            workflow = WorkflowRun()

            workflow.session = {
                "credit_card_account_id": 2,
                "ssn_last_4": "1234",
                "card_last_4": "1234"
            }

            success, msg = service(workflow)
            assert not success
            assert msg == "Card activation failed"

            vendor_service = VendorService(db_session)
            vendor_error_response = vendor_service.get_vendor_error_responses_by_name("amount")[0]
            assert vendor_error_response.status_code == 400
            assert vendor_error_response.error == '{"message":"Data error - Body format incorrect"}'
