from uuid import UUID

from flask import request
from flask_httpauth import HTTPTokenAuth
from flask_restx import Namespace

from ivr_gateway.api.endpoints.schemas.output.call_routing import inbound_routing_schema
from ivr_gateway.api.v1.resources import APIV1AdminResource
from ivr_gateway.api.exceptions import MissingInboundRoutingException
from ivr_gateway.db import session_scope
from ivr_gateway.models.admin import AdminUser
from ivr_gateway.models.enums import AdminRole
from ivr_gateway.services.auth import AuthService

ns = Namespace(name="call_routing", description="Admin API")

auth = HTTPTokenAuth()

AUTHORIZED_ROLES = [AdminRole.user, AdminRole.admin]


@auth.verify_token
def verify_token(token: str):
    with session_scope() as session:
        auth_service = AuthService(session)
        return auth_service.get_user_from_token(token)


@auth.get_user_roles
def get_user_roles(user: AdminUser):
    return [user.role]


@ns.route('')
@ns.doc("Get and Create Call Routings")
class CallRoutingsResource(APIV1AdminResource):

    @auth.login_required(role=AUTHORIZED_ROLES)
    @ns.response(200, 'Success', inbound_routing_schema)
    @ns.marshal_with(inbound_routing_schema)
    def get(self):
        phone_number = request.args.get("phone_number", None)
        if phone_number is not None:
            return self.call_service.get_routings_for_number(phone_number)
        include_admin = request.args.get("include_admin", "false") == "true"
        return self.call_service.get_all_call_routings(include_admin=include_admin)


@ns.route('/<uuid:call_routing_id>')
@ns.doc("Get and Update Call Routing")
class SingleCallRoutingsResource(APIV1AdminResource):
    @auth.login_required(role=AUTHORIZED_ROLES)
    @ns.response(200, 'Success', inbound_routing_schema)
    @ns.marshal_with(inbound_routing_schema)
    def get(self, call_routing_id: UUID):
        result = self.call_service.get_call_routing(call_routing_id)
        if result is None:
            raise MissingInboundRoutingException("Resource not found.")

        return result

