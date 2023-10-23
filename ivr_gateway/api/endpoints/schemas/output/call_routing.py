from flask_restx import Model, fields as flask_fields

from ivr_gateway.api.endpoints.schemas.custom_fields import UuidString, PhoneNumberString
from ivr_gateway.models.enums import StringEnum


class EnumField(flask_fields.Raw):
    def __init__(self, enum=None, **kwargs):
        self._enum = enum
        super().__init__(**kwargs)

    # def format(self, value):
    #     return AdminRole(value)

    def output(self, key, obj, *args, **kwargs):
        _enum = obj.__getattribute__(key)
        if isinstance(_enum, str):
            return _enum
        elif isinstance(_enum, StringEnum):
            return _enum.value


inbound_routing_schema = Model("Call Routing Response", {
    "id": UuidString(description="UUID string of call routing"),
    "inbound_target": PhoneNumberString(description="phone number associated with call routing"),
    "workflow_id": UuidString(description="UUID string of workflow associated with call routing"),
    "workflow_name": flask_fields.String(attribute='workflow.workflow_name', description="name of workflow associated with call routing"),
    "initial_queue_id": UuidString(description="UUID string of initial queue associated with call routing"),
    "initial_queue_name": flask_fields.String(attribute='initial_queue.name', description="name of initial queue"),
    "greeting_id": UuidString(description="UUID string of greeting associated with call routing"),
    "priority": flask_fields.Integer(description="priority of call routing"),
    "admin": flask_fields.Boolean(description="boolean indicating whether or not call routing is an admin call routing"),
    "active": flask_fields.Boolean(),
    "operating_mode": flask_fields.String(),
    "created_at": flask_fields.DateTime(),
    "updated_at": flask_fields.DateTime()
})
