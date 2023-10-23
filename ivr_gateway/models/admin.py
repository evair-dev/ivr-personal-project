import base64
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy_utils.types.encrypted.encrypted_type import StringEncryptedType, AesEngine

from ivr_gateway.models import Base
from ivr_gateway.models.encryption import encryption_key, EncryptionFingerprintedMixin
from ivr_gateway.models.enums import AdminRole

__all__ = ["AdminUser", "AdminCall", "AdminCallTo", "AdminCallFrom", "AdminPhoneNumber", "ScheduledCall",
           "ApiCredential"]


class AdminUser(Base):
    __tablename__ = "admin_user"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    name = Column(String, nullable=False)
    short_id = Column(String, nullable=True)
    pin = Column(String, nullable=True)
    role = Column(Enum(AdminRole), default=AdminRole.user, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    calls = relationship("AdminCall", back_populates="user")
    phone_numbers = relationship("AdminPhoneNumber", back_populates="user")
    scheduled_calls = relationship("ScheduledCall", uselist=True, back_populates="user")
    api_credentials = relationship("ApiCredential", back_populates="user", cascade="all, delete")

    def __repr__(self):  # pragma: no cover
        return f"<User {self.name}>"


class AdminPhoneNumber(Base):
    __tablename__ = "admin_phone_number"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    name = Column(String, nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("admin_user.id"), index=True, nullable=True)
    phone_number = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("AdminUser", uselist=False, back_populates="phone_numbers")

    def __repr__(self):  # pragma: no cover
        return f"<Admin Phone Number: {self.phone_number} Name: {self.name}>"


class AdminCall(Base):
    __tablename__ = "admin_call"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    contact_system = Column(String, nullable=False)
    contact_system_id = Column(String, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("admin_user.id"), index=True, nullable=False)
    ani = Column(String, nullable=True)
    dnis = Column(String, nullable=True)
    verified = Column(Boolean, nullable=False, default=False)
    original_ani = Column(String, nullable=False)
    original_dnis = Column(String, nullable=False)
    inbound_routing_id = Column(UUID(as_uuid=True), ForeignKey("inbound_routing.id", ondelete="CASCADE"), index=True,
                                nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("AdminUser", uselist=False, back_populates="calls")
    inbound_routing = relationship("InboundRouting", uselist=False, back_populates="admin_calls")
    scheduled_call = relationship("ScheduledCall", uselist=False, back_populates="admin_call", lazy="subquery", passive_deletes=True)
    contact = relationship("Contact", uselist=False, back_populates="admin_call")

    def __repr__(self):  # pragma: no cover
        return f"<Call ID: {self.id} user: {self.user_id}>"


class ScheduledCall(Base):
    __tablename__ = "scheduled_call"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("admin_user.id"), index=True, nullable=False)
    ani = Column(String, nullable=True)
    dnis = Column(String, nullable=True)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflow.id"), index=True, nullable=True)
    workflow_version_tag = Column(String, nullable=True)
    routing_phone_number = Column(String, nullable=True)
    admin_call_id = Column(UUID(as_uuid=True), ForeignKey("admin_call.id", ondelete="CASCADE"), index=True,
                           nullable=True)
    call_routing_id = Column(UUID(as_uuid=True), ForeignKey("inbound_routing.id", ondelete="CASCADE"), index=True,
                             nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("AdminUser", uselist=False, back_populates="scheduled_calls")
    inbound_routing = relationship("InboundRouting", uselist=False, back_populates="scheduled_calls")
    admin_call = relationship("AdminCall", uselist=False, back_populates="scheduled_call")

    def __repr__(self):  # pragma: no cover
        return f"<Scheduled Call ID {self.id}>"


class AdminCallFrom(Base):
    __tablename__ = "admin_call_from"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    short_number = Column(String, nullable=True)
    full_number = Column(String, nullable=False)
    name = Column(String, nullable=True)
    customer = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):  # pragma: no cover
        return f"<Translating {self.short_number} to {self.full_number}>"


class AdminCallTo(Base):
    __tablename__ = "admin_call_to"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    short_number = Column(String, nullable=True)
    full_number = Column(String, nullable=False)
    name = Column(String, nullable=True)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):  # pragma: no cover
        return f"<Translating {self.short_number} to {self.full_number}>"


class ApiCredential(EncryptionFingerprintedMixin, Base):
    __tablename__ = "api_credential"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("admin_user.id"), index=True, nullable=False)
    key = Column(StringEncryptedType(String, encryption_key, AesEngine, 'pkcs5'), nullable=False)
    secret = Column(StringEncryptedType(String, encryption_key, AesEngine, 'pkcs5'), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    user = relationship("AdminUser", back_populates="api_credentials")

    def __repr__(self):  # pragma: no cover
        return f"<ApiCredential {self.key} to user: {self.user_id}>"

    def get_encoded_auth_token(self) -> str:
        return base64.urlsafe_b64encode(bytes(f"{self.key}:{self.secret}", "utf-8")).decode("utf-8")
