import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Integer, Time, Date, UniqueConstraint, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from ivr_gateway.models import Base
from ivr_gateway.models.enums import Partner, ProductCode, Department, ContactType

__all__ = ["Queue", "QueueHoursOfOperation", "QueueHoliday"]


class Queue(Base):
    __tablename__ = "queue"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    name = Column(String, nullable=False, index=True, unique=True)
    active = Column(Boolean, default=False, nullable=False)
    timezone = Column(String, nullable=False, default="America/Chicago")
    emergency_mode = Column(Boolean, default=False, nullable=False)
    emergency_message = Column(String, nullable=True)
    past_due_cents_amount = Column(Integer, nullable=False, default=0)
    queue_contact_type = Column(Enum(ContactType), nullable=False, default="IVR")
    partner = Column(Enum(Partner), nullable=False)
    product = Column(Enum(ProductCode), nullable=True)
    department = Column(Enum(Department), nullable=True)
    closed_message = Column(String, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    inbound_routings = relationship("InboundRouting", back_populates="initial_queue")
    contact_legs = relationship("ContactLeg", back_populates="initial_queue")
    transfer_routings = relationship("TransferRouting", back_populates="queue")
    workflow_runs = relationship("WorkflowRun", back_populates="current_queue")
    hours_of_operation = relationship("QueueHoursOfOperation", back_populates="queue")
    holidays = relationship("QueueHoliday", back_populates="queue")


class QueueHoursOfOperation(Base):
    __tablename__ = "queue_hours_of_operation"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    queue_id = Column(UUID(as_uuid=True), ForeignKey("queue.id"), index=True, nullable=False)
    day_of_week = Column(Integer, nullable=False)
    start_time = Column(Time(timezone=False), nullable=False)
    end_time = Column(Time(timezone=False), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    queue = relationship("Queue", uselist=False, back_populates="hours_of_operation")


class QueueHoliday(Base):
    __tablename__ = "queue_holiday"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    queue_id = Column(UUID(as_uuid=True), ForeignKey("queue.id"), index=True, nullable=False)
    date = Column(Date, nullable=False)
    name = Column(String, nullable=False)
    message = Column(String, nullable=True)
    start_time = Column(Time(timezone=False), nullable=True)
    end_time = Column(Time(timezone=False), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    queue = relationship("Queue", uselist=False, back_populates="holidays")

    __table_args__ = (
        UniqueConstraint('queue_id', 'date', name='queue_holiday_one_holiday_for_queue_date_unique_constraint'),
    )
