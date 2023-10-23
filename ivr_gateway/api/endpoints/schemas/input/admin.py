from flask_restx import Model, fields as flask_fields

from ivr_gateway.api.endpoints.schemas.custom_fields import UuidString, PhoneNumberString

login_request_body = Model(
    "Login Admin User",
    {
        "api_key": flask_fields.String(required=True, description="IVR Gateway API Key"),
        "api_secret": flask_fields.String(required=True, description="IVR Gateway API Secret Key")
    }
)

create_admin_user_request_body = Model(
    "Create Admin User",
    {
        "name": flask_fields.String(required=True, description="Name of admin user"),
        "short_id": flask_fields.String(required=True, description="Short sequence of integers to quickly identify admin for purposes of running admin call"),
        "pin": flask_fields.String(required=True, description="Sequence of integers used as a pin number for user"),
        "role": flask_fields.String(required=False, default="user", description="Role of user (user or admin)"),
    }
)

update_admin_user_request_body = Model(
    "Update Admin User",
    {
        "name": flask_fields.String(required=False, description="Name of admin user"),
        "short_id": flask_fields.String(required=False, description="Short sequence of integers to quickly identify admin for purposes of running admin call"),
        "pin": flask_fields.String(required=False, description="Sequence of integers used as a pin number for user"),
        "role": flask_fields.String(required=False, default="user", description="Role of user (user or admin)"),
    }
)

create_admin_phone_number_request_body = Model(
    "Create Admin Phone Number",
    {
        "user_id": UuidString(required=True, description="UUID string of an admin user to be associated with phone number"),
        "phone_number": PhoneNumberString(required=True),
        "name": flask_fields.String(required=True, description="name for phone number")
    }
)


create_admin_phone_number_from_user_request_body = Model(
    "Create Admin Phone Number from User",
    {
        "phone_number": PhoneNumberString(required=True),
        "name": flask_fields.String(required=True, description="name for phone number")
    }
)


update_admin_phone_number_request_body = Model(
    "Update Admin Phone Number",
    {
        "user_id": UuidString(required=False, description="UUID string of an admin user to be associated with phone number"),
        "phone_number": PhoneNumberString(required=False),
        "name": flask_fields.String(required=False, description="name for phone number")
    }
)

create_scheduled_call_request_body = Model(
    "Create Scheduled Call",
    {
        "user_id": UuidString(required=True, description="UUID string of an admin user to be associated with scheduled call"),
        "ani": PhoneNumberString(required=True, description="String of phone number to sending scheduled call"),
        "dnis": PhoneNumberString(required=True, description="String of phone number to receive scheduled call"),
        "call_routing_id": UuidString(required=True, description="UUID string of call routing record associated with scheduled call")
    }
)

update_scheduled_call_request_body = Model(
    "Update Scheduled Call",
    {
        "user_id": PhoneNumberString(required=False, description="UUID string of an admin user to be associated with scheduled call"),
        "ani": PhoneNumberString(required=False, description="String of phone number to sending scheduled call"),
        "dnis": PhoneNumberString(required=False, description="String of phone number to receive scheduled call"),
        "call_routing_id": UuidString(required=False, description="UUID string of call routing record associated with scheduled call")
    }
)

create_scheduled_call_by_workflow_name_request_body = Model(
    "Create Scheduled Call By Workflow Name",
    {
        "user_id": UuidString(required=True, description="UUID string of an admin user to be associated with scheduled call"),
        "ani": PhoneNumberString(required=False, description="String of phone number to sending scheduled call"),
        "dnis": PhoneNumberString(required=False, description="String of phone number to receive scheduled call"),
        "workflow_name": flask_fields.String(required=True, description="Name of workflow to be run for scheduled call"),
        "workflow_version_tag": flask_fields.String(required=False, description="Tag or version SHA indicating version of workflow to be run by scheduled call")
    }
)





