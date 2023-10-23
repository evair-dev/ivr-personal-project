from unittest.mock import Mock, patch

import pytest
import requests
from sqlalchemy.orm import Session as SQLAlchemySession

from ivr_gateway.models.contacts import Greeting, InboundRouting
from ivr_gateway.models.enums import Partner
from ivr_gateway.models.queues import Queue
from ivr_gateway.models.workflows import Workflow, WorkflowRun
from tests.factories import workflow as wcf
from tests.factories import queues as qf
from tests.factories.helper_functions import compare_step_branches
from step_trees.Iivr.sms.make_payment_sms import make_payment_sms_step_tree
from tests.fixtures.step_trees.hangup import hangup_step_tree
from tests.factories.external_workflow_response import AmountWorkflowResponseFactory as awrf


class TestMakePaymentNoUpcomingPayment:

    @pytest.fixture
    def workflow(self, db_session: SQLAlchemySession) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "make_payment",
                                                step_tree=make_payment_sms_step_tree)
        return workflow_factory.create()

    @pytest.fixture
    def self_service_workflow(self, db_session: SQLAlchemySession) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "Iivr.self_service_menu", step_tree=hangup_step_tree)
        return workflow_factory.create()

    @pytest.fixture
    def queue(self, db_session) -> Queue:
        queue = qf.queue_factory(db_session).create(
            name="test",
            partner=Partner.IVR
        )
        return queue

    @pytest.fixture
    def greeting(self, db_session) -> Greeting:
        greeting = Greeting(message='hello from <phoneme alphabet="ipa" ph="əˈvɑnt">Iivr</phoneme>.')
        db_session.add(greeting)
        db_session.commit()
        return greeting

    @pytest.fixture
    def inbound_routing(self, db_session, workflow: Workflow, greeting: Greeting, queue: Queue) -> InboundRouting:
        call_routing = InboundRouting(
            inbound_target="make_payment_sms",
            workflow=workflow,
            active=True,
            greeting=greeting,
            operating_mode="normal",
            initial_queue=queue
        )
        db_session.add(call_routing)
        db_session.commit()
        return call_routing


class TestSuccessfulPayment(TestMakePaymentNoUpcomingPayment):

    @pytest.fixture
    def mock_customer_lookup_no_upcoming_installment(self) -> Mock:
        return awrf.create_mock_response_for_customer_lookup(
            'tests/fixtures/customer_lookups/2021-01-18_customer_id_111350673.json'
        )

    @pytest.fixture
    def mock_customer_select_amount_after_cutoff(self) -> Mock:
        return awrf.create_mock_responses_for_workflow(
            'tests/fixtures/external_workflows/make_payment/'
            '2021-01-18_product_id_2838616_123_cent_selection_after_cutoff_time.json'
        )

    @pytest.fixture
    def mock_customer_payment_no_upcoming_installment(self) -> Mock:
        return awrf.create_mock_responses_for_workflow(
            'tests/fixtures/external_workflows/make_payment/2021-01-19_product_id_2838616_123_cent_payment.json'
        )

    def test_successful_payment(self, db_session, workflow, self_service_workflow, greeting, inbound_routing,
                                test_client, mock_customer_lookup_no_upcoming_installment,
                                mock_customer_payment_no_upcoming_installment):
        with patch.object(requests, "get", side_effect=[mock_customer_lookup_no_upcoming_installment]):
            with patch.object(requests, "post", side_effect=mock_customer_payment_no_upcoming_installment):

                init_form = {
                    "thread_id": "test",
                    "workflow": "make_payment_sms",
                    "initial_settings": {
                        "livevox_account": "Iivr111350673",
                        "zip_code": "60601"
                    }
                }

                pay_form = {
                    "thread_id": "test",
                    "workflow": "make_payment_sms",
                    "input": "PaY"
                }

                zip_code_form = {
                    "thread_id": "test",
                    "workflow": "make_payment_sms",
                    "input": "60601"
                }

                payment_amount_form = {
                    "thread_id": "test",
                    "workflow": "make_payment_sms",
                    "input": "1.23"
                }

                initial_response = test_client.post("/api/v1/livevox/sms", json=init_form)
                assert initial_response.json == \
                       {"error": None,
                        "text_array": ["To set up a payment, please reply with your zip code to confirm your "
                                       "identity. Please note that messages will time out after 1 hour to pro"
                                       "tect your security."],
                        "finished": False}

                zip_confirmation_and_payment_response = test_client.post("/api/v1/livevox/sms", json=zip_code_form)
                assert zip_confirmation_and_payment_response.json == \
                       {'error': None,
                        'finished': False,
                        'text_array': ['Zipcode confirmed. It looks like you recently made your monthly payment. '
                                       'Please reply with the additional payment you\'d like to make as a number '
                                       '"$XXX.XX".']}

                payment_amount_response = test_client.post("/api/v1/livevox/sms", json=payment_amount_form)
                assert payment_amount_response.json == \
                       {'error': None,
                        'finished': False,
                        'text_array': ['To authorize one e-payment of $1.23 on loan '
                                       'ending in 8616 from your bank account ending in 4637 for 01/20/21, '
                                       'reply PAY.']}

                authorized_payment_response = test_client.post("/api/v1/livevox/sms", json=pay_form)
                assert authorized_payment_response.json == \
                       {"error": None,
                        "text_array": ["Thanks, a payment of $1.23 will post to your account on 01/20/21. "
                                       "To Cancel, please call 800-712-5407. Have a great day!"],
                        "finished": True}

            correct_branch_sequence = [
                "root",
                "get_customer_info",
                "initialize_payment",
                "Iivr-basic-workflow-branch-step",
                "pay_with_bank_account_on_file",
                "Iivr-basic-workflow-branch-step",
                "pay_on_earliest_date",
                "Iivr-basic-workflow-branch-step",
                "select_amount",
                "Iivr-basic-workflow-branch-step",
                "confirmation",
                "branch_to_additional_message",
                "confirmation"
            ]
            workflow_run: WorkflowRun = db_session.query(WorkflowRun).first()
            compare_step_branches(correct_branch_sequence, workflow_run)

    def test_amount_selected_after_cutoff_time(self, db_session, workflow, self_service_workflow, greeting,
                                               inbound_routing, test_client,
                                               mock_customer_lookup_no_upcoming_installment,
                                               mock_customer_select_amount_after_cutoff,
                                               mock_customer_payment_no_upcoming_installment):
        with patch.object(requests, "get", side_effect=[mock_customer_lookup_no_upcoming_installment]):
            mock_customer_payment = mock_customer_select_amount_after_cutoff + \
                                    mock_customer_payment_no_upcoming_installment
            with patch.object(requests, "post", side_effect=mock_customer_payment):

                init_form = {
                    "thread_id": "test",
                    "workflow": "make_payment_sms",
                    "initial_settings": {
                        "livevox_account": "Iivr111350673",
                        "zip_code": "60601"
                    }
                }

                pay_form = {
                    "thread_id": "test",
                    "workflow": "make_payment_sms",
                    "input": "PaY"
                }

                zip_code_form = {
                    "thread_id": "test",
                    "workflow": "make_payment_sms",
                    "input": "60601"
                }

                payment_amount_form = {
                    "thread_id": "test",
                    "workflow": "make_payment_sms",
                    "input": "1.23"
                }

                initial_response = test_client.post("/api/v1/livevox/sms", json=init_form)
                assert initial_response.json == \
                       {"error": None,
                        "text_array": ["To set up a payment, please reply with your zip code to confirm your "
                                       "identity. Please note that messages will time out after 1 hour to pro"
                                       "tect your security."],
                        "finished": False}

                zip_confirmation_and_payment_response = test_client.post("/api/v1/livevox/sms", json=zip_code_form)
                assert zip_confirmation_and_payment_response.json == \
                       {'error': None,
                        'finished': False,
                        'text_array': ['Zipcode confirmed. It looks like you recently made your monthly payment. '
                                       'Please reply with the additional payment you\'d like to make as a number '
                                       '"$XXX.XX".']}

                selection_after_cutoff_response = test_client.post("/api/v1/livevox/sms", json=payment_amount_form)
                assert selection_after_cutoff_response.json == \
                       {'error': None,
                        'finished': False,
                        'text_array': ['Sorry, we received your reply after the cut-off time for today. '
                                       'A payment was not made. A new session is being started.',
                                       'It looks like you recently made your monthly payment. Please reply with the '
                                       'additional payment you\'d like to make as a number "$XXX.XX".']}

                payment_amount_response = test_client.post("/api/v1/livevox/sms", json=payment_amount_form)
                assert payment_amount_response.json == \
                       {'error': None,
                        'finished': False,
                        'text_array': ['To authorize one e-payment of $1.23 on loan '
                                       'ending in 8616 from your bank account ending in 4637 for 01/20/21, '
                                       'reply PAY.']}

                authorized_payment_response = test_client.post("/api/v1/livevox/sms", json=pay_form)
                assert authorized_payment_response.json == \
                       {"error": None,
                        "text_array": ["Thanks, a payment of $1.23 will post to your account on 01/20/21. "
                                       "To Cancel, please call 800-712-5407. Have a great day!"],
                        "finished": True}

            correct_branch_sequence = [
                "root",
                "get_customer_info",
                "initialize_payment",
                "Iivr-basic-workflow-branch-step",
                "pay_with_bank_account_on_file",
                "Iivr-basic-workflow-branch-step",
                "pay_on_earliest_date",
                "Iivr-basic-workflow-branch-step",
                "select_amount",
                "cutoff",
                "initialize_payment",
                "Iivr-basic-workflow-branch-step",
                "pay_with_bank_account_on_file",
                "Iivr-basic-workflow-branch-step",
                "pay_on_earliest_date",
                "cutoff",
                "Iivr-basic-workflow-branch-step",
                "select_amount",
                "Iivr-basic-workflow-branch-step",
                "confirmation",
                "branch_to_additional_message",
                "confirmation"
            ]
            workflow_run: WorkflowRun = db_session.query(WorkflowRun).first()
            compare_step_branches(correct_branch_sequence, workflow_run)


class TestBadPaymentInputs(TestMakePaymentNoUpcomingPayment):

    @pytest.fixture
    def mock_customer_lookup_no_upcoming_installment_high_payment(self) -> Mock:
        return awrf.create_mock_response_for_customer_lookup(
            'tests/fixtures/customer_lookups/2021-02-08_customer_id_111350673.json'
        )

    @pytest.fixture
    def mock_customer_payment_no_upcoming_installment_high_payment(self) -> Mock:
        return awrf.create_mock_responses_for_workflow(
            'tests/fixtures/external_workflows/make_payment/'
            '2021-02-08_product_id_2838616_50000000_cent_payment_error_and_100_cent_payment.json'
        )

    def test_high_payment(self, db_session, workflow, self_service_workflow, greeting, inbound_routing,
                          test_client, mock_customer_lookup_no_upcoming_installment_high_payment,
                          mock_customer_payment_no_upcoming_installment_high_payment):
        with patch.object(requests, "get", side_effect=[mock_customer_lookup_no_upcoming_installment_high_payment]):
            with patch.object(requests, "post", side_effect=mock_customer_payment_no_upcoming_installment_high_payment):

                init_form = {
                    "thread_id": "test",
                    "workflow": "make_payment_sms",
                    "initial_settings": {
                        "livevox_account": "Iivr111350673",
                        "zip_code": "60601"
                    }
                }

                pay_form = {
                    "thread_id": "test",
                    "workflow": "make_payment_sms",
                    "input": "PaY"
                }

                zip_code_form = {
                    "thread_id": "test",
                    "workflow": "make_payment_sms",
                    "input": "60601"
                }

                high_payment_form = {
                    "thread_id": "test",
                    "workflow": "make_payment_sms",
                    "input": "500000.00"
                }

                low_payment_form = {
                    "thread_id": "test",
                    "workflow": "make_payment_sms",
                    "input": "1.00"
                }

                initial_response = test_client.post("/api/v1/livevox/sms", json=init_form)
                assert initial_response.json == \
                       {"error": None,
                        "text_array": ["To set up a payment, please reply with your zip code to confirm your "
                                       "identity. Please note that messages will time out after 1 hour to pro"
                                       "tect your security."],
                        "finished": False}

                zip_confirmation_and_payment_response = test_client.post("/api/v1/livevox/sms", json=zip_code_form)
                assert zip_confirmation_and_payment_response.json == \
                       {'error': None,
                        'finished': False,
                        'text_array': ['Zipcode confirmed. It looks like you recently made your monthly payment. '
                                       'Please reply with the additional payment you\'d like to make as a number '
                                       '"$XXX.XX".']}

                high_payment_response = test_client.post("/api/v1/livevox/sms", json=high_payment_form)
                assert high_payment_response.json == \
                       {'error': None,
                        'finished': False,
                        'text_array': ['Please enter an amount that is $100.19 or less.',
                                       'Please reply with the additional payment you\'d like to make '
                                       'as a number "$XXX.XX".']}

                low_payment_response = test_client.post("/api/v1/livevox/sms", json=low_payment_form)
                assert low_payment_response.json == \
                       {'error': None,
                        'finished': False,
                        'text_array': ['To authorize one e-payment of $1.00 on loan '
                                       'ending in 8616 from your bank account ending in 4637 for 02/08/21, '
                                       'reply PAY.']}

                authorized_payment_response = test_client.post("/api/v1/livevox/sms", json=pay_form)
                assert authorized_payment_response.json == \
                       {"error": None,
                        "text_array": ["Thanks, a payment of $1.00 will post to your account on 02/08/21. "
                                       "To Cancel, please call 800-712-5407. Have a great day!"],
                        "finished": True}

                correct_branch_sequence = [
                    "root",
                    "get_customer_info",
                    "initialize_payment",
                    "Iivr-basic-workflow-branch-step",
                    "pay_with_bank_account_on_file",
                    "Iivr-basic-workflow-branch-step",
                    "pay_on_earliest_date",
                    "Iivr-basic-workflow-branch-step",
                    "select_amount",
                    "Iivr-basic-workflow-branch-step",
                    "confirmation",
                    "branch_to_additional_message",
                    "confirmation"
                ]
                workflow_run: WorkflowRun = db_session.query(WorkflowRun).first()
                compare_step_branches(correct_branch_sequence, workflow_run)

    @pytest.fixture
    def mock_customer_lookup_no_upcoming_installment(self) -> Mock:
        return awrf.create_mock_response_for_customer_lookup(
            'tests/fixtures/customer_lookups/2021-01-18_customer_id_111350673.json'
        )

    @pytest.fixture
    def mock_customer_payment_no_upcoming_installment(self) -> Mock:
        return awrf.create_mock_responses_for_workflow(
            'tests/fixtures/external_workflows/make_payment/2021-01-19_product_id_2838616_123_cent_payment.json'
        )

    def test_improper_payment_input(self, db_session, workflow, self_service_workflow, greeting, inbound_routing,
                                    test_client, mock_customer_lookup_no_upcoming_installment,
                                    mock_customer_payment_no_upcoming_installment):
        with patch.object(requests, "get", side_effect=[mock_customer_lookup_no_upcoming_installment]):
            with patch.object(requests, "post", side_effect=mock_customer_payment_no_upcoming_installment):

                init_form = {
                    "thread_id": "test",
                    "workflow": "make_payment_sms",
                    "initial_settings": {
                        "livevox_account": "Iivr111350673",
                        "zip_code": "60601"
                    }
                }

                pay_form = {
                    "thread_id": "test",
                    "workflow": "make_payment_sms",
                    "input": "PaY"
                }

                zip_code_form = {
                    "thread_id": "test",
                    "workflow": "make_payment_sms",
                    "input": "60601"
                }

                bad_payment_amount_form_1 = {
                    "thread_id": "test",
                    "workflow": "make_payment_sms",
                    "input": "dog food"
                }

                bad_payment_amount_form_2 = {
                    "thread_id": "test",
                    "workflow": "make_payment_sms",
                    "input": "1.234"
                }

                payment_amount_form = {
                    "thread_id": "test",
                    "workflow": "make_payment_sms",
                    "input": "1.23"
                }

                initial_response = test_client.post("/api/v1/livevox/sms", json=init_form)
                assert initial_response.json == \
                       {"error": None,
                        "text_array": ["To set up a payment, please reply with your zip code to confirm your "
                                       "identity. Please note that messages will time out after 1 hour to pro"
                                       "tect your security."],
                        "finished": False}

                zip_confirmation_and_payment_response = test_client.post("/api/v1/livevox/sms", json=zip_code_form)
                assert zip_confirmation_and_payment_response.json == \
                       {'error': None,
                        'finished': False,
                        'text_array': ['Zipcode confirmed. It looks like you recently made your monthly payment. '
                                       'Please reply with the additional payment you\'d like to make as a number '
                                       '"$XXX.XX".']}

                bad_payment_amount_response_1 = test_client.post("/api/v1/livevox/sms", json=bad_payment_amount_form_1)
                assert bad_payment_amount_response_1.json == \
                       {'error': None,
                        'finished': False,
                        'text_array': ['Unfortunately we did not receive a response or were unable to '
                                       'process your request.',
                                       'Please reply with the additional payment you\'d like to make as a number '
                                       '"$XXX.XX".']}

                bad_payment_amount_response_2 = test_client.post("/api/v1/livevox/sms", json=bad_payment_amount_form_2)
                assert bad_payment_amount_response_2.json == \
                       {'error': None,
                        'finished': False,
                        'text_array': ['Unfortunately we did not receive a response or were unable to '
                                       'process your request.',
                                       'Please reply with the additional payment you\'d like to make as a number '
                                       '"$XXX.XX".']}

                payment_amount_response = test_client.post("/api/v1/livevox/sms", json=payment_amount_form)
                assert payment_amount_response.json == \
                       {'error': None,
                        'finished': False,
                        'text_array': ['To authorize one e-payment of $1.23 on loan '
                                       'ending in 8616 from your bank account ending in 4637 for 01/20/21, '
                                       'reply PAY.']}

                authorized_payment_response = test_client.post("/api/v1/livevox/sms", json=pay_form)
                assert authorized_payment_response.json == \
                       {"error": None,
                        "text_array": ["Thanks, a payment of $1.23 will post to your account on 01/20/21. "
                                       "To Cancel, please call 800-712-5407. Have a great day!"],
                        "finished": True}

            correct_branch_sequence = [
                "root",
                "get_customer_info",
                "initialize_payment",
                "Iivr-basic-workflow-branch-step",
                "pay_with_bank_account_on_file",
                "Iivr-basic-workflow-branch-step",
                "pay_on_earliest_date",
                "Iivr-basic-workflow-branch-step",
                "select_amount",
                "Iivr-basic-workflow-branch-step",
                "confirmation",
                "branch_to_additional_message",
                "confirmation"
            ]
            workflow_run: WorkflowRun = db_session.query(WorkflowRun).first()
            compare_step_branches(correct_branch_sequence, workflow_run)
