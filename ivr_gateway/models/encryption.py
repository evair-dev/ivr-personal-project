import json
import os

from sqlalchemy import String, Column
from sqlalchemy.dialects.postgresql.json import JSONB


class EncryptableJSONB(JSONB):
    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        json_serializer = dialect._json_serializer or json.dumps
        return json_serializer(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        json_deserializer = dialect._json_deserializer or json.loads
        return json_deserializer(value)


active_encryption_key_fingerprint = os.environ["ACTIVE_ENCRYPTION_KEY"]
encryption_key = os.environ[active_encryption_key_fingerprint]


class EncryptionFingerprintedMixin(object):
    encryption_key_fingerprint = Column(String(), nullable=False)

    def __init__(self, *args, **kwargs):
        if kwargs.get("encryption_key_fingerprint", None) is None:
            self.encryption_key_fingerprint = active_encryption_key_fingerprint
            kwargs["encryption_key_fingerprint"] = active_encryption_key_fingerprint
        super().__init__(*args, **kwargs)