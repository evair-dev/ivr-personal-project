from typing import Dict, Optional
from uuid import uuid4

from sqlalchemy import orm

from ivr_gateway.models.contacts import Contact, Greeting, InboundRouting, ContactLeg
from ivr_gateway.models.enums import ContactType
from ivr_gateway.models.workflows import Workflow, WorkflowRun
from ivr_gateway.services.workflows import WorkflowService
from ivr_gateway.steps.config import Step, StepTree, StepBranch
from tests.factories.workflow import workflow_factory


class BaseStepTestMixin:

    @staticmethod
    def create_call(db_session) -> Contact:
        call = Contact(global_id=str(uuid4()), contact_type=ContactType.IVR)
        db_session.add(call)
        db_session.commit()
        return call

    @staticmethod
    def create_greeting(db_session) -> Greeting:
        greeting = Greeting(message="test greeting")
        db_session.add(greeting)
        db_session.commit()
        return greeting

    @staticmethod
    def create_workflow(db_session: orm.Session, step_template: Step) -> Workflow:
        factory = workflow_factory(db_session, "main_menu", step_tree=StepTree(
            branches=[
                StepBranch(
                    name="root",
                    steps=[
                        step_template
                    ]
                )
            ]
        ))
        return factory.create()

    @staticmethod
    def add_call_routing_to_workflow(db_session, workflow: Workflow, greeting: Greeting) -> InboundRouting:
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

    @staticmethod
    def create_call_leg_for_call_routing(db_session, contact: Contact, inbound_routing: InboundRouting,
                                         workflow_run: WorkflowRun) -> ContactLeg:
        call_leg = ContactLeg(
            contact=contact,
            inbound_routing=inbound_routing,
            contact_system="test",
            contact_system_id="test",
            workflow_run=workflow_run
        )
        db_session.add(call_leg)
        db_session.commit()
        return call_leg

    @staticmethod
    def create_workflow_run(db_session: orm.Session, workflow: Workflow,
                            workflow_session: Dict = None) -> WorkflowRun:
        workflow_session = workflow_session or {}
        run = WorkflowRun(workflow=workflow, workflow_config=workflow.latest_config, session=workflow_session)
        db_session.add(run)
        db_session.commit()
        return run

    @staticmethod
    def create_workflow_step(db_session: orm.Session, workflow_run: WorkflowRun) -> Step:
        workflow_service = WorkflowService(db_session)
        step = workflow_service.create_step_for_workflow(
            workflow_run,
            workflow_run.workflow.latest_config.step_tree.branches[0].steps[0].name
        )
        workflow_run.initialize_first_step.set(step)
        db_session.add_all(workflow_run.step_runs)
        db_session.add(workflow_run)
        db_session.commit()
        return step

    def create_test_objects_for_step_template(self, db_session: orm.Session,
                                              step_template: Step,
                                              workflow_session: Optional[Dict] = None):
        call = self.create_call(db_session)
        greeting = self.create_greeting(db_session)
        workflow = self.create_workflow(db_session, step_template)
        call_routing = self.add_call_routing_to_workflow(db_session, workflow, greeting)
        workflow_run = self.create_workflow_run(db_session, workflow, workflow_session=workflow_session)
        call_leg = self.create_call_leg_for_call_routing(db_session, call, call_routing, workflow_run)
        step = self.create_workflow_step(db_session, workflow_run)
        return (
            call,
            call_leg,
            call_routing,
            greeting,
            workflow,
            workflow_run,
            step
        )
