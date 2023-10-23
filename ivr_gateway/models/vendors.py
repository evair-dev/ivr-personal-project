import uuid
from datetime import datetime

from sqlalchemy import Column, String, Integer, Float, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy_utils.types.encrypted.encrypted_type import StringEncryptedType, AesEngine

from ivr_gateway.models import Base
from ivr_gateway.models.encryption import encryption_key, EncryptableJSONB, EncryptionFingerprintedMixin

__all__ = ["VendorResponse"]


class VendorResponse(EncryptionFingerprintedMixin, Base):
    __tablename__ = "vendor_response"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    vendor = Column(String, nullable=False)
    request_name = Column(String, nullable=False)
    response_time = Column(Float, nullable=False)
    status_code = Column(Integer, nullable=False)
    headers = Column(StringEncryptedType(EncryptableJSONB, encryption_key, AesEngine, 'pkcs5'),
                     nullable=False, default={})
    error = Column(StringEncryptedType(String, encryption_key, AesEngine, 'pkcs5'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
