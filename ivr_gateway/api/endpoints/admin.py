from uuid import UUID

from flask import request
from flask_httpauth import HTTPTokenAuth
from flask_restx import Namespace

from ivr_gateway.api.endpoints.schemas.input.admin import (create_admin_user_request_body,
                                                           create_admin_phone_number_request_body,
                                                           create_admin_phone_number_from_user_request_body,
                                                           create_scheduled_call_request_body,
                                                           update_admin_phone_number_request_body,
                                                           update_scheduled_call_request_body,
                                                           login_request_body,
                                                           update_admin_user_request_body,
                                                           create_scheduled_call_by_workflow_name_request_body)
from ivr_gateway.api.endpoints.schemas.output.admin import (admin_user_schema,
                                                            admin_phone_number_schema,
                                                            admin_call_schema,
                                                            scheduled_call_schema, admin_api_credential_schema,
                                                            token_response_schema)
from ivr_gateway.api.v1.resources import APIV1AdminResource
from ivr_gateway.api.exceptions import (InvalidAPIAuthenticationException,
                                        MissingAdminUserException,
                                        MissingAdminPhoneException,
                                        MissingAdminCallException,
                                        MissingWorkflowException)
from ivr_gateway.db import session_scope
from ivr_gateway.models.admin import AdminUser
from ivr_gateway.models.enums import AdminRole
from ivr_gateway.services.auth import AuthService
from ivr_gateway.services.workflows import MissingWorkflowConfigException

ns = Namespace(name="admin", description="Admin API")

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


@ns.route('/login')
@ns.doc("Login")
class LoginResource(APIV1AdminResource):
    @ns.response(200, 'Success', admin_user_schema)
    @ns.marshal_with(token_response_schema)
    @ns.expect(login_request_body)
    def post(self):
        json_result = request.json
        user = self.admin_service.get_user_by_credential(**json_result)
        if user is None:
            raise InvalidAPIAuthenticationException("Invalid Credentials")
        return {"token": AuthService.get_token(user)}


@ns.route('/users')
@ns.doc("Get and Create Admin Users")
class AdminUsersResource(APIV1AdminResource):
    @auth.login_required(role=AUTHORIZED_ROLES)
    @ns.response(200, 'Success', admin_user_schema)
    @ns.marshal_with(admin_user_schema)
    @ns.expect(create_admin_user_request_body)
    def post(self):
        json_result = request.json
        result = self.admin_service.create_admin_user(**json_result)
        return result

    @auth.login_required(role=AUTHORIZED_ROLES)
    @ns.response(200, 'Success', admin_user_schema)
    @ns.marshal_with(admin_user_schema)
    def get(self):
        return self.admin_service.get_all_admin_users()


@ns.route('/users/<uuid:user_id>')
@ns.doc("Get, Update and Delete Admins by UserId")
class AdminUserResource(APIV1AdminResource):

    @auth.login_required(role=AUTHORIZED_ROLES)
    @ns.response(200, 'Success', admin_user_schema)
    @ns.marshal_with(admin_user_schema)
    def get(self, user_id: UUID):
        result = self.admin_service.find_admin_user(user_id)

        if result is None:
            raise MissingAdminUserException("Resource not found.")

        return result

    @auth.login_required(role=AUTHORIZED_ROLES)
    @ns.response(200, 'Success', admin_user_schema)
    @ns.marshal_with(admin_user_schema)
    @ns.expect(update_admin_user_request_body)
    def put(self, user_id: UUID):
        json_result = request.json
        result = self.admin_service.update_admin_user(user_id=user_id, **json_result)

        if result is None:
            raise MissingAdminUserException("Resource not found.")

        return result

    @auth.login_required(role=AUTHORIZED_ROLES)
    @ns.response(200, 'Success', admin_user_schema)
    @ns.marshal_with(admin_user_schema)
    def delete(self, user_id: UUID):
        result = self.admin_service.delete_admin_user(user_id)

        if result is None:
            raise MissingAdminUserException("Resource not found.")

        return result


@ns.route('/users/<uuid:user_id>/phone_numbers')
@ns.doc("Create and Retrieve Admin Phone Numbers by User ID")
class AdminUserPhoneNumberResource(APIV1AdminResource):
    @auth.login_required(role=AUTHORIZED_ROLES)
    @ns.response(200, 'Success', admin_phone_number_schema)
    @ns.marshal_with(admin_phone_number_schema)
    def get(self, user_id: UUID):
        results = self.admin_service.get_all_phone_numbers_by_user_id(user_id)
        return results

    @auth.login_required(role=AUTHORIZED_ROLES)
    @ns.response(200, 'Success', admin_phone_number_schema)
    @ns.marshal_with(admin_phone_number_schema)
    @ns.expect(create_admin_phone_number_from_user_request_body)
    def post(self, user_id: UUID):
        json_result = request.json
        result = self.admin_service.create_admin_phone_number_with_user_id(user_id=user_id, **json_result)
        return result


@ns.route('/users/<uuid:user_id>/api_credentials')
@ns.doc("Create Admin Api Credentials by User ID")
class AdminUserApiCredentialResource(APIV1AdminResource):
    @auth.login_required(role=AUTHORIZED_ROLES)
    @ns.response(200, 'Success', admin_api_credential_schema)
    @ns.marshal_with(admin_api_credential_schema)
    def post(self, user_id: UUID):
        return self.admin_service.create_api_credential_for_admin_user(user_id)


@ns.route('/phone_numbers')
@ns.doc("Create and Retrieve Admin Phone Numbers")
class AdminPhoneNumbersResource(APIV1AdminResource):
    @auth.login_required(role=AUTHORIZED_ROLES)
    @ns.response(200, 'Success', admin_phone_number_schema)
    @ns.marshal_with(admin_phone_number_schema)
    def get(self):
        results = self.admin_service.get_all_phone_numbers()
        return results

    @auth.login_required(role=AUTHORIZED_ROLES)
    @ns.response(200, 'Success', admin_phone_number_schema)
    @ns.marshal_with(admin_phone_number_schema)
    @ns.expect(create_admin_phone_number_request_body)
    def post(self):
        json_result = request.json
        result = self.admin_service.create_admin_phone_number_with_user_id(**json_result)

        return result


@ns.route('/phone_numbers/<uuid:phone_number_id>')
@ns.doc("Get, Update and Delete Admin Phone Numbers")
class AdminPhoneNumberResource(APIV1AdminResource):

    @auth.login_required(role=AUTHORIZED_ROLES)
    @ns.response(200, 'Success', admin_phone_number_schema)
    @ns.marshal_with(admin_phone_number_schema)
    def get(self, phone_number_id: UUID):
        result = self.admin_service.find_admin_phone_number_by_id(phone_number_id)

        if result is None:
            raise MissingAdminPhoneException("Resource not found.")

        return result

    @auth.login_required(role=AUTHORIZED_ROLES)
    @ns.response(200, 'Success', admin_phone_number_schema)
    @ns.marshal_with(admin_phone_number_schema)
    @ns.expect(update_admin_phone_number_request_body)
    def put(self, phone_number_id: UUID):
        json_result = request.json
        result = self.admin_service.update_admin_phone_number(phone_number_id=phone_number_id, upsert=False, **json_result)

        if result is None:
            raise MissingAdminPhoneException("Resource not found.")

        return result

    @auth.login_required(role=AUTHORIZED_ROLES)
    @ns.response(200, 'Success', admin_phone_number_schema)
    @ns.marshal_with(admin_phone_number_schema)
    def delete(self, phone_number_id: UUID):
        result = self.admin_service.delete_admin_phone_number(phone_number_id)

        if result is None:
            raise MissingAdminPhoneException("Resource not found.")

        return result


@ns.route('/admin_calls/<uuid:call_id>')
@ns.doc("Get Admin Call by ID")
class AdminCallResource(APIV1AdminResource):
    @auth.login_required(role=AUTHORIZED_ROLES)
    @ns.response(200, 'Success', admin_call_schema)
    @ns.marshal_with(admin_call_schema)
    def get(self, call_id: UUID):
        result = self.admin_service.find_admin_call_by_id(call_id)

        if result is None:
            raise MissingAdminCallException("Resource not found.")

        return result


@ns.route('/admin_calls')
@ns.doc("Get all Admin Calls")
class AdminCallsResource(APIV1AdminResource):
    @auth.login_required(role=AUTHORIZED_ROLES)
    @ns.response(200, 'Success', admin_call_schema)
    @ns.marshal_with(admin_call_schema)
    def get(self):
        results = self.admin_service.get_all_calls()

        return results


@ns.route('/admin_calls/<uuid:call_id>/scheduled_call')
@ns.doc("Create Scheduled Call from Admin Call")
class CreateScheduledCallFromAdminCall(APIV1AdminResource):
    @auth.login_required(role=AUTHORIZED_ROLES)
    @ns.response(200, 'Success', scheduled_call_schema)
    @ns.marshal_with(scheduled_call_schema)
    def post(self, call_id: UUID):
        result = self.admin_service.copy_scheduled_call_from_admin_by_id(call_id)
        if result is None:
            raise MissingAdminCallException("Resource not found.")

        return result


@ns.route('/scheduled_calls')
@ns.doc("Create and Retrieve Scheduled Calls")
class ScheduledCallsResource(APIV1AdminResource):
    @auth.login_required(role=AUTHORIZED_ROLES)
    @ns.response(200, 'Success', scheduled_call_schema)
    @ns.marshal_with(scheduled_call_schema)
    def get(self):
        result = self.admin_service.get_all_scheduled_calls()

        return result

    @auth.login_required(role=AUTHORIZED_ROLES)
    @ns.response(200, 'Success', scheduled_call_schema)
    @ns.marshal_with(scheduled_call_schema)
    @ns.expect(create_scheduled_call_request_body)
    def post(self):
        json_result = request.json
        json_result["user_id"] = UUID(json_result["user_id"])
        result = self.admin_service.create_scheduled_call(**json_result)

        return result


@ns.route('/scheduled_calls/<uuid:call_id>')
@ns.doc("Retrieve and Update Scheduled Call by ID")
class ScheduledCallResource(APIV1AdminResource):
    @auth.login_required(role=AUTHORIZED_ROLES)
    @ns.response(200, 'Success', scheduled_call_schema)
    @ns.marshal_with(scheduled_call_schema)
    def get(self, call_id: UUID):
        result = self.admin_service.find_scheduled_call_by_id(call_id)

        if result is None:
            raise MissingAdminCallException("Resource not found.")

        return result

    @auth.login_required(role=AUTHORIZED_ROLES)
    @ns.response(200, 'Success', scheduled_call_schema)
    @ns.marshal_with(scheduled_call_schema)
    @ns.expect(update_scheduled_call_request_body)
    def put(self, call_id: UUID):
        json_result = request.json
        result = self.admin_service.update_scheduled_call(scheduled_call_id=call_id, **json_result)

        if result is None:
            raise MissingAdminCallException("Resource not found.")

        return result

    @ns.route('/workflows/scheduled_call')
    @ns.doc("Create scheduled call by workflow name and version")
    class ScheduledCallWorkflowResource(APIV1AdminResource):

        @auth.login_required(role=AUTHORIZED_ROLES)
        @ns.response(200, 'Success', scheduled_call_schema)
        @ns.marshal_with(scheduled_call_schema)
        @ns.expect(create_scheduled_call_by_workflow_name_request_body)
        def post(self):
            json_result = request.json
            workflow_name = json_result.get("workflow_name")
            workflow = self.workflow_service.get_workflow_by_name(workflow_name)

            if workflow is None:
                raise MissingWorkflowException(f"Workflow with name {workflow_name} not found.")

            workflow_version_tag = json_result.get("workflow_version_tag")
            if workflow_version_tag:
                try:
                    self.workflow_service.update_active_workflow_config(workflow, workflow_version_tag)
                except MissingWorkflowConfigException:
                    raise MissingWorkflowException(f"Workflow version tag {workflow_version_tag} not found.")

            result = self.admin_service.create_scheduled_call_from_workflow(workflow, **json_result)

            return result
