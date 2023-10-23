from flask import Blueprint, jsonify, current_app
from flask_restx import Api

from ivr_gateway.api.endpoints.admin import ns as admin_namespace
from ivr_gateway.api.endpoints.schemas.output.call_routing import inbound_routing_schema
from ivr_gateway.api.endpoints.schemas.output.queue import queue_schema, queue_hours_of_operation_schema, \
    transfer_routing_schema, queue_holiday_schema, full_queue_schema
from ivr_gateway.api.endpoints.twilio import ns as twilio_namespace
from ivr_gateway.api.endpoints.queue import ns as queue_namespace
from ivr_gateway.api.endpoints.telco import ns as telco_namespace
from ivr_gateway.api.endpoints.livevox import ns as livevox_namespace
from ivr_gateway.api.endpoints.call_routing import ns as call_routing_namespace
from ivr_gateway.api.endpoints.schemas.input.admin import (create_admin_user_request_body,
                                                           create_admin_phone_number_request_body,
                                                           create_admin_phone_number_from_user_request_body,
                                                           create_scheduled_call_request_body,
                                                           update_admin_phone_number_request_body,
                                                           update_scheduled_call_request_body,
                                                           update_admin_user_request_body, login_request_body,
                                                           create_scheduled_call_by_workflow_name_request_body)
from ivr_gateway.api.endpoints.schemas.output.admin import (admin_user_schema,
                                                            admin_phone_number_schema,
                                                            admin_call_schema,
                                                            scheduled_call_schema, admin_api_credential_schema,
                                                            token_response_schema)
from ivr_gateway.utils import log_request_info


def get_logger():
    return current_app.logger


api_v1_blueprint = Blueprint('api_v1', __name__, url_prefix='/api/v1')

authorizations = {
    'Bearer Auth': {
        'type': 'apiKey',
        'in': 'header',
        'name': 'Authorization',
        'description': 'Bearer JWT token from the /login endpoint'

    },
}

api = Api(
    api_v1_blueprint,
    version='1.0',
    title='IVR API',
    description='IVR API',
    doc='/docs/',
    validate=True,
    security="Basic Auth",
    authorizations=authorizations
)

api.add_namespace(twilio_namespace)
api.add_namespace(admin_namespace)
api.add_namespace(call_routing_namespace)
api.add_namespace(queue_namespace)
api.add_namespace(telco_namespace)
api.add_namespace(livevox_namespace)


@api_v1_blueprint.before_request
def log_before_request_info():
    log_request_info(get_logger())


@api_v1_blueprint.after_request
def log_after_request(response):
    get_logger().debug('Response Data: %s', response.json)
    return response

@api_v1_blueprint.app_errorhandler(404)
def resource_not_found(e):
    return jsonify(error=str(e)), 404


api.models[login_request_body.name] = login_request_body
api.models[token_response_schema.name] = token_response_schema
api.models[create_admin_user_request_body.name] = create_admin_user_request_body
api.models[create_admin_phone_number_request_body.name] = create_admin_phone_number_request_body
api.models[update_admin_phone_number_request_body.name] = update_admin_phone_number_request_body
api.models[update_scheduled_call_request_body.name] = update_scheduled_call_request_body
api.models[update_admin_user_request_body.name] = update_admin_user_request_body
api.models[create_admin_phone_number_from_user_request_body.name] = create_admin_phone_number_from_user_request_body
api.models[create_scheduled_call_request_body.name] = create_scheduled_call_request_body
api.models[
    create_scheduled_call_by_workflow_name_request_body.name] = create_scheduled_call_by_workflow_name_request_body
api.models[admin_user_schema.name] = admin_user_schema
api.models[admin_phone_number_schema.name] = admin_phone_number_schema
api.models[admin_call_schema.name] = admin_call_schema
api.models[scheduled_call_schema.name] = scheduled_call_schema
api.models[admin_api_credential_schema.name] = admin_api_credential_schema
api.models[inbound_routing_schema.name] = inbound_routing_schema
api.models[queue_schema.name] = queue_schema
api.models[queue_hours_of_operation_schema.name] = queue_hours_of_operation_schema
api.models[transfer_routing_schema.name] = transfer_routing_schema
api.models[queue_holiday_schema.name] = queue_holiday_schema
api.models[full_queue_schema.name] = full_queue_schema
