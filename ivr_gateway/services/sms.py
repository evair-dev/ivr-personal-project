from datetime import datetime

from sqlalchemy.orm import joinedload
from sqlalchemy.orm.session import Session as SQLAlchemySession

from ivr_gateway.models.contacts import ContactLeg, Contact, InboundRouting
from ivr_gateway.models.enums import ContactType
from ivr_gateway.models.workflows import WorkflowRun
from ivr_gateway.services.workflows import WorkflowService
from ivr_gateway.utils import trailing_digits


class SmsService:
    def __init__(self, db_session: SQLAlchemySession):
        self.session = db_session
        self.workflow_service = WorkflowService(db_session)

    def get_active_contact_leg_for_sms_system_and_id(self, contact_system: str, contact_system_id: str) -> ContactLeg:
        sms_leg = (self.session.query(ContactLeg)
                    .options(joinedload(ContactLeg.workflow_run).subqueryload(WorkflowRun.workflow_step_runs),
                             joinedload(ContactLeg.contact))
                    .filter(ContactLeg.contact_system_id == contact_system_id)
                    .filter(ContactLeg.contact_system == contact_system)
                    .filter(ContactLeg.end_time.is_(None))
                    .first())
        return sms_leg

    def create_sms_leg(self, contact: Contact, contact_system: str, contact_system_id: str,
                       inbound_routing: InboundRouting, inital_settings: dict) -> ContactLeg:
        """
        Used to construct a fresh sms leg from
        :param contact:
        :param contact_system:
        :param contact_system_id:
        :param inbound_routing:
        :param inital_settings:
        :return:
        """
        workflow = self.workflow_service.get_workflow_for_id(inbound_routing.workflow_id)
        workflow_run = WorkflowRun(current_queue=inbound_routing.initial_queue, workflow=workflow,
                                   workflow_config=workflow.active_config, session={})
        leg = ContactLeg()
        leg.contact_system = contact_system
        leg.contact_system_id = contact_system_id
        leg.contact = contact
        leg.inbound_routing = inbound_routing
        leg.initial_queue = inbound_routing.initial_queue
        leg.workflow_run = workflow_run
        workflow_run.session.update(inital_settings)
        self.session.add(workflow_run)
        self.session.add(leg)
        self.session.commit()
        return leg

    def end_sms_leg(self, sms_leg: ContactLeg, disposition_type: str, disposition_kwargs: dict = None):
        if sms_leg is None or sms_leg.end_time is not None:
            return
        sms_leg.end_time = datetime.now()
        sms_leg.disposition_type = disposition_type
        sms_leg.disposition_kwargs = disposition_kwargs or {}
        self.session.add(sms_leg)
        self.session.commit()

    def transfer_sms_leg_to_workflow(self, sms_leg: ContactLeg, workflow_name: str) -> ContactLeg:
        workflow = self.workflow_service.get_workflow_by_name(workflow_name)
        current_queue = sms_leg.workflow_run.current_queue
        workflow_run = WorkflowRun(
            workflow=workflow, current_queue=current_queue, workflow_config=workflow.active_config
        )

        new_leg = ContactLeg()
        new_leg.contact = sms_leg.contact
        new_leg.contact_system = sms_leg.contact_system
        new_leg.contact_system_id = sms_leg.contact_system_id

        new_leg.workflow_run = workflow_run

        self.session.add(workflow_run)
        self.session.add(new_leg)
        self.session.commit()

        return new_leg

    def create_sms_contact(self, contact_system: str, contact_system_id: str, inbound_routing: InboundRouting,
                           device: str, target: str, initial_settings: dict) -> Contact:
        sms = Contact()
        sms.contact_type = ContactType.SMS
        sms.device_identifier = device
        sms.inbound_target = target
        if "customer_id" in initial_settings:
            sms.customer_id = initial_settings["customer_id"]
        elif "livevox_account" in initial_settings:
            sms.customer_id = trailing_digits(initial_settings["livevox_account"])
        else:
            sms.customer_id = None
        sms.session = {}
        sms.session.update(initial_settings)
        sms.global_id = f"{contact_system}:{contact_system_id}"
        sms.contact_type = ContactType.SMS
        self.session.add(sms)
        self.session.commit()
        self.create_sms_leg(sms, contact_system, contact_system_id, inbound_routing, initial_settings)

        return sms

    def get_routing_for_number(self, phone_number: str) -> InboundRouting:
        return (self.session.query(InboundRouting)
                .options(joinedload(InboundRouting.greeting), joinedload(InboundRouting.initial_queue),
                         joinedload(InboundRouting.workflow))
                .filter(InboundRouting.inbound_target == phone_number)
                .filter(InboundRouting.active)
                .first())
