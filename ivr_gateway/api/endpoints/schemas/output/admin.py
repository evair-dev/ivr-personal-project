from flask_restx import Model, fields as flask_fields

from ivr_gateway.api.endpoints.schemas.custom_fields import UuidString, PhoneNumberString
from ivr_gateway.models.enums import AdminRole, StringEnum


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


token_response_schema = Model(
    "Login Admin User Response",
    {
        "token": flask_fields.String(description="API token for use in admin API")
    }
)

admin_user_schema = Model("Admin User Response", {
    "id": UuidString(description="UUID of Admin User"),
    "name": flask_fields.String(description="Name of Admin User"),
    "short_id": flask_fields.String(description="Short sequence of integers to quickly identify admin for purposes of running admin call"),
    "role": EnumField(enum=[x.name for x in AdminRole], description="role of admin user", example="user"),
    "created_at": flask_fields.DateTime(),
    "updated_at": flask_fields.DateTime()
})

admin_phone_number_schema = Model("Admin Phone Number Response", {
    "id": UuidString(description="UUID of phone number"),
    "name": flask_fields.String(description="Name of phone number"),
    "user_id": UuidString(description="UUID of associated Admin User"),
    "phone_number": PhoneNumberString(),
    "created_at": flask_fields.DateTime(),
    "updated_at": flask_fields.DateTime()
})

admin_api_credential_schema = Model("Admin Create Credential Response", {
    "id": UuidString(description="UUID of admin credential"),
    "user_id": UuidString(description="UUID of associated Admin User"),
    "key": flask_fields.String(description="API key for admin user"),
    "secret": flask_fields.String(description="API secret key for admin user"),
    "active": flask_fields.Boolean(),
    "created_at": flask_fields.DateTime(),
})


admin_call_schema = Model("Admin Call Response", {
    "id": UuidString(description="UUID of admin call"),
    "contact_system": flask_fields.String(description="string name of telephony system"),
    "contact_system_id": flask_fields.String(description="string ID of telephony system"),
    "user_id": UuidString(description="UUID of associated Admin User"),
    "ani": PhoneNumberString(description="String of phone number to sending scheduled call"),
    "dnis": PhoneNumberString(description="String of phone number to receive scheduled call"),
    "verified": flask_fields.Boolean(),
    "original_ani": PhoneNumberString(description="String of original phone number to sending admin call"),
    "original_dnis": PhoneNumberString(description="String of original phone number to receiving admin call"),
    "inbound_routing_id": UuidString(description="UUID of associated call routing"),
    "created_at": flask_fields.DateTime(),
    "updated_at": flask_fields.DateTime()
})

scheduled_call_schema = Model("Scheduled Call Response", {
    "id": UuidString(description="UUID string of scheduled call"),
    "user_id": UuidString(description="UUID of associated Admin User"),
    "ani": PhoneNumberString(description="String of phone number to sending scheduled call"),
    "dnis": PhoneNumberString(description="String of phone number to receive scheduled call"),
    "admin_call_id": UuidString(description="UUID string of admin call to associated with scheduled call"),
    "inbound_routing_id": UuidString(description="UUID string of call routing to associated with scheduled call"),
    "workflow_id": UuidString(description="UUID string of workflow to associated with scheduled call"),
    "workflow_version_tag": flask_fields.String(description="Tag or version SHA indicating version of workflow to be run by scheduled call"),
    "created_at": flask_fields.DateTime(),
    "updated_at": flask_fields.DateTime()
})