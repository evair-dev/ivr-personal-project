from flask_restx import Model, fields as flask_fields

from ivr_gateway.api.endpoints.schemas.custom_fields import UuidString
from ivr_gateway.models.enums import StringEnum, TransferType, Partner, ProductCode, Department


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


queue_schema = Model("Queue Response", {
    "id": UuidString(description="UUID string of queue"),
    "name": flask_fields.String(description="name of queue"),
    "active": flask_fields.Boolean(),
    "timezone": flask_fields.String(description="timezone of queue"),
    "emergency_mode": flask_fields.String(description="is queue in emergency mode"),
    "emergency_message": flask_fields.String(description="emergency mode message for queue"),
    "past_due_cents_amount": flask_fields.Integer(description="past due amount in cents associated with queue"),
    "partner": EnumField(enum=Partner, example="Iivr"),
    "product": EnumField(enum=ProductCode, example="LN"),
    "department": EnumField(enum=Department, example="CUS"),
    "created_at": flask_fields.DateTime(),
    "updated_at": flask_fields.DateTime()
})

queue_hours_of_operation_schema = Model("Queue Hours Of Operation Response", {
    "id": UuidString(description="UUID string of queue hours of operation"),
    "queue_id": UuidString(description="UUID string of queue associated with hours of operation record"),
    "day_of_week": flask_fields.Integer(),
    "start_time": flask_fields.String(),
    "end_time": flask_fields.String(),
    "created_at": flask_fields.DateTime(),
    "updated_at": flask_fields.DateTime()
})

transfer_routing_schema = Model("Transfer Routing Response", {
    "id": UuidString(),
    "transfer_type": EnumField(enum=TransferType, example="PSTN"),
    "destination": flask_fields.String(),
    "destination_system": flask_fields.String(),
    "queue_id": flask_fields.String(),
    "priority": flask_fields.Integer(),
    "operating_mode": flask_fields.String(),
    "created_at": flask_fields.DateTime(),
    "updated_at": flask_fields.DateTime()
})

full_queue_schema = queue_schema.inherit("Full Queue Response", {
    "hours_of_operation": flask_fields.List(flask_fields.Nested(queue_hours_of_operation_schema)),
    "transfer_routings": flask_fields.List(flask_fields.Nested(transfer_routing_schema)),
})

queue_holiday_schema = Model("Queue Holiday Response", {
    "id": UuidString(),
    "queue_id": flask_fields.String(),
    "date": flask_fields.Date(),
    "name": flask_fields.String(),
    "message": flask_fields.String(),
    "created_at": flask_fields.DateTime(),
    "updated_at": flask_fields.DateTime()
})
