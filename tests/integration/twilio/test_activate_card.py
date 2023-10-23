import os
from unittest.mock import patch

from mbtest.server import MountebankServer
from mbtest.imposters import Imposter, Predicate, Response, Stub
from mbtest.imposters.responses import HttpResponse

import pytest

import time_machine
from sqlalchemy.orm import Session as SQLAlchemySession

from ivr_gateway.models.contacts import Greeting, InboundRouting
from ivr_gateway.models.queues import Queue
from ivr_gateway.models.workflows import Workflow, WorkflowRun
from ivr_gateway.services.workflows.fields import CustomerLookupFieldLookupService
from ivr_gateway.services.vendors import VendorService

from tests.factories import workflow as wcf
from tests.factories.helper_functions import compare_step_branches
from tests.factories import queues as qf
from step_trees.Iivr.ivr.activate_card import activate_card_step_tree


class ActivateCardFixtures:

    @pytest.fixture
    def workflow(self, db_session: SQLAlchemySession) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "activate_card",
                                                step_tree=activate_card_step_tree)
        return workflow_factory.create()

    @pytest.fixture
    def greeting(self, db_session) -> Greeting:
        greeting = Greeting(message='Thank you for calling <phoneme alphabet="ipa" ph="əˈvɑnt">Iivr</phoneme>. '
                                    'Please be advised that your call will be monitored or record for quality and '
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

    @pytest.fixture
    def mock_env_card_activation_secret(self, monkeypatch):
        monkeypatch.setenv("IVR_AMOUNT_CARD_ACTIVATION_SECRET", "not_null")

    @pytest.fixture
    def mock_env_card_activation_url(self, monkeypatch):
        mountebank_base_url = os.environ.get("MOUNTEBANK_BASE_URL")
        monkeypatch.setenv("IVR_AMOUNT_BASE_URL", mountebank_base_url)

    @pytest.fixture(scope="session")
    def mock_server(self) -> MountebankServer:
        mountebank_host_name = os.environ.get("MOUNTEBANK_HOST_NAME")
        return MountebankServer(port=2525, host=mountebank_host_name)

    @pytest.fixture
    def card_activation_imposter(self) -> Imposter:
        secret = os.environ.get("IVR_AMOUNT_CARD_ACTIVATION_SECRET")
        imposter = Imposter(
            [
                Stub(
                    Predicate(path="/api/account_management/webhook/activate_card")
                    & Predicate(body={'data':
                                          {'credit_card_account_id': 71568378,
                                           'ssn_last_4': '1111',
                                           'card_last_4': '0000'}
                                      })
                    & Predicate(headers={"Authorization": "Bearer abc"})
                    & Predicate(method="POST"),
                    Response(body={
                        "message": "ok"
                    })
                ),
                Stub(
                    Predicate(path="/api/v1/phone_number_customer_lookup")
                    & Predicate(query={"phone_number":"5555555555"})
                    & Predicate(method="GET"),
                    Response(body={
                                    "open_applications": [
                                    {
                                        "id": 672,
                                        "type": "installment"
                                    }
                                    ],
                                    "open_products": [
                                    {
                                        "id": 126,
                                        "type": "Loan",
                                        "funding_date": "2021-06-01",
                                        "active_payoff_quote?": False,
                                        "product_type": "installment",
                                        "product_subtype": "unsecured",
                                        "past_due_amount_cents": 7296,
                                        "operationally_charged_off?": False,
                                        "in_grace_period?": False,
                                        "days_late": 42
                                    },
                                    {
                                        "type": "CreditCardAccount",
                                        "id": 71568378,
                                        "activatable?": False,
                                        "credit_available_cents": 36181,
                                        "past_due_amount_cents": 0,
                                        "operationally_charged_off?": False,
                                        "days_late": None
                                    },
                                    {
                                        "type": "CreditCardAccount",
                                        "id": 123456,
                                        "activatable?": False,
                                        "credit_available_cents": 36181,
                                        "past_due_amount_cents": 0,
                                        "operationally_charged_off?": False,
                                        "days_late": None
                                    }
                                    ],
                                    "customer_information": {
                                    "id": 68,
                                    "state_of_residence": "IL",
                                    "disaster_relief_plan?": False,
                                    "last_contact": None
                                    }
                                })
                ),
                Stub(
                    Predicate(path="/api/account_management/auth/token")
                    & Predicate(headers={"Authorization": f"Basic {secret}"})
                    & Predicate(method="POST"),
                    Response(body={
                        "token_type": "Bearer",
                        "access_token": "abc",
                        "expiration": 11111
                    })
                )
            ],
            record_requests=True,
            default_response=HttpResponse(
                body={"error": "default response"},
                status_code=400
            ),
            port=8080
        )

        return imposter


class TestActivateCard(ActivateCardFixtures):

    @time_machine.travel("2020-12-29 19:00")
    def test_card_activation_success(self, db_session, call_routing, test_client, mock_env_card_activation_url,
                                     mock_env_card_activation_secret, mock_server, card_activation_imposter):
        with patch.object(CustomerLookupFieldLookupService, "get_field_by_lookup_key", return_value=71568378):
            with mock_server([card_activation_imposter]):
                init_form = {"CallSid": "test",
                             "To": "+15555555555",
                             "Digits": ""}

                initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
                assert initial_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Thank you for calling <phoneme '
                    b'alphabet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>. Please be advised that your call '
                    b'will be monitored or record for quality and training purposes.</Say><Gather '
                    b'action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="4" '
                    b'timeout="6"><Say>To activate your card, please enter the last 4 digits of your credit card '
                    b'number.</Say></Gather></Response>'
                )

                card_form = {"CallSid": "test",
                             "To": "+15555555555",
                             "Digits": "0000"}

                card_response = test_client.post("/api/v1/twilio/continue", data=card_form)
                assert card_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You entered 0 0 0 0</Say><Gather '
                    b'action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>If '
                    b'this is correct, press 1. To try again, press 2. To hear this again, '
                    b'press 9.</Say></Gather></Response>')

                confirm_form = {"CallSid": "test",
                                "To": "+15555555555",
                                "Digits": "1"}

                confirm_card_response = test_client.post("/api/v1/twilio/continue", data=confirm_form)
                assert confirm_card_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/continue" '
                    b'actionOnEmptyResult="true" numDigits="4" timeout="6"><Say>Please enter the last four digits of '
                    b'your social security number.</Say></Gather></Response>'
                )

                ssn_form = {"CallSid": "test",
                            "To": "+15555555555",
                            "Digits": "1111"}
                ssn_response = test_client.post("/api/v1/twilio/continue", data=ssn_form)

                assert ssn_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You entered 1 1 1 1</Say><Gather '
                    b'action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>If '
                    b'this is correct, press 1. To try again, press 2. To hear this again, '
                    b'press 9.</Say></Gather></Response>'
                )

                confirm_ssn_response = test_client.post("/api/v1/twilio/continue", data=confirm_form)
                assert confirm_ssn_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Congratulations, your <phoneme '
                    b'alphabet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme> Card is now active. Please remove the '
                    b'activation sticker and sign the back of the card in the designated area. Have a wonderful day. '
                    b'</Say><Hangup /></Response>'
                )

                vendor_service = VendorService(db_session)
                vendor_error_response = vendor_service.get_vendor_responses_by_name("amount")[0]
                assert vendor_error_response.status_code == 200
                assert vendor_error_response.error == ""

                correct_branch_sequence = [
                    "root",
                    "get_customer_card_last_four",
                    "get_customer_ssn_last_four",
                    "card_activation"
                ]
                workflow_run: WorkflowRun = db_session.query(WorkflowRun).first()
                compare_step_branches(correct_branch_sequence, workflow_run)

    @time_machine.travel("2020-12-29 19:00")
    def test_card_activation_bad_activation(self, db_session, call_routing, test_client,
                                            mock_env_card_activation_secret):
        with patch.object(CustomerLookupFieldLookupService, "get_field_by_lookup_key", return_value=71568378):
            init_form = {"CallSid": "test",
                         "To": "+15555555555",
                         "Digits": ""}

            initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
            assert initial_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Thank you for calling <phoneme '
                b'alphabet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>. Please be advised that your call '
                b'will be monitored or record for quality and training purposes.</Say><Gather '
                b'action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="4" '
                b'timeout="6"><Say>To activate your card, please enter the last 4 digits of your credit card '
                b'number.</Say></Gather></Response>'
            )

            card_form = {"CallSid": "test",
                         "To": "+15555555555",
                         "Digits": "0000"}

            card_response = test_client.post("/api/v1/twilio/continue", data=card_form)
            assert card_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You entered 0 0 0 0</Say><Gather '
                b'action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>If '
                b'this is correct, press 1. To try again, press 2. To hear this again, '
                b'press 9.</Say></Gather></Response>')

            confirm_form = {"CallSid": "test",
                            "To": "+15555555555",
                            "Digits": "1"}

            confirm_card_response = test_client.post("/api/v1/twilio/continue", data=confirm_form)
            assert confirm_card_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/continue" '
                b'actionOnEmptyResult="true" numDigits="4" timeout="6"><Say>Please enter the last four digits of '
                b'your social security number.</Say></Gather></Response>'
            )

            ssn_form = {"CallSid": "test",
                        "To": "+15555555555",
                        "Digits": "1111"}
            ssn_response = test_client.post("/api/v1/twilio/continue", data=ssn_form)

            assert ssn_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You entered 1 1 1 1</Say><Gather '
                b'action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>If '
                b'this is correct, press 1. To try again, press 2. To hear this again, '
                b'press 9.</Say></Gather></Response>'
            )

            confirm_ssn_response = test_client.post("/api/v1/twilio/continue", data=confirm_form)
            assert confirm_ssn_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Please hold while we connect you to a '
                b'customer service specialist.</Say><Dial>12345678901</Dial></Response>'
            )

            correct_branch_sequence = [
                "root",
                "get_customer_card_last_four",
                "get_customer_ssn_last_four",
                "card_activation",
                "card_activation_failed"
            ]
            workflow_run: WorkflowRun = db_session.query(WorkflowRun).first()
            compare_step_branches(correct_branch_sequence, workflow_run)

    @time_machine.travel("2020-12-29 19:00")
    def test_card_bad_input(self, db_session, call_routing, test_client, mock_env_card_activation_url):
        with patch.object(CustomerLookupFieldLookupService, "get_field_by_lookup_key", return_value=71568378):
            init_form = {"CallSid": "test",
                         "To": "+15555555555",
                         "Digits": ""}

            initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
            assert initial_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Thank you for calling <phoneme '
                b'alphabet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>. Please be advised that your call '
                b'will be monitored or record for quality and training purposes.</Say><Gather '
                b'action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="4" '
                b'timeout="6"><Say>To activate your card, please enter the last 4 digits of your credit card '
                b'number.</Say></Gather></Response>'
            )

            # test < 4 digits
            card_form = {"CallSid": "test",
                         "To": "+15555555555",
                         "Digits": "000"}

            card_response = test_client.post("/api/v1/twilio/continue", data=card_form)
            assert card_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/continue" '
                b'actionOnEmptyResult="true" numDigits="4" timeout="6">'
                b"<Say>I'm sorry, I didn't receive 4 digits.</Say><Say>To activate your card, please enter "
                b'the last 4 digits of your credit card number.</Say></Gather></Response>'
            )

            # test > 4 digits
            card_form = {"CallSid": "test",
                         "To": "+15555555555",
                         "Digits": "00000"}

            card_response = test_client.post("/api/v1/twilio/continue", data=card_form)
            assert card_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/continue" '
                b'actionOnEmptyResult="true" numDigits="4" timeout="6">'
                b"<Say>I'm sorry, I didn't receive 4 digits.</Say><Say>To activate your card, please enter "
                b'the last 4 digits of your credit card number.</Say></Gather></Response>'
            )

            # test 0 digits
            card_form = {"CallSid": "test",
                         "To": "+15555555555",
                         "Digits": ""}

            card_response = test_client.post("/api/v1/twilio/continue", data=card_form)
            assert card_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Please hold while we transfer your '
                b'call.</Say><Dial>12345678901</Dial></Response>'
            )

            correct_branch_sequence = [
                "root",
                "get_customer_card_last_four",
                "customer_info_input_failed_transfer"
            ]
            workflow_run: WorkflowRun = db_session.query(WorkflowRun).first()
            compare_step_branches(correct_branch_sequence, workflow_run)

    @time_machine.travel("2020-12-29 19:00")
    def test_card_input_bad_confirmation(self, db_session, call_routing, test_client, mock_env_card_activation_url):
        with patch.object(CustomerLookupFieldLookupService, "get_field_by_lookup_key", return_value=71568378):
            init_form = {"CallSid": "test",
                         "To": "+15555555555",
                         "Digits": ""}

            initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
            assert initial_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Thank you for calling <phoneme '
                b'alphabet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>. Please be advised that your call '
                b'will be monitored or record for quality and training purposes.</Say><Gather '
                b'action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="4" '
                b'timeout="6"><Say>To activate your card, please enter the last 4 digits of your credit card '
                b'number.</Say></Gather></Response>'
            )

            card_form = {"CallSid": "test",
                         "To": "+15555555555",
                         "Digits": "0000"}

            confirm_form = {"CallSid": "test",
                            "To": "+15555555555",
                            "Digits": "2"}

            for _ in range(2):
                card_response = test_client.post("/api/v1/twilio/continue", data=card_form)
                assert card_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You entered 0 0 0 0</Say><Gather '
                    b'action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>If '
                    b'this is correct, press 1. To try again, press 2. To hear this again, '
                    b'press 9.</Say></Gather></Response>')
                confirm_card_response = test_client.post("/api/v1/twilio/continue", data=confirm_form)
                assert confirm_card_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twil'
                    b'io/continue" actionOnEmptyResult="true" numDigits="4" timeout="6"><Say>To ac'
                    b'tivate your card, please enter the last 4 digits of your credit card number.'
                    b'</Say></Gather></Response>'
                )

            card_response = test_client.post("/api/v1/twilio/continue", data=card_form)
            assert card_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You entered 0 0 0 0</Say><Gather '
                b'action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>If '
                b'this is correct, press 1. To try again, press 2. To hear this again, '
                b'press 9.</Say></Gather></Response>')

            confirm_card_response = test_client.post("/api/v1/twilio/continue", data=confirm_form)
            assert confirm_card_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Please hold while we tr'
                b'ansfer your call.</Say><Dial>12345678901</Dial></Response>'
            )

            correct_branch_sequence = [
                "root",
                "get_customer_card_last_four",
                "customer_info_input_failed_transfer"
            ]
            workflow_run: WorkflowRun = db_session.query(WorkflowRun).first()
            compare_step_branches(correct_branch_sequence, workflow_run)

    @time_machine.travel("2020-12-29 19:00")
    def test_card_input_talk_to_specialist(self, db_session, call_routing, test_client,
                                            mock_env_card_activation_secret):
        with patch.object(CustomerLookupFieldLookupService, "get_field_by_lookup_key", return_value=71568378):
            init_form = {"CallSid": "test",
                         "To": "+15555555555",
                         "Digits": ""}

            initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
            assert initial_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Thank you for calling <phoneme '
                b'alphabet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>. Please be advised that your call '
                b'will be monitored or record for quality and training purposes.</Say><Gather '
                b'action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="4" '
                b'timeout="6"><Say>To activate your card, please enter the last 4 digits of your credit card '
                b'number.</Say></Gather></Response>'
            )

            card_form = {"CallSid": "test",
                         "To": "+15555555555",
                         "Digits": "0000"}

            card_response = test_client.post("/api/v1/twilio/continue", data=card_form)
            assert card_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You entered 0 0 0 0</Say><Gather '
                b'action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>If '
                b'this is correct, press 1. To try again, press 2. To hear this again, '
                b'press 9.</Say></Gather></Response>')

            confirm_form = {"CallSid": "test",
                            "To": "+15555555555",
                            "Digits": "0"}

            confirm_card_response = test_client.post("/api/v1/twilio/continue", data=confirm_form)
            assert confirm_card_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Dial>12345678901</Dial></Response>'
            )

        


    @time_machine.travel("2020-12-29 19:00")
    def test_ssn_bad_input(self, db_session, call_routing, test_client, mock_env_card_activation_url):
        with patch.object(CustomerLookupFieldLookupService, "get_field_by_lookup_key", return_value=71568378):
            init_form = {"CallSid": "test",
                         "To": "+15555555555",
                         "Digits": ""}

            initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
            assert initial_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Thank you for calling <phoneme '
                b'alphabet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>. Please be advised that your call '
                b'will be monitored or record for quality and training purposes.</Say><Gather '
                b'action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="4" '
                b'timeout="6"><Say>To activate your card, please enter the last 4 digits of your credit card '
                b'number.</Say></Gather></Response>'
            )

            card_form = {"CallSid": "test",
                         "To": "+15555555555",
                         "Digits": "0000"}

            card_response = test_client.post("/api/v1/twilio/continue", data=card_form)
            assert card_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You entered 0 0 0 0</Say><Gather '
                b'action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>If '
                b'this is correct, press 1. To try again, press 2. To hear this again, '
                b'press 9.</Say></Gather></Response>')

            confirm_form = {"CallSid": "test",
                            "To": "+15555555555",
                            "Digits": "1"}

            confirm_card_response = test_client.post("/api/v1/twilio/continue", data=confirm_form)
            assert confirm_card_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/continue" '
                b'actionOnEmptyResult="true" numDigits="4" timeout="6"><Say>Please enter the last four digits of '
                b'your social security number.</Say></Gather></Response>'
            )

            ssn_form = {"CallSid": "test",
                        "To": "+15555555555",
                        "Digits": "000"}

            # try sending invalid input twice
            for _ in range(2):
                ssn_response = test_client.post("/api/v1/twilio/continue", data=ssn_form)
                assert ssn_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/continue" '
                    b'actionOnEmptyResult="true" numDigits="4" timeout="6"><Say>'
                    b"I'm sorry, I didn't receive 4 digits.</Say><Say>Please enter the last four digits "
                    b'of your social security number.</Say></Gather></Response>'
                )

            # try a third input
            # get transferred to the customer queue
            ssn_response = test_client.post("/api/v1/twilio/continue", data=ssn_form)
            assert ssn_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Please hold while we transfer your '
                b'call.</Say><Dial>12345678901</Dial></Response>'
            )

            correct_branch_sequence = [
                "root",
                "get_customer_card_last_four",
                "get_customer_ssn_last_four",
                "customer_info_input_failed_transfer"
            ]
            workflow_run: WorkflowRun = db_session.query(WorkflowRun).first()
            compare_step_branches(correct_branch_sequence, workflow_run)

    @time_machine.travel("2020-12-29 19:00")
    def test_ssn_input_bad_confirmation(self, db_session, call_routing, test_client, mock_env_card_activation_url):
        with patch.object(CustomerLookupFieldLookupService, "get_field_by_lookup_key", return_value=71568378):
            init_form = {"CallSid": "test",
                         "To": "+15555555555",
                         "Digits": ""}

            initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
            assert initial_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Thank you for calling <phoneme '
                b'alphabet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>. Please be advised that your call '
                b'will be monitored or record for quality and training purposes.</Say><Gather '
                b'action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="4" '
                b'timeout="6"><Say>To activate your card, please enter the last 4 digits of your credit card '
                b'number.</Say></Gather></Response>'
            )

            card_form = {"CallSid": "test",
                         "To": "+15555555555",
                         "Digits": "0000"}

            card_response = test_client.post("/api/v1/twilio/continue", data=card_form)
            assert card_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You entered 0 0 0 0</Say><Gather '
                b'action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>If '
                b'this is correct, press 1. To try again, press 2. To hear this again, '
                b'press 9.</Say></Gather></Response>')

            confirm_form = {"CallSid": "test",
                            "To": "+15555555555",
                            "Digits": "1"}

            confirm_card_response = test_client.post("/api/v1/twilio/continue", data=confirm_form)
            ssn_form = {"CallSid": "test",
                        "To": "+15555555555",
                        "Digits": "0000"}
            confirm_form = {"CallSid": "test",
                            "To": "+15555555555",
                            "Digits": "2"}

            assert confirm_card_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/continue" '
                b'actionOnEmptyResult="true" numDigits="4" timeout="6"><Say>Please enter the last four digits '
                b'of your social security number.</Say></Gather></Response>'
            )

            for _ in range(2):
                ssn_response = test_client.post("/api/v1/twilio/continue", data=ssn_form)
                assert ssn_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You entered 0 0 0 0</Sa'
                    b'y><Gather action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDig'
                    b'its="1" timeout="6"><Say>If this is correct, press 1. To try again, press 2.'
                    b' To hear this again, press 9.</Say></Gather></Response>'
                )
                ssn_confirm_response = test_client.post("/api/v1/twilio/continue", data=confirm_form)
                assert ssn_confirm_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twil'
                    b'io/continue" actionOnEmptyResult="true" numDigits="4" timeout="6"><Say>Pleas'
                    b'e enter the last four digits of your social security number.</Say></Gather><'
                    b'/Response>'
                )

            ssn_response = test_client.post("/api/v1/twilio/continue", data=ssn_form)
            assert ssn_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You entered 0 0 0 0</Sa'
                b'y><Gather action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDig'
                b'its="1" timeout="6"><Say>If this is correct, press 1. To try again, press 2.'
                b' To hear this again, press 9.</Say></Gather></Response>'
            )
            ssn_confirm_response = test_client.post("/api/v1/twilio/continue", data=confirm_form)
            assert ssn_confirm_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Please hold while we tr'
                b'ansfer your call.</Say><Dial>12345678901</Dial></Response>'
            )

            correct_branch_sequence = [
                "root",
                "get_customer_card_last_four",
                "get_customer_ssn_last_four",
                "customer_info_input_failed_transfer"
            ]
            workflow_run: WorkflowRun = db_session.query(WorkflowRun).first()
            compare_step_branches(correct_branch_sequence, workflow_run)

    @time_machine.travel("2020-12-29 19:00")
    def test_customer_lookup_bad_customer(self, db_session, call_routing, test_client, mock_env_card_activation_url,
                                          card_activation_imposter, mock_server):
        init_form = {"CallSid": "test",
                     "To": "+15555555555",
                     "Digits": ""}
        with mock_server([card_activation_imposter]):
            initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
            assert initial_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Thank you for calling <phoneme '
                b'alphabet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>. Please be advised that your call '
                b'will be monitored or record for quality and training purposes.</Say><Gather '
                b'action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="10" '
                b'timeout="6"><Say>To activate your card, please enter your full ten digit phone number on '
                b'file.</Say></Gather></Response>'
            )

            phone_number_form = {"CallSid": "test",
                                 "To": "+15555555555",
                                 "Digits": "6666666666"}
            phone_number_input_response = test_client.post("/api/v1/twilio/continue", data=phone_number_form)

            assert phone_number_input_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You entered 6 6 6 6 6 6 6 6 6 6</Say><Gather '
                b'action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>If '
                b'this is correct, press 1. To try again, press 2. To hear this again, '
                b'press 9.</Say></Gather></Response>'
            )

            confirm_form = {"CallSid": "test",
                            "To": "+15555555555",
                            "Digits": "1"}

            confirm_phone_response = test_client.post("/api/v1/twilio/continue", data=confirm_form)

            assert confirm_phone_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>We\'re sorry, we were not able to locate your '
                b'account. Please hold while we transfer your call.</Say><Dial>12345678901</Dial></Response>'
            )

            correct_branch_sequence = [
                "root",
                "get_customer_phone_number",
                "customer_lookup_with_session",
                "customer_lookup_with_session_failed"
            ]
            workflow_run: WorkflowRun = db_session.query(WorkflowRun).first()
            compare_step_branches(correct_branch_sequence, workflow_run)

    @time_machine.travel("2020-12-29 19:00")
    def test_customer_lookup_success(self, db_session, call_routing, test_client, mock_env_card_activation_secret,
                                     mock_env_card_activation_url, card_activation_imposter, mock_server):
        init_form = {"CallSid": "test",
                     "To": "+15555555555",
                     "Digits": ""}

        with mock_server([card_activation_imposter]):
            initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
            assert initial_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Thank you for calling <phoneme '
                b'alphabet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>. Please be advised that your call '
                b'will be monitored or record for quality and training purposes.</Say><Gather '
                b'action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="10" '
                b'timeout="6"><Say>To activate your card, please enter your full ten digit phone number on '
                b'file.</Say></Gather></Response>'
            )

            with patch.object(CustomerLookupFieldLookupService, "get_field_by_lookup_key", return_value=71568378):
                phone_number_form = {"CallSid": "test",
                                     "To": "+15555555555",
                                     "Digits": "5555555555"}
                phone_number_input_response = test_client.post("/api/v1/twilio/continue", data=phone_number_form)

                assert phone_number_input_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You entered 5 5 5 5 5 5 5 5 5 '
                    b'5</Say><Gather action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" '
                    b'timeout="6"><Say>If this is correct, press 1. To try again, press 2. To hear this again, '
                    b'press 9.</Say></Gather></Response>'
                )

                confirm_form = {"CallSid": "test",
                                "To": "+15555555555",
                                "Digits": "1"}

                confirm_phone_response = test_client.post("/api/v1/twilio/continue", data=confirm_form)
                assert confirm_phone_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twil'
                    b'io/continue" actionOnEmptyResult="true" numDigits="4" timeout="6"><Say>To ac'
                    b'tivate your card, please enter the last 4 digits of your credit card number.'
                    b'</Say></Gather></Response>'
                )

                card_form = {"CallSid": "test",
                             "To": "+15555555555",
                             "Digits": "0000"}

                card_response = test_client.post("/api/v1/twilio/continue", data=card_form)
                assert card_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You entered 0 0 0 0</Say><Gather '
                    b'action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>If '
                    b'this is correct, press 1. To try again, press 2. To hear this again, '
                    b'press 9.</Say></Gather></Response>')

                confirm_form = {"CallSid": "test",
                                "To": "+15555555555",
                                "Digits": "1"}

                confirm_card_response = test_client.post("/api/v1/twilio/continue", data=confirm_form)
                assert confirm_card_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/continue" '
                    b'actionOnEmptyResult="true" numDigits="4" timeout="6"><Say>Please enter the last four digits of '
                    b'your social security number.</Say></Gather></Response>'
                )

                ssn_form = {"CallSid": "test",
                            "To": "+15555555555",
                            "Digits": "1111"}
                ssn_response = test_client.post("/api/v1/twilio/continue", data=ssn_form)

                assert ssn_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You entered 1 1 1 1</Say><Gather '
                    b'action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>If '
                    b'this is correct, press 1. To try again, press 2. To hear this again, '
                    b'press 9.</Say></Gather></Response>'
                )

                confirm_form = {"CallSid": "test",
                                "To": "+15555555555",
                                "Digits": "1"}

                confirm_ssn_response = test_client.post("/api/v1/twilio/continue", data=confirm_form)
                assert confirm_ssn_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Congratulations, your <phoneme '
                    b'alphabet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme> Card is now active. Please remove the '
                    b'activation sticker and sign the back of the card in the designated area. Have a wonderful day. '
                    b'</Say><Hangup /></Response>'
                )

                vendor_service = VendorService(db_session)
                vendor_error_response = vendor_service.get_vendor_responses_by_name("amount")[0]
                assert vendor_error_response.status_code == 200
                assert vendor_error_response.error == ""

                correct_branch_sequence = [
                    "root",
                    "get_customer_phone_number",
                    "customer_lookup_with_session",
                    "get_customer_card_last_four",
                    "get_customer_ssn_last_four",
                    "card_activation"
                ]
                workflow_run: WorkflowRun = db_session.query(WorkflowRun).first()
                compare_step_branches(correct_branch_sequence, workflow_run)

    @time_machine.travel("2020-12-29 19:00")
    def test_phone_number_bad_input(self, db_session, call_routing, test_client,
                                    mock_env_card_activation_url):
        init_form = {"CallSid": "test",
                     "To": "+15555555555",
                     "Digits": ""}

        initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
        assert initial_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Thank you for calling <phoneme '
            b'alphabet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>. Please be advised that your call '
            b'will be monitored or record for quality and training purposes.</Say><Gather '
            b'action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="10" '
            b'timeout="6"><Say>To activate your card, please enter your full ten digit phone number on '
            b'file.</Say></Gather></Response>'
        )

        # enter < 10 digits
        phone_number_form = {"CallSid": "test",
                             "To": "+15555555555",
                             "Digits": "555555555"}
        for _ in range(2):
            phone_number_input_response = test_client.post("/api/v1/twilio/continue", data=phone_number_form)
            assert phone_number_input_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/continue" '
                b'actionOnEmptyResult="true" numDigits="10" timeout="6">'
                b"<Say>I'm sorry, I didn't receive 10 digits.</Say><Say>To activate your card, please enter "
                b'your full ten digit phone number on file.</Say></Gather></Response>'
            )

        phone_number_input_response = test_client.post("/api/v1/twilio/continue", data=phone_number_form)
        assert phone_number_input_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Please hold while we transfer your '
            b'call.</Say><Dial>12345678901</Dial></Response>'
        )

        correct_branch_sequence = [
            "root",
            "get_customer_phone_number",
            "customer_info_input_failed_transfer"
        ]
        workflow_run: WorkflowRun = db_session.query(WorkflowRun).first()
        compare_step_branches(correct_branch_sequence, workflow_run)

    @time_machine.travel("2020-12-29 19:00")
    def test_phone_number_input_bad_confirmation(self, db_session, call_routing, test_client,
                                                 mock_env_card_activation_url):
        init_form = {"CallSid": "test",
                     "To": "+15555555555",
                     "Digits": ""}

        initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
        assert initial_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Thank you for calling <phoneme '
            b'alphabet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>. Please be advised that your call '
            b'will be monitored or record for quality and training purposes.</Say><Gather '
            b'action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="10" '
            b'timeout="6"><Say>To activate your card, please enter your full ten digit phone number on '
            b'file.</Say></Gather></Response>'
        )

        with patch.object(CustomerLookupFieldLookupService, "get_field_by_lookup_key", return_value=71568378):
            phone_number_form = {"CallSid": "test",
                                 "To": "+15555555555",
                                 "Digits": "5555555555"}

            for _ in range(2):
                phone_number_input_response = test_client.post("/api/v1/twilio/continue", data=phone_number_form)
                assert phone_number_input_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You entered 5 5 5 5 5 5 5 5 5 '
                    b'5</Say><Gather action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" '
                    b'timeout="6"><Say>If this is correct, press 1. To try again, press 2. To hear this again, '
                    b'press 9.</Say></Gather></Response>'
                )

                confirm_form = {"CallSid": "test",
                                "To": "+15555555555",
                                "Digits": "2"}

                confirm_phone_response = test_client.post("/api/v1/twilio/continue", data=confirm_form)
                assert confirm_phone_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twil'
                    b'io/continue" actionOnEmptyResult="true" numDigits="10" timeout="6"><Say>To a'
                    b'ctivate your card, please enter your full ten digit phone number on file.</'
                    b'Say></Gather></Response>'
                )

            phone_number_input_response = test_client.post("/api/v1/twilio/continue", data=phone_number_form)
            assert phone_number_input_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You entered 5 5 5 5 5 5 5 5 5 '
                b'5</Say><Gather action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" '
                b'timeout="6"><Say>If this is correct, press 1. To try again, press 2. To hear this again, '
                b'press 9.</Say></Gather></Response>'
            )

            confirm_phone_response = test_client.post("/api/v1/twilio/continue", data=confirm_form)
            assert confirm_phone_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Please hold while we tr'
                b'ansfer your call.</Say><Dial>12345678901</Dial></Response>'
            )

            correct_branch_sequence = [
                "root",
                "get_customer_phone_number",
                "customer_info_input_failed_transfer"
            ]
            workflow_run: WorkflowRun = db_session.query(WorkflowRun).first()
            compare_step_branches(correct_branch_sequence, workflow_run)

    @time_machine.travel("2020-12-29 19:00")
    def test_phone_number_replay_message(self, db_session, call_routing, test_client, mock_env_card_activation_url):
        init_form = {"CallSid": "test",
                     "To": "+15555555555",
                     "Digits": ""}

        initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
        assert initial_response.data == (
            b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Thank you for calling <phoneme '
            b'alphabet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>. Please be advised that your call '
            b'will be monitored or record for quality and training purposes.</Say><Gather '
            b'action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="10" '
            b'timeout="6"><Say>To activate your card, please enter your full ten digit phone number on '
            b'file.</Say></Gather></Response>'
        )

        with patch.object(CustomerLookupFieldLookupService, "get_field_by_lookup_key", return_value=71568378):
            phone_number_form = {"CallSid": "test",
                                 "To": "+15555555555",
                                 "Digits": "5555555555"}

            phone_number_input_response = test_client.post("/api/v1/twilio/continue", data=phone_number_form)
            assert phone_number_input_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You entered 5 5 5 5 5 5 5 5 5 '
                b'5</Say><Gather action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" '
                b'timeout="6"><Say>If this is correct, press 1. To try again, press 2. To hear this again, '
                b'press 9.</Say></Gather></Response>'
            )

            confirm_form = {"CallSid": "test",
                            "To": "+15555555555",
                            "Digits": "9"}

            for _ in range(10):
                confirm_phone_response = test_client.post("/api/v1/twilio/continue", data=confirm_form)
                assert confirm_phone_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You entered 5 5 5 5 5 5 5 5 5 '
                    b'5</Say><Gather action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" '
                    b'timeout="6"><Say>If this is correct, press 1. To try again, press 2. To hear this again, '
                    b'press 9.</Say></Gather></Response>'
                )
            correct_branch_sequence = [
                "root",
                "get_customer_phone_number",
            ]
            workflow_run: WorkflowRun = db_session.query(WorkflowRun).first()
            compare_step_branches(correct_branch_sequence, workflow_run)

    @time_machine.travel("2020-12-29 19:00")
    def test_card_activation_with_mulitple_products(self, db_session, call_routing, test_client, mock_env_card_activation_url,
                                            mock_env_card_activation_secret, mock_server, card_activation_imposter):

        with mock_server([card_activation_imposter]):
            init_form = {"CallSid": "test",
                         "To": "+15555555555",
                         "Digits": ""}

            initial_response = test_client.post("/api/v1/twilio/new", data=init_form)
            assert initial_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Thank you for calling <phoneme '
                b'alphabet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>. Please be advised that your call '
                b'will be monitored or record for quality and training purposes.</Say><Gather '
                b'action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="10" '
                b'timeout="6"><Say>To activate your card, please enter your full ten digit phone number on '
                b'file.</Say></Gather></Response>'
            )

            phone_number_form = {"CallSid": "test",
                                    "To": "+15555555555",
                                    "Digits": "5555555555"}

            phone_number_input_response = test_client.post("/api/v1/twilio/continue", data=phone_number_form)

            assert phone_number_input_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You entered 5 5 5 5 5 5 5 5 5 '
                b'5</Say><Gather action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" '
                b'timeout="6"><Say>If this is correct, press 1. To try again, press 2. To hear this again, '
                b'press 9.</Say></Gather></Response>'
            )

            confirm_form = {"CallSid": "test",
                            "To": "+15555555555",
                            "Digits": "1"}

            confirm_phone_response = test_client.post("/api/v1/twilio/continue", data=confirm_form)
            assert confirm_phone_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twil'
                b'io/continue" actionOnEmptyResult="true" numDigits="4" timeout="6"><Say>To ac'
                b'tivate your card, please enter the last 4 digits of your credit card number.'
                b'</Say></Gather></Response>'
            )

            card_form = {"CallSid": "test",
                         "To": "+15555555555",
                         "Digits": "0000"}

            card_response = test_client.post("/api/v1/twilio/continue", data=card_form)
            assert card_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You entered 0 0 0 0</Say><Gather '
                b'action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>If '
                b'this is correct, press 1. To try again, press 2. To hear this again, '
                b'press 9.</Say></Gather></Response>')

            confirm_form = {"CallSid": "test",
                            "To": "+15555555555",
                            "Digits": "1"}

            confirm_card_response = test_client.post("/api/v1/twilio/continue", data=confirm_form)
            assert confirm_card_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/continue" '
                b'actionOnEmptyResult="true" numDigits="4" timeout="6"><Say>Please enter the last four digits of '
                b'your social security number.</Say></Gather></Response>'
            )

            ssn_form = {"CallSid": "test",
                        "To": "+15555555555",
                        "Digits": "1111"}
            ssn_response = test_client.post("/api/v1/twilio/continue", data=ssn_form)

            assert ssn_response.data == (
                b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You entered 1 1 1 1</Say><Gather '
                b'action="/api/v1/twilio/continue" actionOnEmptyResult="true" numDigits="1" timeout="6"><Say>If '
                b'this is correct, press 1. To try again, press 2. To hear this again, '
                b'press 9.</Say></Gather></Response>'
            )

            confirm_ssn_response = test_client.post("/api/v1/twilio/continue", data=confirm_form)
            assert confirm_ssn_response.data == (
                    b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Congratulations, your <phoneme '
                    b'alphabet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme> Card is now active. Please remove the '
                    b'activation sticker and sign the back of the card in the designated area. Have a wonderful day. '
                    b'</Say><Hangup /></Response>'
                )

            correct_branch_sequence = [
                "root",
                "get_customer_phone_number",
                "customer_lookup_with_session",
                "get_customer_card_last_four",
                "get_customer_ssn_last_four",
                "card_activation"
            ]
            workflow_run: WorkflowRun = db_session.query(WorkflowRun).first()
            compare_step_branches(correct_branch_sequence, workflow_run)
