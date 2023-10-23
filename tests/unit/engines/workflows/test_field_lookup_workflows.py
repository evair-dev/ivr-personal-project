from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
import requests
from sqlalchemy.orm import Session as SQLAlchemySession

from ivr_gateway.engines.workflows import WorkflowEngine
from ivr_gateway.exit_paths import HangUpExitPath
from ivr_gateway.models.contacts import Contact, ContactLeg, InboundRouting, Greeting
from ivr_gateway.models.queues import Queue
from ivr_gateway.models.workflows import WorkflowRun, Workflow
from ivr_gateway.steps.api.v1 import AddFieldToWorkflowSessionStep, InputStep
from ivr_gateway.steps.config import StepTree, StepBranch, Step
from ivr_gateway.steps.inputs import PhoneNumberInput
from ivr_gateway.steps.result import StepSuccess
from tests.factories import workflow as wcf
from tests.factories import queues as qf


class TestThreeStepGatewayWorkflow:

    @pytest.fixture
    def call(self, db_session) -> Contact:
        call = Contact(global_id=str(uuid4()), device_identifier="2345678901")
        call.session = {}
        db_session.add(call)
        db_session.commit()
        return call

    @pytest.fixture
    def workflow(self, db_session: SQLAlchemySession) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "main_menu", step_tree=StepTree(
            branches=[
                StepBranch(
                    name="root",
                    steps=[
                        Step(
                            name="step-1",
                            step_type=AddFieldToWorkflowSessionStep.get_type_string(),
                            step_kwargs={
                                "field_name": "customer_id",
                                "service_name": "customer_lookup",
                                "lookup_key": "customer_id"
                            }
                        ),
                        Step(
                            name="step-2",
                            step_type=InputStep.get_type_string(),
                            step_kwargs={
                                "input_key": "input_phone_number",
                                "input_prompt": "Please enter your phone number",
                                "input_type": PhoneNumberInput.get_type_string()
                            }
                        ),
                        Step(
                            name="step-3",
                            step_type=AddFieldToWorkflowSessionStep.get_type_string(),
                            step_kwargs={
                                "field_name": "customer_state_of_residence",
                                "service_name": "customer_lookup",
                                "service_overrides": {
                                    "lookup_phone_number": "session.input_phone_number"
                                },
                                "lookup_key": "customer_state_of_residence",
                                "use_cache": False
                            }
                        ),
                        Step(
                            name="step-4",
                            step_type=AddFieldToWorkflowSessionStep.get_type_string(),
                            step_kwargs={
                                "field_name": "loan_id",
                                "service_name": "customer",
                                "lookup_key": "product_id"
                            }
                        ),
                        Step(
                            name="step-5",
                            step_type=AddFieldToWorkflowSessionStep.get_type_string(),
                            step_kwargs={
                                "field_name": "application_id",
                                "service_name": "customer",
                                "lookup_key": "application_id"
                            }
                        ),
                        Step(
                            name="step-6",
                            step_type=AddFieldToWorkflowSessionStep.get_type_string(),
                            step_kwargs={
                                "service_name": "customer",
                                "lookup_key": "product_type",
                                "use_cache": False
                            },
                        ),
                        Step(
                            name="step-7",
                            step_type=AddFieldToWorkflowSessionStep.get_type_string(),
                            step_kwargs={
                                "field_name": "queue_past_due_cents_amount",
                                "service_name": "queue",
                                "lookup_key": "past_due_cents_amount"
                            },
                            exit_path={
                                "exit_path_type": HangUpExitPath.get_type_string(),
                            },
                        )
                    ]
                )
            ]
        ))
        return workflow_factory.create()

    @pytest.fixture
    def queue(self, db_session, workflow: Workflow) -> Queue:
        queue = qf.queue_factory(db_session).create(
            name="test", past_due_cents_amount=5000)
        return queue

    @pytest.fixture
    def greeting(self, db_session) -> Greeting:
        greeting = Greeting(message="test greeting")
        db_session.add(greeting)
        db_session.commit()
        return greeting

    @pytest.fixture
    def call_routing(self, db_session, workflow: Workflow, greeting: Greeting) -> InboundRouting:
        call_routing = InboundRouting(
            inbound_target="+15555555555",
            workflow=workflow,
            active=True,
            greeting=greeting,
            operating_mode="normal"
        )
        db_session.add(call_routing)
        db_session.commit()
        return call_routing

    @pytest.fixture
    def workflow_run(self, db_session: SQLAlchemySession, workflow: Workflow, queue: Queue) -> WorkflowRun:
        run = WorkflowRun(workflow=workflow, workflow_config=workflow.latest_config, current_queue=queue)
        run.session = {}
        db_session.add(run)
        db_session.commit()
        return run

    @pytest.fixture
    def call_leg(self, db_session, call: Contact, call_routing: InboundRouting,
                 workflow_run: WorkflowRun, queue: Queue) -> ContactLeg:
        call_leg = ContactLeg(
            contact=call,
            inbound_routing=call_routing,
            contact_system="test",
            contact_system_id="test",
            ani="2345678901",
            workflow_run=workflow_run,
            initial_queue=queue
        )
        db_session.add(call_leg)
        db_session.commit()
        return call_leg

    @pytest.fixture
    def mock_customer_summary(self) -> Mock:
        search_mock = Mock()
        search_mock.json.return_value = {
            'open_applications': [
                {
                    'id': 123025290,
                    'type': 'installment'
                }
            ],
            'open_products': [{
                'id': 3944960,
                'type': 'Loan',
                'in_grace_period': False,
                'can_make_ach_payment': True,
                'can_run_check_balance_and_quote_payoff': True,
                'past_due_amount_cents': 0,
                'next_payment_date': '2020-11-09',
                'next_payment_amount': '114.82',
                'next_payment_method': 'ach'
            }]
        }
        search_mock.status_code = 200
        return search_mock

    @pytest.fixture
    def mock_customer_lookup(self) -> Mock:
        search_mock = Mock()
        search_mock.json.return_value = {
            "open_applications": [
                {
                    'id': 123025290,
                    'type': 'installment'
                }
            ],
            "open_products": [
                {
                    "id": 2838616,
                    "type": "Loan",
                    "funding_date": "2018-03-21",
                    "active_payoff_quote?": False,
                    "product_type": "installment",
                    "product_subtype": "unsecured",
                    "past_due_amount_cents": 0,
                    "operationally_charged_off?": False,
                    "in_grace_period?": False,
                    "days_late": 0
                }
            ],
            "customer_information": {
                "id": 123456789,
                "state_of_residence": "FL",
                "disaster_relief_plan?": False,
                "last_contact": None
            }
        }
        search_mock.status_code = 200
        return search_mock

    def test_field_lookup(self, db_session: SQLAlchemySession, workflow: Workflow,
                          workflow_run, call_leg, mock_customer_summary, mock_customer_lookup):
        with patch.object(requests, "get",
                          side_effect=[mock_customer_lookup, mock_customer_lookup,
                                       mock_customer_summary, mock_customer_summary]) as mock_get:
            engine = WorkflowEngine(db_session, workflow_run)
            engine.initialize()

            # Run the first step
            assert workflow_run.session.get("customer_id") is None
            result, next_step_or_exit = engine.run_current_workflow_step()
            assert isinstance(next_step_or_exit, InputStep)
            assert isinstance(result, StepSuccess)
            assert workflow_run.session.get("customer_id") == 123456789

            # Run input step
            result, next_step_or_exit = engine.run_current_workflow_step(
                step_input=PhoneNumberInput("phone_number", "2345678901")
            )
            assert isinstance(next_step_or_exit, AddFieldToWorkflowSessionStep)
            assert isinstance(result, StepSuccess)

            assert workflow_run.session.get("customer_state_of_residence") is None
            result, next_step_or_exit = engine.run_current_workflow_step()
            assert isinstance(next_step_or_exit, AddFieldToWorkflowSessionStep)
            assert isinstance(result, StepSuccess)
            assert workflow_run.session.get("customer_state_of_residence") == "FL"

            assert workflow_run.session.get("loan_id") is None
            result, next_step_or_exit = engine.run_current_workflow_step()
            assert isinstance(next_step_or_exit, AddFieldToWorkflowSessionStep)
            assert isinstance(result, StepSuccess)
            assert workflow_run.session.get("loan_id") == 3944960

            assert workflow_run.session.get("application_id") is None
            result, next_step_or_exit = engine.run_current_workflow_step()
            assert isinstance(next_step_or_exit, AddFieldToWorkflowSessionStep)
            assert isinstance(result, StepSuccess)
            assert workflow_run.session.get("application_id") == 123025290
            assert mock_get.call_count == 3

            assert workflow_run.session.get("product_type") is None
            result, next_step_or_exit = engine.run_current_workflow_step()
            assert isinstance(next_step_or_exit, AddFieldToWorkflowSessionStep)
            assert isinstance(result, StepSuccess)
            assert workflow_run.session.get("product_type") == "Loan"

            assert mock_get.call_count == 4
            result, next_step_or_exit = engine.run_current_workflow_step()
            assert isinstance(next_step_or_exit, HangUpExitPath)
            assert isinstance(result, StepSuccess)
            assert workflow_run.session.get("queue_past_due_cents_amount") == 5000

