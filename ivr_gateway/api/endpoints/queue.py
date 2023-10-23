from flask_httpauth import HTTPTokenAuth
from flask_restx import Namespace

from ivr_gateway.api.endpoints.schemas.output.queue import queue_schema, full_queue_schema
from ivr_gateway.api.v1.resources import APIV1AdminResource
from ivr_gateway.api.exceptions import MissingQueueException
from ivr_gateway.db import session_scope
from ivr_gateway.models.admin import AdminUser
from ivr_gateway.models.enums import AdminRole
from ivr_gateway.services.auth import AuthService

ns = Namespace(name="queue", description="Admin API")

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
@ns.doc("Get and Create Queues")
class QueuesResource(APIV1AdminResource):
    @auth.login_required(role=AUTHORIZED_ROLES)
    @ns.response(200, 'Success', queue_schema)
    @ns.marshal_with(queue_schema)
    def get(self):
        return self.queue_service.get_all_queues()

@ns.route('/<string:queue_name>')
@ns.doc("Get and Update A Queue")
class QueueResource(APIV1AdminResource):
    @auth.login_required(role=AUTHORIZED_ROLES)
    @ns.response(200, 'Success', full_queue_schema)
    @ns.marshal_with(full_queue_schema)
    def get(self, queue_name: str):
        result = self.queue_service.get_queue_by_name(queue_name)
        if result is None:
            raise MissingQueueException("Resource not found.")

        return result


