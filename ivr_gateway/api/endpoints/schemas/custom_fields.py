import uuid

from flask_restx.fields import String


class UuidString(String):
    @property
    def __schema_example__(self):
        return str(uuid.uuid4())

    def schema(self):
        schema = super(String, self).schema()
        schema["pattern"] = "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
        return schema


class PhoneNumberString(String):
    __schema_example__ = "14108887777"
    description = "String of phone number without any punctuation."

    def schema(self):
        schema = super(String, self).schema()
        schema["pattern"] = "^[0-9]{11,13}$"
        return schema
