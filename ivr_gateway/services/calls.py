import os
from datetime import datetime, timedelta
from textwrap import dedent
from typing import Optional, Dict, List
from uuid import UUID

from sqlalchemy.orm import joinedload
from sqlalchemy.orm.session import Session as SQLAlchemySession

from ivr_gateway.models.admin import ScheduledCall
from ivr_gateway.models.contacts import ContactLeg, Contact, InboundRouting, TransferRouting, Greeting
from ivr_gateway.models.enums import OperatingMode
from ivr_gateway.models.queues import Queue
from ivr_gateway.models.workflows import WorkflowRun
from ivr_gateway.services.workflows import WorkflowService
from ivr_gateway.logger import ivr_logger


class CallService:
    def __init__(self, db_session: SQLAlchemySession):
        self.session = db_session
        self.workflow_service = WorkflowService(db_session)

    def get_active_call_leg_for_call_system_and_id(self, telephony_system: str, telephony_system_id: str) -> ContactLeg:
        call_leg = (self.session.query(ContactLeg)
                    .options(joinedload(ContactLeg.workflow_run).subqueryload(WorkflowRun.workflow_step_runs),
                             joinedload(ContactLeg.contact))
                    .filter(ContactLeg.contact_system_id == telephony_system_id)
                    .filter(ContactLeg.contact_system == telephony_system)
                    .filter(ContactLeg.end_time.is_(None))
                    .first())
        return call_leg

    def create_call_leg_from_scheduled_call(self, scheduled_call, call):
        workflow = self.workflow_service.get_workflow_for_id(scheduled_call.workflow_id)

        workflow_config = None
        if scheduled_call.workflow_version_tag:
            workflow_config = self.workflow_service.get_config_for_sha_or_tag(workflow,
                                                                              scheduled_call.workflow_version_tag)
        workflow_run = WorkflowRun(workflow=workflow, workflow_config=workflow_config or workflow.active_config)
        leg = ContactLeg()
        admin_call = scheduled_call.admin_call
        leg.contact_system = admin_call.contact_system
        leg.contact_system_id = admin_call.contact_system_id
        leg.contact = call
        leg.ani = scheduled_call.ani
        leg.dnis = scheduled_call.dnis
        leg.workflow_run = workflow_run
        self.session.add(workflow_run)
        self.session.add(leg)
        self.session.commit()
        return leg

    def create_call_leg(self, call: Contact, telephony_system: str, telephony_system_id: str, call_routing: InboundRouting,
                        ani: Optional[str], dnis: Optional[str]) -> ContactLeg:
        """
        Used to construct a fresh call leg from
        :param call:
        :param telephony_system:
        :param telephony_system_id:
        :param call_routing:
        :param ani:
        :param dnis:
        :return:
        """
        workflow = self.workflow_service.get_workflow_for_id(call_routing.workflow_id)
        workflow_run = WorkflowRun(current_queue=call_routing.initial_queue, workflow=workflow,
                                   workflow_config=workflow.active_config)
        leg = ContactLeg()
        leg.contact_system = telephony_system
        leg.contact_system_id = telephony_system_id
        leg.contact = call
        leg.inbound_routing = call_routing
        leg.ani = ani
        leg.dnis = dnis
        leg.initial_queue = call_routing.initial_queue
        leg.workflow_run = workflow_run
        self.session.add(workflow_run)
        self.session.add(leg)
        self.session.commit()
        return leg

    def end_call_leg(self, call_leg: ContactLeg, disposition_type: str, disposition_kwargs: dict = None):
        if call_leg is None or call_leg.end_time is not None:
            return
        call_leg.end_time = datetime.now()
        call_leg.disposition_type = disposition_type
        call_leg.disposition_kwargs = disposition_kwargs or {}
        self.session.add(call_leg)
        self.session.commit()

    def transfer_call_leg_to_workflow(self, call_leg: ContactLeg, workflow_name: str) -> ContactLeg:
        workflow = self.workflow_service.get_workflow_by_name(workflow_name)
        current_queue = call_leg.workflow_run.current_queue
        workflow_run = WorkflowRun(
            workflow=workflow, current_queue=current_queue, workflow_config=workflow.active_config
        )

        new_leg = ContactLeg()
        new_leg.contact = call_leg.contact
        new_leg.contact_system = call_leg.contact_system
        new_leg.contact_system_id = call_leg.contact_system_id

        new_leg.workflow_run = workflow_run

        self.session.add(workflow_run)
        self.session.add(new_leg)
        self.session.commit()

        return new_leg

    def create_call_from_scheduled_call(self, scheduled_call: ScheduledCall) -> Contact:
        call = Contact()
        call.device_identifier = scheduled_call.ani
        call.inbound_target = scheduled_call.dnis
        call.session = {}
        admin_call = scheduled_call.admin_call
        call.global_id = f"{admin_call.contact_system}:{admin_call.contact_system_id}"
        self.session.add(call)
        self.session.commit()
        self.create_call_leg_from_scheduled_call(scheduled_call, call)
        return call

    def create_call(self, telephony_system: str, telephony_system_id: str, call_routing: InboundRouting, ani: str,
                    dnis: str) -> Contact:
        call = Contact()
        call.device_identifier = ani
        call.inbound_target = dnis
        call.session = {}
        call.global_id = f"{telephony_system}:{telephony_system_id}"
        self.session.add(call)
        self.session.commit()
        self.create_call_leg(call, telephony_system, telephony_system_id, call_routing, ani, dnis)
        return call

    def get_greeting_by_id(self, greeting_id: UUID):
        return (self.session.query(Greeting).filter(Greeting.id == greeting_id).first())

    def get_greeting_by_message(self, greeting_message: str):
        return (self.session.query(Greeting).filter(Greeting.message == greeting_message).first())

    def create_greeting_if_not_exists(self, greeting_message: str):
        greeting = self.get_greeting_by_message(greeting_message=greeting_message)
        if not greeting:
            greeting = Greeting(message=greeting_message)
            self.session.add(greeting)
            self.session.commit()
        return greeting

    def get_routing_for_number(self, phone_number: str) -> InboundRouting:
        return (self.session.query(InboundRouting)
                .options(joinedload(InboundRouting.greeting), joinedload(InboundRouting.initial_queue),
                         joinedload(InboundRouting.workflow))
                .filter(InboundRouting.inbound_target == phone_number)
                .filter(InboundRouting.active)
                .first())

    def get_routings_for_numbers_in_list(self, phone_numbers: List[str]):
        return self.session.query(InboundRouting).filter(InboundRouting.inbound_target.in_(phone_numbers)).all()

    def get_routings_for_number(self, phone_number: str) -> List[InboundRouting]:
        return (self.session.query(InboundRouting)
                .options(joinedload(InboundRouting.greeting), joinedload(InboundRouting.initial_queue),
                         joinedload(InboundRouting.workflow))
                .filter(InboundRouting.inbound_target == phone_number)
                .order_by(InboundRouting.priority.desc())
                .all())

    def get_all_call_routings(self, include_admin=False) -> List[InboundRouting]:
        query = self.session.query(InboundRouting).options(joinedload(InboundRouting.greeting),
                                                           joinedload(InboundRouting.initial_queue),
                                                           joinedload(InboundRouting.workflow))
        if not include_admin:
            query = query.filter(InboundRouting.admin == include_admin)
        return query.order_by(InboundRouting.initial_queue_id.desc()).all()

    def get_call_routing(self, call_routing_id: UUID) -> InboundRouting:
        return self.session.query(InboundRouting).options(joinedload(InboundRouting.greeting),
                                                          joinedload(InboundRouting.initial_queue),
                                                          joinedload(InboundRouting.workflow)).get(call_routing_id)

    def get_transfer_routings_for_queue(self, queue: Queue) -> List[TransferRouting]:
        return (self.session.query(TransferRouting)
                .join(TransferRouting.queue)
                .filter(Queue.id == queue.id)
                .order_by(TransferRouting.priority.asc())
                .all())

    def get_sip_headers(self, call_leg: ContactLeg) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        contact = call_leg.contact
        if contact.secured_key is not None:
            headers["X-Ava-Secure-Key"] = contact.secured_key
        headers["X-Ava-Call-ID"] = contact.global_id
        if contact.customer_id is not None:
            headers["X-Ava-Customer-ID"] = contact.customer_id
        ani = contact.device_identifier
        dnis = contact.inbound_target
        headers["X-Ava-Tele-Info"] = f"${ani}:${dnis}"
        return headers

    def get_system_operating_mode(self) -> OperatingMode:
        """
        Returns the operational mode of the system used to determine routing short circuiting
        :return:
        """
        is_in_emergency_mode = os.getenv("IVR_IVR_SYSTEM_EMERGENCY_MODE", False) == "true"
        return OperatingMode.EMERGENCY if is_in_emergency_mode else OperatingMode.NORMAL

    def get_system_wide_emergency_message(self):
        return " ".join(dedent("""
        Due to unforeseen circumstances our customer support center is currently closed and we're unable to take
        your call. We apologize for any inconvenience this may have caused you. Please check our website at
        www.Iivr.com for further updates or try your call again later.
        """).split("\n"))

    def get_most_recent_call(self, ani: str) -> Optional[Contact]:
        most_recent_call = (self.session.query(Contact)
                            .options(joinedload(Contact.contact_legs).subqueryload(ContactLeg.transfer_routing))
                            .filter(Contact.device_identifier == ani)
                            .order_by(Contact.created_at.desc())
                            .first())
        return most_recent_call

    def get_most_recent_call_leg(self, ani: str) -> Optional[ContactLeg]:

        # call_leg = (self.session.query(CallLeg)
        #             .options(joinedload(CallLeg.call), joinedload(CallLeg.transfer_routing))
        #             .filter(Call.ani == ani)
        #             .order_by(CallLeg.created_at.desc())
        #             .first())
        most_recent_call = self.get_most_recent_call(ani)

        if most_recent_call is None:
            ivr_logger.warning(f"call missing: {ani}")
            return None

        if len(most_recent_call.contact_legs) == 0:
            ivr_logger.warning(f"no call legs: {ani}")
            return None

        most_recent_call_leg = most_recent_call.contact_legs[0]
        for call_leg in most_recent_call.contact_legs:
            if call_leg.created_at > most_recent_call_leg.created_at:
                most_recent_call_leg = call_leg

        return most_recent_call_leg

    def get_recent_transferred_call(self, ani: str, dnis: str) -> (Optional[Contact], Optional[str]):
        most_recent_call_leg = self.get_most_recent_call_leg(ani)
        if most_recent_call_leg is None:
            return None, "no call"

        transfer_routing = most_recent_call_leg.transfer_routing
        if transfer_routing is None:
            ivr_logger.warning(f"no transfer routing: {ani}")
            return None, "not transferred"
        if transfer_routing.destination != dnis:
            ivr_logger.warning(f"mismatched transfer routing destination call dnis: {dnis} actual destination: {transfer_routing.destination}")
            return None, "dnis mismatch"

        if most_recent_call_leg.end_time < (datetime.now() - timedelta(minutes=1)):
            ivr_logger.warning(f"most recent call too old: {most_recent_call_leg.end_time}")
            return None, "call too old"
        return most_recent_call_leg.contact, None

    def set_active_routings_inactive(self, active_routings: List[InboundRouting]) -> List[InboundRouting]:
        inactive_routings = []

        for routing in active_routings:
            routing.active = False
            inactive_routings.append(routing)
            self.session.add(routing)
            self.session.commit()

        return inactive_routings
