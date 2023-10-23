import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Enum, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB

from sqlalchemy.orm import relationship
from sqlalchemy_utils.types.encrypted.encrypted_type import StringEncryptedType, AesEngine

from ivr_gateway.models import Base
from ivr_gateway.models.encryption import encryption_key, EncryptableJSONB, EncryptionFingerprintedMixin
from ivr_gateway.models.enums import Partner, ProductCode, Department, TransferType, ContactType

__all__ = ["Contact", "ContactLeg", "InboundRouting", "Greeting", "TransferRouting"]

from ivr_gateway.services.message import SimpleMessageService


class Contact(EncryptionFingerprintedMixin, Base):
    __tablename__ = "contact"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    global_id = Column(String, index=True)
    device_identifier = Column(String, index=True, nullable=True)
    inbound_target = Column(String, nullable=True)
    customer_id = Column(String, nullable=True)
    secured = Column(DateTime, nullable=True)
    secured_key = Column(String, nullable=True)
    session = Column(StringEncryptedType(EncryptableJSONB, encryption_key, AesEngine, 'pkcs5'),
                     nullable=False, default={})
    admin_call_id = Column(UUID(as_uuid=True), ForeignKey("admin_call.id"), index=True, nullable=True)
    contact_type = Column(Enum(ContactType), nullable=False, default=ContactType.IVR)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    contact_legs = relationship("ContactLeg", back_populates="contact", passive_deletes=True,
                                order_by="ContactLeg.created_at.asc()")
    admin_call = relationship("AdminCall", uselist=False, back_populates="contact")

    def __repr__(self):  # pragma: no cover
        return f"<Call {self.id}, customer_id={self.customer_id}, admin_call_id={self.admin_call_id}>"


class InboundRouting(Base):
    """
    This model represents entries for inbound routing for calls

    Call routings can come inbound from either a phone number or sip trunk depending on how the vendor integration
    is configured

    Call routings are assigned an initial greeting, a workflow to manage the inbound call, and an initial queue to back
    that routing in the event of an issues

    Routings have a priority as there can be multiple routings assigned to a specific phone number or sip trunk as well
    as a "operating_mode" which can be used to filter which routings are used in which operating mode

    Routings also can be marked as "admin" which means they are not available for the gen-pop to access and will trigger
    the admin login/verify flow

    Call routings are the "ingress" point for the IVR gateway thus are always associated with the ivr-gateway
    (so no "backend" specifications)
    """
    __tablename__ = "inbound_routing"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    inbound_target = Column(String, index=True)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflow.id"), index=True, nullable=True)
    greeting_id = Column(UUID(as_uuid=True), ForeignKey("greeting.id"), index=True, nullable=False)
    priority = Column(Integer, default=0, nullable=False)
    admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    active = Column(Boolean, default=False)
    operating_mode = Column(String, nullable=False)
    initial_queue_id = Column(UUID(as_uuid=True), ForeignKey("queue.id"), index=True, nullable=True)
    contact_type = Column(Enum(ContactType), nullable=False, default=ContactType.IVR)

    workflow = relationship("Workflow", uselist=False, back_populates="inbound_routings")
    greeting = relationship("Greeting", uselist=False, back_populates="inbound_routings")
    contact_legs = relationship("ContactLeg", back_populates="inbound_routing", passive_deletes=True,
                                order_by="ContactLeg.created_at.asc()")
    admin_calls = relationship("AdminCall", back_populates="inbound_routing", passive_deletes=True)
    scheduled_calls = relationship("ScheduledCall", back_populates="inbound_routing", passive_deletes=True)
    initial_queue = relationship("Queue", back_populates="inbound_routings")

    def __repr__(self):  # pragma: no cover
        return f"<InboundRouting {self.id}, inbound_target={self.inbound_target}, workflow_id={self.workflow_id}" \
               f"active={self.active}, initial_queue_id={self.initial_queue_id}>"


class ContactLeg(Base):
    __tablename__ = "contact_leg"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    contact_id = Column(UUID(as_uuid=True), ForeignKey("contact.id", ondelete="CASCADE"), index=True, nullable=False)
    inbound_routing_id = Column(UUID(as_uuid=True), ForeignKey("inbound_routing.id", ondelete="CASCADE"), index=True,
                                nullable=True)
    workflow_run_id = Column(UUID(as_uuid=True), ForeignKey("workflow_run.id"), index=True, nullable=True)
    end_time = Column(DateTime, nullable=True)
    contact_system = Column(String, nullable=False)
    contact_system_id = Column(String, nullable=False, index=True)
    previous_call_legs = Column(String, nullable=False, default='/')
    ani = Column(String, index=True, nullable=True)
    dnis = Column(String, nullable=True)
    initial_queue_id = Column(UUID(as_uuid=True), ForeignKey("queue.id"), index=True, nullable=True)
    disposition_type = Column(String, nullable=True)
    disposition_kwargs = Column(JSONB, nullable=True, default={})
    transfer_routing_id = Column(UUID(as_uuid=True), ForeignKey("transfer_routing.id"), index=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    contact = relationship("Contact", back_populates="contact_legs")
    inbound_routing = relationship("InboundRouting", back_populates="contact_legs")
    transfer_routing = relationship("TransferRouting", back_populates="contact_legs")
    workflow_run = relationship("WorkflowRun", uselist=False, back_populates="contact_leg")
    initial_queue = relationship("Queue", back_populates="contact_legs")

    def __repr__(self):  # pragma: no cover
        # TODO: Can incur a DB hit for a repr, not sure we want this, also can error if not loaded potentially
        return f"<CallLeg {self.id}, call.call_id={self.contact_id}>"


class Greeting(Base):
    __tablename__ = "greeting"
    _message_service = SimpleMessageService()

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    partner = Column(Enum(Partner), nullable=True)
    product_code = Column(Enum(ProductCode), nullable=True)
    department = Column(Enum(Department), nullable=True)
    message = Column(String, nullable=False, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    inbound_routings = relationship("InboundRouting", back_populates="greeting")

    def __repr__(self):  # pragma: no cover
        return f"<Greeting {self.id},  message={self.message}>"


class TransferRouting(Base):
    __tablename__ = "transfer_routing"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    transfer_type = Column(Enum(TransferType), nullable=False, default=TransferType.SIP)
    destination = Column(String, nullable=False)
    destination_system = Column(String, nullable=False)
    queue_id = Column(UUID(as_uuid=True), ForeignKey("queue.id"), index=True, nullable=False)
    operating_mode = Column(String, nullable=False)
    priority = Column(Integer, default=0, nullable=False)
    weight = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    queue = relationship("Queue", back_populates="transfer_routings")
    contact_legs = relationship("ContactLeg", back_populates="transfer_routing", order_by="ContactLeg.created_at.asc()")

    def __repr__(self):  # pragma: no cover
        return f"<Transfer {self.id},  destination={self.destination}>"
