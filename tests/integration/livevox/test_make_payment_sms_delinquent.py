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


class TestMakePaymentSMSDelinquent:

    @pytest.fixture
    def workflow(self, db_session: SQLAlchemySession) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "make_payment_sms", step_tree=make_payment_sms_step_tree)
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


class TestLateWithinGracePeriod(TestMakePaymentSMSDelinquent):

    @pytest.fixture
    def mock_customer_lookup_late_within_grace_period(self) -> Mock:
        return awrf.create_mock_response_for_customer_lookup(
            'tests/fixtures/customer_lookups/2021-01-05_customer_id_111350673.json'
        )

    @pytest.fixture
    def mock_customer_payment_late_within_grace_period(self) -> Mock:
        return awrf.create_mock_responses_for_workflow(
            'tests/fixtures/external_workflows/make_payment/2021-01-05_product_id_3050541_9518_cent_payment.json'
        )

    @pytest.fixture
    def mock_customer_payment_late_within_grace_period_cancelled(self) -> Mock:
        return awrf.create_mock_responses_for_workflow(
            'tests/fixtures/external_workflows/make_payment/'
            '2021-01-05_product_id_3050541_9518_cent_payment_cancelled.json'
        )

    def test_successful_payment_late_within_grace_period(self, db_session, workflow, self_service_workflow, greeting,
                                                         inbound_routing, test_client,
                                                         mock_customer_lookup_late_within_grace_period,
                                                         mock_customer_payment_late_within_grace_period):
        with patch.object(requests, "get", side_effect=[mock_customer_lookup_late_within_grace_period]):
            with patch.object(requests, "post", side_effect=mock_customer_payment_late_within_grace_period):
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

                initial_response = test_client.post("/api/v1/livevox/sms", json=init_form)
                assert initial_response.json == \
                       {"error": None,
                        "text_array": ["To set up a payment, please reply with your zip code to confirm "
                                       "your identity. Please note that messages will time out after 1 "
                                       "hour to protect your security."],
                        "finished": False}

                zip_confirmation_and_payment_response = test_client.post("/api/v1/livevox/sms", json=zip_code_form)
                assert zip_confirmation_and_payment_response.json == \
                       {'error': None,
                        'finished': False,
                        'text_array': ['Zipcode confirmed. This is an attempt to collect a debt and '
                                       'any information obtained will be used for that purpose.',
                                       'Your current past due is $95.18. To authorize one e-payment '
                                       'of $95.18 on loan ending in 0541 from your bank account '
                                       'ending in 1075 for 01/07/21, reply PAY.']}

                authorized_payment_response = test_client.post("/api/v1/livevox/sms", json=pay_form)
                assert authorized_payment_response.json == \
                       {"error": None,
                        "text_array": ["Thanks, a payment of $95.18 will post to your account on 01/07/21. "
                                       "To Cancel, please call 800-712-5407. Have a great day!"],
                        "finished": True}

                correct_branch_sequence = [
                    "root",
                    "get_customer_info",
                    "initialize_payment",
                    "Iivr-basic-workflow-branch-step",
                    "pay_with_bank_account_on_file",
                    "Iivr-basic-workflow-branch-step",
                    "pay_amount_due",
                    "Iivr-basic-workflow-branch-step",
                    "pay_on_earliest_date",
                    "Iivr-basic-workflow-branch-step",
                    "confirmation",
                    "branch_to_additional_message",
                    "play_delinquent_message",
                    "confirmation"
                ]
                workflow_run: WorkflowRun = db_session.query(WorkflowRun).first()
                compare_step_branches(correct_branch_sequence, workflow_run)

    def test_cancelled_payment_late_within_grace_period(self, db_session, workflow, self_service_workflow, greeting,
                                                        inbound_routing, test_client,
                                                        mock_customer_lookup_late_within_grace_period,
                                                        mock_customer_payment_late_within_grace_period_cancelled):
        # Note that this payment isn't truly cancelled in Amount - it's just never confirmed. Mock shows a cancellation
        # but we never actually send "cancel" to Amount in our StepTree.
        with patch.object(requests, "get", side_effect=[mock_customer_lookup_late_within_grace_period]):
            with patch.object(requests, "post", side_effect=mock_customer_payment_late_within_grace_period_cancelled):
                init_form = {
                    "thread_id": "test",
                    "workflow": "make_payment_sms",
                    "initial_settings": {
                        "livevox_account": "Iivr111350673",
                        "zip_code": "60601"
                    }
                }

                zip_code_form = {
                    "thread_id": "test",
                    "workflow": "make_payment_sms",
                    "input": "60601"
                }

                cancel_form = {
                    "thread_id": "test",
                    "workflow": "make_payment_sms",
                    "input": "anything but pay"
                }

                initial_response = test_client.post("/api/v1/livevox/sms", json=init_form)
                assert initial_response.json == \
                       {"error": None,
                        "text_array": ["To set up a payment, please reply with your zip code to confirm "
                                       "your identity. Please note that messages will time out after 1 "
                                       "hour to protect your security."],
                        "finished": False}

                zip_confirmation_and_payment_response = test_client.post("/api/v1/livevox/sms", json=zip_code_form)
                assert zip_confirmation_and_payment_response.json == \
                       {'error': None,
                        'finished': False,
                        'text_array': ['Zipcode confirmed. This is an attempt to collect a debt and any '
                                       'information obtained will be used for that purpose.',
                                       'Your current past due is $95.18. To authorize one e-payment of '
                                       '$95.18 on loan ending in 0541 from your bank account ending in '
                                       '1075 for 01/07/21, reply PAY.']}

                cancelled_payment_response = test_client.post("/api/v1/livevox/sms", json=cancel_form)
                assert cancelled_payment_response.json == \
                       {"error": None,
                        "text_array": ["A payment was not made. Please contact an agent for further "
                                       "assistance at 800-712-5407."],
                        "finished": True}

                correct_branch_sequence = [
                    "root",
                    "get_customer_info",
                    "initialize_payment",
                    "Iivr-basic-workflow-branch-step",
                    "pay_with_bank_account_on_file",
                    "Iivr-basic-workflow-branch-step",
                    "pay_amount_due",
                    "Iivr-basic-workflow-branch-step",
                    "pay_on_earliest_date",
                    "Iivr-basic-workflow-branch-step",
                    "confirmation",
                    "branch_to_additional_message",
                    "play_delinquent_message",
                    "confirmation",
                    "payment_not_made"
                ]
                workflow_run: WorkflowRun = db_session.query(WorkflowRun).first()
                compare_step_branches(correct_branch_sequence, workflow_run)

    def test_zip_code_retry(self, db_session, workflow, self_service_workflow, greeting, inbound_routing, test_client,
                            mock_customer_lookup_late_within_grace_period,
                            mock_customer_payment_late_within_grace_period):
        with patch.object(requests, "get", side_effect=[mock_customer_lookup_late_within_grace_period]):
            with patch.object(requests, "post", side_effect=mock_customer_payment_late_within_grace_period):
                init_form = {
                    "thread_id": "test",
                    "workflow": "make_payment_sms",
                    "initial_settings": {
                        "livevox_account": "Iivr111350673",
                        "zip_code": "60601"
                    }
                }

                correct_zip_code_form = {
                    "thread_id": "test",
                    "workflow": "make_payment_sms",
                    "input": "60601"
                }

                incorrect_zip_code_form = {
                    "thread_id": "test",
                    "workflow": "make_payment_sms",
                    "input": "12345"
                }

                # incorrect zip code x2 followed by correct zip code
                initial_response = test_client.post("/api/v1/livevox/sms", json=init_form)
                assert initial_response.json == \
                       {"error": None,
                        "text_array": ["To set up a payment, please reply with your zip code to confirm "
                                       "your identity. Please note that messages will time out after 1 h"
                                       "our to protect your security."],
                        "finished": False}

                incorrect_zip_code_response_1 = test_client.post("/api/v1/livevox/sms",
                                                                 json=incorrect_zip_code_form)
                assert incorrect_zip_code_response_1.json == \
                       {"error": None, "text_array": ["Sorry, invalid zip code. Try again please."], "finished": False}

                incorrect_zip_code_response_2 = test_client.post("/api/v1/livevox/sms",
                                                                 json=incorrect_zip_code_form)
                assert incorrect_zip_code_response_2.json == \
                       {"error": None, "text_array": ["Sorry, invalid zip code. Try again please."], "finished": False}

                correct_zip_code_response = test_client.post("/api/v1/livevox/sms",
                                                             json=correct_zip_code_form)
                assert correct_zip_code_response.json == \
                       {'error': None,
                        'finished': False,
                        'text_array': ['Zipcode confirmed. This is an attempt to collect a debt and any '
                                       'information obtained will be used for that purpose.',
                                       'Your current past due is $95.18. To authorize one e-payment of '
                                       '$95.18 on loan ending in 0541 from your bank account ending in '
                                       '1075 for 01/07/21, reply PAY.']}

    def test_incorrect_zip_code(self, db_session, workflow, self_service_workflow, greeting, inbound_routing,
                                test_client, mock_customer_lookup_late_within_grace_period,
                                mock_customer_payment_late_within_grace_period):
        with patch.object(requests, "get", side_effect=[mock_customer_lookup_late_within_grace_period]):
            with patch.object(requests, "post", side_effect=mock_customer_payment_late_within_grace_period):
                init_form = {
                    "thread_id": "test",
                    "workflow": "make_payment_sms",
                    "initial_settings": {
                        "livevox_account": "Iivr111350673",
                        "zip_code": "60601"
                    }
                }

                incorrect_zip_code_form = {
                    "thread_id": "test",
                    "workflow": "make_payment_sms",
                    "input": "12345",
                }

                # incorrect zip code x3
                initial_response = test_client.post("/api/v1/livevox/sms", json=init_form)
                assert initial_response.json == \
                       {"error": None,
                        "text_array": ["To set up a payment, please reply with your zip code to confirm "
                                       "your identity. Please note that messages will time out after 1 h"
                                       "our to protect your security."],
                        "finished": False}

                incorrect_zip_code_response_1 = test_client.post("/api/v1/livevox/sms",
                                                                 json=incorrect_zip_code_form)
                assert incorrect_zip_code_response_1.json == \
                       {"error": None, "text_array": ["Sorry, invalid zip code. Try again please."],
                        "finished": False}

                incorrect_zip_code_response_2 = test_client.post("/api/v1/livevox/sms",
                                                                 json=incorrect_zip_code_form)
                assert incorrect_zip_code_response_2.json == \
                       {"error": None, "text_array": ["Sorry, invalid zip code. Try again please."],
                        "finished": False}

                incorrect_zip_code_response_3 = test_client.post("/api/v1/livevox/sms",
                                                             json=incorrect_zip_code_form)
                assert incorrect_zip_code_response_3.json == \
                       {"error": None,
                        "text_array": ["A payment was not made. Please contact an agent "
                                       "for further assistance at 800-712-5407."],
                        "finished": True}


class TestLatePastGracePeriod(TestMakePaymentSMSDelinquent):

    @pytest.fixture
    def mock_customer_lookup_late_past_grace_period(self) -> Mock:
        return awrf.create_mock_response_for_customer_lookup(
            'tests/fixtures/customer_lookups/2021-08-09_customer_id_7.json'
        )

    @pytest.fixture
    def mock_customer_payment_late_past_grace_period(self) -> Mock:
        return awrf.create_mock_responses_for_workflow(
            'tests/fixtures/external_workflows/make_payment/2021-08-09_product_id_7_141828_cent_payment.json'
        )

    @pytest.fixture
    def mock_customer_lookup_late_past_grace_period_cutoff(self) -> Mock:
        return awrf.create_mock_response_for_customer_lookup(
            'tests/fixtures/customer_lookups/2021-08-12_customer_id_68.json'
        )

    @pytest.fixture
    def mock_customer_payment_late_past_grace_period_cutoff_error(self) -> Mock:
        return awrf.create_mock_responses_for_workflow(
            'tests/fixtures/external_workflows/make_payment/'
            '2021-08-12_product_id_126_7296_cent_payment_confirmed_after_cutoff_time.json'
        )

    @pytest.fixture
    def mock_customer_payment_late_past_grace_period_cutoff_success(self) -> Mock:
        return awrf.create_mock_responses_for_workflow(
            'tests/fixtures/external_workflows/make_payment/'
            '2021-08-13_product_id_126_7296_cent_payment.json'
        )

    def test_successful_late_payment_past_grace_period(self, db_session, workflow, self_service_workflow, greeting,
                                                       inbound_routing, test_client,
                                                       mock_customer_lookup_late_past_grace_period,
                                                       mock_customer_payment_late_past_grace_period):
        with patch.object(requests, "get", side_effect=[mock_customer_lookup_late_past_grace_period,
                                                        mock_customer_lookup_late_past_grace_period]):
            with patch.object(requests, "post", side_effect=mock_customer_payment_late_past_grace_period):

                init_form = {
                    "thread_id": "test",
                    "workflow": "make_payment_sms",
                    "initial_settings": {
                        "livevox_account": "Iivr7",
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

                initial_response = test_client.post("/api/v1/livevox/sms", json=init_form)
                assert initial_response.json == \
                       {"error": None,
                        "text_array": ["To set up a payment, please reply with your zip code to confirm your "
                                       "identity. Please note that messages will time out after 1 hour to "
                                       "protect your security."],
                        "finished": False}

                zip_confirmation_and_payment_response = test_client.post("/api/v1/livevox/sms", json=zip_code_form)
                assert zip_confirmation_and_payment_response.json == \
                       {'error': None,
                        'finished': False,
                        'text_array': ['Zipcode confirmed. This is an attempt to collect a debt and any '
                                       'information obtained will be used for that purpose.',
                                       'Your current past due is $1418.28. To authorize one e-payment of '
                                       '$1418.28 on loan ending in 7 from your bank account ending in 965'
                                       '1 for 08/10/21, reply PAY.']}

                authorized_payment_response = test_client.post("/api/v1/livevox/sms", json=pay_form)
                assert authorized_payment_response.json == \
                       {"error": None,
                        "text_array": ["Thanks, a payment of $1418.28 will post to your account on 08/10/21. "
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
                    "select_amount_use_past_due",
                    "Iivr-basic-workflow-branch-step",
                    "confirmation",
                    "branch_to_additional_message",
                    "play_delinquent_message",
                    "confirmation"
                ]
                workflow_run: WorkflowRun = db_session.query(WorkflowRun).first()
                compare_step_branches(correct_branch_sequence, workflow_run)

    def test_payment_confirmed_after_cutoff_time(self, db_session, workflow, greeting, inbound_routing, test_client,
                                                 mock_customer_lookup_late_past_grace_period_cutoff,
                                                 mock_customer_payment_late_past_grace_period_cutoff_error,
                                                 mock_customer_payment_late_past_grace_period_cutoff_success):
        mock_customer_payment = mock_customer_payment_late_past_grace_period_cutoff_error + \
                                mock_customer_payment_late_past_grace_period_cutoff_success
        with patch.object(requests, "get", side_effect=[mock_customer_lookup_late_past_grace_period_cutoff]):
            with patch.object(requests, "post", side_effect=mock_customer_payment):

                init_form = {
                    "thread_id": "test",
                    "workflow": "make_payment_sms",
                    "initial_settings": {
                        "livevox_account": "Iivr68",
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

                initial_response = test_client.post("/api/v1/livevox/sms", json=init_form)
                assert initial_response.json == \
                       {"error": None,
                        "text_array": ["To set up a payment, please reply with your zip code to confirm "
                                       "your identity. Please note that messages will time out after 1 "
                                       "hour to protect your security."],
                        "finished": False}

                zip_confirmation_and_payment_response = test_client.post("/api/v1/livevox/sms", json=zip_code_form)
                assert zip_confirmation_and_payment_response.json == \
                       {'error': None,
                        'finished': False,
                        'text_array': ['Zipcode confirmed. This is an attempt to collect a debt and any '
                                       'information obtained will be used for that purpose.',
                                       'Your current past due is $72.96. To authorize one e-payment of '
                                       '$72.96 on loan ending in 126 from your bank account ending in 6'
                                       '789 for 08/13/21, reply PAY.']}

                confirmed_after_cutoff_response = test_client.post("/api/v1/livevox/sms", json=pay_form)
                assert confirmed_after_cutoff_response.json == \
                       {'error': None,
                        'finished': False,
                        'text_array': ['Sorry, we received your reply after the cut-off time for today. '
                                       'A payment was not made. A new session is being started.',
                                       'Your current past due is $72.96. To authorize one e-payment of '
                                       '$72.96 on loan ending in 126 from your bank account ending in 6'
                                       '789 for 08/16/21, reply PAY.']}

                authorized_payment_response = test_client.post("/api/v1/livevox/sms", json=pay_form)
                assert authorized_payment_response.json == \
                       {"error": None,
                        "text_array": ["Thanks, a payment of $72.96 will post to your account on 08/16/21. "
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
                    "select_amount_use_past_due",
                    "Iivr-basic-workflow-branch-step",
                    "confirmation",
                    "branch_to_additional_message",
                    "play_delinquent_message",
                    "confirmation",
                    "cutoff",
                    "initialize_payment",
                    "Iivr-basic-workflow-branch-step",
                    "pay_with_bank_account_on_file",
                    "Iivr-basic-workflow-branch-step",
                    "pay_on_earliest_date",
                    "cutoff",
                    "Iivr-basic-workflow-branch-step",
                    "select_amount",
                    "select_amount_use_past_due",
                    "Iivr-basic-workflow-branch-step",
                    "confirmation",
                    "branch_to_additional_message",
                    "play_delinquent_message",
                    "confirmation",
                ]
                workflow_run: WorkflowRun = db_session.query(WorkflowRun).first()
                compare_step_branches(correct_branch_sequence, workflow_run)

    def test_failed_payment(self, db_session, workflow, self_service_workflow, greeting, inbound_routing, test_client,
                            mock_customer_lookup_late_past_grace_period_cutoff,
                            mock_customer_payment_late_past_grace_period_cutoff_error):
        mock_customer_payment = mock_customer_payment_late_past_grace_period_cutoff_error + \
                                mock_customer_payment_late_past_grace_period_cutoff_error
        with patch.object(requests, "get", side_effect=[mock_customer_lookup_late_past_grace_period_cutoff]):
            with patch.object(requests, "post", side_effect=mock_customer_payment):
                init_form = {
                    "thread_id": "test",
                    "workflow": "make_payment_sms",
                    "initial_settings": {
                        "livevox_account": "Iivr68",
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
                        'text_array': ['Zipcode confirmed. This is an attempt to collect a debt and any '
                                       'information obtained will be used for that purpose.',
                                       'Your current past due is $72.96. To authorize one e-payment of '
                                       '$72.96 on loan ending in 126 from your bank account ending in 6'
                                       '789 for 08/13/21, reply PAY.']}

                failed_payment_response = test_client.post("/api/v1/livevox/sms", json=pay_form)
                assert failed_payment_response.json == \
                       {"error": None,
                        "text_array": ["Sorry! There was an issue processing your payment. "
                                       "Call 800-712-5407 to speak to an agent."],
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
                    "select_amount_use_past_due",
                    "Iivr-basic-workflow-branch-step",
                    "confirmation",
                    "branch_to_additional_message",
                    "play_delinquent_message",
                    "confirmation",
                    "cutoff",
                    "initialize_payment",
                    "Iivr-basic-workflow-branch-step",
                    "pay_with_bank_account_on_file",
                    "Iivr-basic-workflow-branch-step",
                    "pay_on_earliest_date",
                    "cutoff",
                    "error_processing"
                ]
                workflow_run: WorkflowRun = db_session.query(WorkflowRun).first()
                compare_step_branches(correct_branch_sequence, workflow_run)
