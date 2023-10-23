from typing import Dict

import pytest
from sqlalchemy import orm
from sqlalchemy.orm import Session as SQLAlchemySession

from ivr_gateway.exit_paths import HangUpExitPath
from ivr_gateway.models.admin import AdminUser, AdminPhoneNumber, AdminCall, ApiCredential, ScheduledCall
from ivr_gateway.models.contacts import InboundRouting, Greeting
from ivr_gateway.models.workflows import Workflow, WorkflowConfig
from ivr_gateway.services.admin import AdminService

import uuid

from ivr_gateway.services.auth import AuthService
from ivr_gateway.steps.api.v1 import PlayMessageStep
from ivr_gateway.steps.config import StepTree, StepBranch, Step

from tests.factories import workflow as wcf
from tests.fixtures.step_trees.loan_origination import loan_origination_step_tree


class TestAdmin:

    @pytest.fixture
    def greeting(self, db_session) -> Greeting:
        greeting = Greeting(message='greeting')
        db_session.add(greeting)
        db_session.commit()
        return greeting

    @pytest.fixture
    def modified_step_tree(self) -> StepTree:
        return StepTree(
            branches=[
                StepBranch(
                    name="root",
                    steps=[
                        Step(
                            name="step-1",
                            step_type=PlayMessageStep.get_type_string(),
                            step_kwargs={
                                "template": "Hello"
                            },
                            exit_path={
                                "exit_path_type": HangUpExitPath.get_type_string(),
                                "exit_path_kwargs": {}
                            }
                        )

                    ]
                )
            ])


    @pytest.fixture
    def workflow(self, db_session: SQLAlchemySession) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "loan_origination", step_tree=loan_origination_step_tree)
        workflow = workflow_factory.create()
        initial_step_tree_workflow_config = workflow.latest_config
        initial_step_tree_workflow_config.tag = "1.0.0"
        workflow.active_config_tag = "1.0.0"
        db_session.add(workflow)
        db_session.add(initial_step_tree_workflow_config)
        db_session.commit()
        return workflow


    @pytest.fixture
    def modified_workflow(self, db_session: SQLAlchemySession, workflow, modified_step_tree):
        new_workflow_config = WorkflowConfig(workflow=workflow, step_tree=modified_step_tree)
        db_session.add(new_workflow_config)
        db_session.commit()

        workflow.active_config_tag  = "latest"
        db_session.add(workflow)
        db_session.commit()
        return workflow


    @pytest.fixture
    def admin_call_routing(self, db_session, greeting: Greeting) -> InboundRouting:
        call_routing = InboundRouting(
            inbound_target="15555555555",
            workflow=None,
            admin=True,
            active=True,
            greeting=greeting,
            operating_mode="normal",
            priority=100
        )
        db_session.add(call_routing)
        db_session.commit()
        return call_routing

    @pytest.fixture
    def admin_user(self, db_session: SQLAlchemySession) -> AdminUser:
        admin_user = AdminUser(
            name="Mister Admin",
            short_id="1234",
            pin="5678",
            role="user"
        )
        db_session.add(admin_user)
        db_session.commit()
        return admin_user

    @pytest.fixture
    def api_credential(self, db_session: orm.Session, admin_user: AdminUser) -> ApiCredential:
        admin_service = AdminService(db_session)
        cred = admin_service.create_api_credential_for_admin_user(admin_user.id)
        return cred

    @pytest.fixture
    def auth_token(self, admin_user: AdminUser) -> str:
        return AuthService.get_token(admin_user)

    @pytest.fixture
    def auth_header(self, auth_token) -> Dict:
        return {"Authorization": f"Bearer {auth_token}"}

    @pytest.fixture
    def admin_phone_number(self, db_session: SQLAlchemySession, admin_user: AdminUser) -> AdminPhoneNumber:
        admin_phone_number = AdminPhoneNumber(
            user_id=admin_user.id,
            phone_number="4108339999",
            name="Some Weird Phone Number"
        )

        db_session.add(admin_phone_number)
        db_session.commit()
        return admin_phone_number

    @pytest.fixture
    def admin_call(self, db_session: SQLAlchemySession, admin_user: AdminUser) -> AdminCall:
        admin_call = AdminCall(
            contact_system="Some System",
            contact_system_id=str(uuid.uuid1()),
            user_id=admin_user.id,
            ani="some_ani",
            dnis="some_dnis",
            verified=True,
            original_ani="original_ani",
            original_dnis="original_dnis"
        )

        db_session.add(admin_call)
        db_session.commit()
        return admin_call

    def test_create_new_admin_user(self, test_client, api_credential: ApiCredential, auth_header):
        body = {
            "name": "My Name",
            "short_id": "1234",
            "pin": "1234",
            "role": "user"
        }
        response = test_client.post("api/v1/admin/users", json=body, headers=auth_header)
        assert response.status_code == 200
        del body["pin"]
        assert body.items() <= response.json.items()
        body = {
            "name": "My Admin Name",
            "short_id": "9876",
            "pin": "1234",
            "role": "admin"
        }
        response = test_client.post("api/v1/admin/users", json=body, headers=auth_header)
        assert response.status_code == 200
        del body["pin"]
        assert body.items() <= response.json.items()

    def test_get_user_if_user_unknown(self, test_client, api_credential: ApiCredential, auth_header):
        nonexistent_uuid_str = str(uuid.uuid1())
        response = test_client.get(f"api/v1/admin/users/{nonexistent_uuid_str}", headers=auth_header)
        assert response.status_code == 404
        assert response.json == {'message': 'Resource not found.'}

    def test_get_admin_user(self, test_client, admin_user, api_credential: ApiCredential, auth_header):
        admin_user_id = admin_user.id
        response = test_client.get(f"api/v1/admin/users/{admin_user_id}", headers=auth_header)
        assert response.status_code == 200

        expected_result = {
            "name": "Mister Admin",
            "short_id": "1234",
            "role": "user"
        }

        assert expected_result.items() <= response.json.items()

    def test_update_admin_user(self, test_client, db_session, admin_user, api_credential: ApiCredential, auth_header):
        name = "Mrs Admin"
        admin_user_id = admin_user.id
        update_json = {
            "name": name
        }
        response = test_client.put(f"api/v1/admin/users/{admin_user_id}", json=update_json, headers=auth_header)
        assert response.status_code == 200
        assert update_json.items() <= response.json.items()
        assert response.json["name"] == name
        assert db_session.query(AdminUser).filter(AdminUser.id == admin_user_id, AdminUser.name == name).one_or_none()

    def test_update_admin_user_not_found(self, test_client, api_credential: ApiCredential, auth_header):
        nonexistent_id = str(uuid.uuid1())
        update_json = {
            "name": "Name"
        }

        response = test_client.put(f"api/v1/admin/users/{nonexistent_id}", json=update_json, headers=auth_header)
        assert response.status_code == 404

    def test_update_admin_user_incorrect_data(self, test_client, admin_user, api_credential: ApiCredential,
                                              auth_header):
        admin_user_id = admin_user.id
        update_json = {
            "name": 1
        }
        response = test_client.put(f"api/v1/admin/users/{admin_user_id}", json=update_json, headers=auth_header)
        assert response.status_code == 400

    def test_delete_admin_user(self, test_client, db_session, admin_user, api_credential: ApiCredential, auth_header):
        admin_user_id = admin_user.id
        response = test_client.delete(f"api/v1/admin/users/{admin_user_id}", headers=auth_header)
        assert response.status_code == 200

        found_user = db_session.query(AdminUser).filter(AdminUser.id == admin_user_id).first()
        assert found_user is None

    def test_get_admin_phone_number(self, test_client, admin_phone_number, admin_user, api_credential: ApiCredential,
                                    auth_header):
        admin_phone_number_id = admin_phone_number.id
        response = test_client.get(f"api/v1/admin/phone_numbers/{admin_phone_number_id}", headers=auth_header)
        assert response.status_code == 200
        expected_result = {
            "user_id": str(admin_user.id),
            "phone_number": "4108339999",
            "name": "Some Weird Phone Number"
        }

        assert expected_result.items() <= response.json.items()


    def test_get_admin_phone_number_not_found(self, test_client, api_credential: ApiCredential, auth_header):
        nonexistent_id = str(uuid.uuid1())
        response = test_client.get(f"api/v1/admin/phone_numbers/{nonexistent_id}", headers=auth_header)
        assert response.status_code == 404

    def test_get_all_phone_numbers_from_user(self, test_client, admin_user, admin_phone_number,
                                             api_credential: ApiCredential, auth_header):
        id = admin_user.id
        response = test_client.get(f"api/v1/admin/users/{id}/phone_numbers", headers=auth_header)
        assert response.status_code == 200
        assert response.json[0]['id'] == str(admin_phone_number.id)
        assert response.json[0]['user_id'] == str(admin_user.id)

    def test_create_admin_phone_number_from_user(self, test_client, admin_user, api_credential: ApiCredential,
                                                 auth_header):
        create_json = {
            "phone_number": "18006676677",
            "name": "A number of sorts"
        }
        response = test_client.post(f"api/v1/admin/users/{admin_user.id}/phone_numbers", json=create_json,
                                    headers=auth_header)
        assert response.status_code == 200

    def test_create_admin_phone_number_from_user_invalid_phone_number(self, test_client, admin_user, api_credential: ApiCredential,
                                                 auth_header):
        create_json = {
            "phone_number": "006676677",
            "name": "A number of sorts"
        }
        response = test_client.post(f"api/v1/admin/users/{admin_user.id}/phone_numbers", json=create_json,
                                    headers=auth_header)
        assert response.status_code == 400

    def test_create_admin_phone_number(self, test_client, admin_user, api_credential: ApiCredential, auth_header):
        create_json = {
            "user_id": str(admin_user.id),
            "phone_number": "18006676677",
            "name": "A number of sorts"
        }

        response = test_client.post("api/v1/admin/phone_numbers", json=create_json, headers=auth_header)
        assert response.status_code == 200
        assert create_json.items() <= response.json.items()

    def test_create_admin_phone_number_invalid_uuid(self, test_client, admin_user, api_credential: ApiCredential, auth_header):
        create_json = {
            "user_id": "12978612981",
            "phone_number": "18006676677",
            "name": "A number of sorts"
        }

        response = test_client.post("api/v1/admin/phone_numbers", json=create_json, headers=auth_header)
        assert response.status_code == 400

    def test_create_admin_phone_number_already_exists(self, test_client, admin_phone_number, admin_user,api_credential: ApiCredential, auth_header):
        create_json = {
            "user_id": str(admin_user.id),
            "phone_number": admin_phone_number.phone_number,
            "name": "Duplicate Number"
        }

        response = test_client.post("api/v1/admin/phone_numbers", json=create_json, headers=auth_header)
        assert response.status_code == 400

    def test_get_all_phone_numbers(self, test_client, admin_user, admin_phone_number, api_credential: ApiCredential,
                                   auth_header):
        response = test_client.get("api/v1/admin/phone_numbers", headers=auth_header)
        assert response.status_code == 200

    def test_update_phone_number(self, test_client, db_session, admin_phone_number, api_credential: ApiCredential,
                                 auth_header):
        admin_phone_number_id = admin_phone_number.id
        changed_phone_number = "18477845555"
        update_json = {
            "phone_number": changed_phone_number
        }
        response = test_client.put(f"api/v1/admin/phone_numbers/{admin_phone_number_id}", json=update_json,
                                   headers=auth_header)

        assert response.status_code == 200
        assert response.json["phone_number"] == changed_phone_number
        assert (db_session.query(AdminPhoneNumber)
                .filter(AdminPhoneNumber.id == admin_phone_number_id)
                .filter(AdminPhoneNumber.phone_number == changed_phone_number)
                .one_or_none())

    def test_update_phone_number_not_found(self, test_client, api_credential: ApiCredential, auth_header):
        nonexistent_id = str(uuid.uuid1())
        changed_phone_number = "18477845555"
        update_json = {
            "phone_number": changed_phone_number
        }

        response = test_client.put(f"api/v1/admin/phone_numbers/{nonexistent_id}", json=update_json,
                                   headers=auth_header)
        assert response.status_code == 404

    def test_update_phone_number_improper_input(self, test_client, admin_phone_number, api_credential: ApiCredential,
                                                auth_header):
        admin_phone_number_id = admin_phone_number.id
        update_json = {
            "phone_number": 8484
        }
        response = test_client.put(f"api/v1/admin/phone_numbers/{admin_phone_number_id}", json=update_json,
                                   headers=auth_header)
        assert response.status_code == 400

    def test_delete_phone_number(self, test_client, admin_phone_number, db_session, api_credential: ApiCredential,
                                 auth_header):
        admin_phone_number_id = admin_phone_number.id
        response = test_client.delete(f"api/v1/admin/phone_numbers/{admin_phone_number_id}", headers=auth_header)
        assert response.status_code == 200
        found_user = db_session.query(AdminPhoneNumber).filter(AdminPhoneNumber.id == admin_phone_number_id).first()

        assert found_user is None

    def test_delete_phone_number_not_found(self, test_client, api_credential: ApiCredential, auth_header):
        id = str(uuid.uuid1())
        response = test_client.delete(f"api/v1/admin/phone_numbers/{id}", headers=auth_header)
        assert response.status_code == 404

    def test_get_admin_call(self, test_client, admin_call, api_credential: ApiCredential, auth_header):
        admin_call_id = admin_call.id
        response = test_client.get(f"api/v1/admin/admin_calls/{admin_call_id}", headers=auth_header)
        assert response.status_code == 200
        assert response.json["id"] == str(admin_call_id)

    def test_get_admin_call_not_found(self, test_client, api_credential: ApiCredential, auth_header):
        nonexistent_uuid = str(uuid.uuid1())
        response = test_client.get(f"api/v1/admin/admin_calls/{nonexistent_uuid}", headers=auth_header)
        assert response.status_code == 404

    def test_get_all_admin_calls(self, test_client, admin_call, api_credential: ApiCredential, auth_header):
        admin_call_id = admin_call.id
        response = test_client.get("api/v1/admin/admin_calls", headers=auth_header)
        assert response.status_code == 200
        assert response.json[0]["id"] == str(admin_call_id)

    def test_copy_scheduled_call_from_admin(self, test_client, db_session, admin_call, api_credential: ApiCredential,
                                            auth_header):
        admin_call_id = admin_call.id
        response = test_client.post(f"api/v1/admin/admin_calls/{admin_call_id}/scheduled_call", headers=auth_header)
        assert response.status_code == 200
        assert db_session.query(ScheduledCall).filter(ScheduledCall.admin_call_id == admin_call_id) \
            .filter(ScheduledCall.id == response.json["id"]) \
            .one_or_none()

    def test_create_scheduled_call(self, test_client, admin_call, admin_user, admin_call_routing,
                                   api_credential: ApiCredential, auth_header):
        request_json = {
            "user_id": str(admin_user.id),
            "dnis": "18776665555",
            "ani": "14439992323",
            "call_routing_id": admin_call_routing.id
        }

        response = test_client.post("api/v1/admin/scheduled_calls", json=request_json, headers=auth_header)
        assert response.status_code == 200

    def test_login(self, test_client, db_session, admin_user, api_credential: ApiCredential, auth_header):
        request_json = {
            "api_key": api_credential.key,
            "api_secret": api_credential.secret
        }

        response = test_client.post("api/v1/admin/login", json=request_json)
        assert response.status_code == 200
        token = response.json.get("token")
        auth_service = AuthService(db_session)
        user = auth_service.get_user_from_token(token)
        assert user.id == admin_user.id

    def test_bad_login(self, test_client, db_session, admin_user, api_credential: ApiCredential, auth_header):
        request_json = {
            "api_key": "not a real key",
            "api_secret": "not a real secret"
        }

        response = test_client.post("api/v1/admin/login", json=request_json)
        assert response.status_code == 401

    def test_create_scheduled_call_from_workflow_name(self, test_client, db_session, admin_call, admin_user,
                                                      admin_call_routing, api_credential: ApiCredential, auth_header, workflow):
        request_json = {
            "user_id": str(admin_user.id),
            "workflow_name": workflow.workflow_name
        }

        response = test_client.post("api/v1/admin/workflows/scheduled_call", json=request_json, headers=auth_header)

        assert response.status_code == 200
        assert response.json["workflow_id"] == str(workflow.id)

    def test_create_scheduled_call_from_workflow_name_with_version(self, test_client, db_session, admin_call, admin_user,
                                                      admin_call_routing, api_credential: ApiCredential, auth_header, modified_workflow):
        request_json = {
            "user_id": str(admin_user.id),
            "workflow_name": modified_workflow.workflow_name,
            "workflow_version_tag": "1.0.0"
        }
        response = test_client.post("api/v1/admin/workflows/scheduled_call", json=request_json, headers=auth_header)

        assert response.status_code == 200
        assert response.json["workflow_id"] == str(modified_workflow.id)
        assert response.json["workflow_version_tag"] == str("1.0.0")

    def test_create_scheduled_call_from_workflow_name_no_workflow(self, test_client, db_session, admin_call, admin_user,
                                                      admin_call_routing, api_credential: ApiCredential, auth_header):

        request_json = {
            "user_id": str(admin_user.id),
            "workflow_name": "fake_workflow",
        }


        response = test_client.post("api/v1/admin/workflows/scheduled_call", json=request_json, headers=auth_header)

        assert response.status_code == 404