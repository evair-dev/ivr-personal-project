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


class TestMakePaymentUpcomingPayment:

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

    @pytest.fixture
    def mock_customer_lookup_late_no_upcoming_installment(self) -> Mock:
        return awrf.create_mock_response_for_customer_lookup(
            'tests/fixtures/customer_lookups/2021-01-11_customer_id_12345.json'
        )

    @pytest.fixture
    def mock_customer_payment_no_upcoming_installment(self) -> Mock:
        return awrf.create_mock_responses_for_workflow(
            'tests/fixtures/external_workflows/make_payment/2021-01-11_product_id_3942467_11482_cent_payment.json'
        )


class TestSuccessfulPayment(TestMakePaymentUpcomingPayment):

    def test_successful_payment(self, db_session, workflow, self_service_workflow, greeting, inbound_routing,
                                test_client, mock_customer_lookup_late_no_upcoming_installment,
                                mock_customer_payment_no_upcoming_installment):
        with patch.object(requests, "get", side_effect=[mock_customer_lookup_late_no_upcoming_installment]):
            with patch.object(requests, "post", side_effect=mock_customer_payment_no_upcoming_installment):
                init_form = {
                    "thread_id": "test",
                    "workflow": "make_payment_sms",
                    "initial_settings": {
                        "livevox_account": "Iivr12345",
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
                        'text_array': ['Zipcode confirmed. Your payment amount is $114.82. To '
                                       'authorize one e-payment of $114.82 on loan ending in 2467 '
                                       'from your bank account ending in 8546 for 01/11/',
                                       '21, reply PAY.']}

                authorized_payment_response = test_client.post("/api/v1/livevox/sms", json=pay_form)
                assert authorized_payment_response.json == \
                       {"error": None,
                        "text_array": ["Thanks, a payment of $114.82 will post to your account on 01/11/21. "
                                       "To Cancel, please call 800-712-5407. Have a great day!"],
                        "finished": True}

                correct_branch_sequence = [
                    "root",
                    "get_customer_info",
                    "initialize_payment",
                    "Iivr-basic-workflow-branch-step",
                    "apply_to_future_installments",
                    "Iivr-basic-workflow-branch-step",
                    "pay_with_bank_account_on_file",
                    "Iivr-basic-workflow-branch-step",
                    "pay_on_earliest_date",
                    "Iivr-basic-workflow-branch-step",
                    "pay_amount_due",
                    "Iivr-basic-workflow-branch-step",
                    "confirmation",
                    "branch_to_additional_message",
                    "play_upcoming_payment_message",
                    "confirmation"
                ]
                workflow_run: WorkflowRun = db_session.query(WorkflowRun).first()
                compare_step_branches(correct_branch_sequence, workflow_run)
