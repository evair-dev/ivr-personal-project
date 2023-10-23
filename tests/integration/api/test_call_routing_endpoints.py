from typing import Dict
from uuid import uuid4

import pytest
from sqlalchemy import orm
from sqlalchemy.orm import Session as SQLAlchemySession

from ivr_gateway.models.admin import AdminUser, ApiCredential
from ivr_gateway.models.contacts import InboundRouting, Greeting
from ivr_gateway.models.queues import Queue
from ivr_gateway.models.workflows import Workflow
from ivr_gateway.services.admin import AdminService


from ivr_gateway.services.auth import AuthService
from tests.factories import queues as qf

from tests.factories import workflow as wcf
from tests.fixtures.step_trees.loan_origination import loan_origination_step_tree


class TestAdmin:

    @pytest.fixture
    def workflow(self, db_session: SQLAlchemySession) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "loan_origination", step_tree=loan_origination_step_tree)
        return workflow_factory.create()

    @pytest.fixture
    def greeting(self, db_session) -> Greeting:
        greeting = Greeting(message='hello from <phoneme alphabet="ipa" ph="əˈvɑnt">Iivr</phoneme>.')
        db_session.add(greeting)
        db_session.commit()
        return greeting

    @pytest.fixture
    def queue(self, db_session) -> Queue:
        queue = qf.queue_factory(db_session).create(
            name="test")
        return queue

    @pytest.fixture
    def call_routing(self, db_session, workflow: Workflow, greeting: Greeting, queue) -> InboundRouting:
        call_routing = InboundRouting(
            inbound_target="15555555556",
            workflow=workflow,
            active=True,
            greeting=greeting,
            operating_mode="normal",
            priority=0,
            initial_queue=queue
        )
        db_session.add(call_routing)
        db_session.commit()
        return call_routing

    @pytest.fixture
    def admin_call_routing(self, db_session, greeting: Greeting) -> InboundRouting:
        admin_call_routing = InboundRouting(
            inbound_target="15555555555",
            workflow=None,
            admin=True,
            active=True,
            greeting=greeting,
            operating_mode="normal",
            priority=100
        )
        db_session.add(admin_call_routing)
        db_session.commit()
        return admin_call_routing

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

    def test_get_call_routings(self, db_session, test_client, api_credential: ApiCredential, auth_header, call_routing,
                               admin_call_routing):
        response = test_client.get("api/v1/call_routing", headers=auth_header)
        no_admin_json = response.json
        assert response.status_code == 200
        assert len(no_admin_json) == 1
        assert no_admin_json[0] == {'id': str(call_routing.id),
                                    'inbound_target': '15555555556',
                                    'workflow_id': str(call_routing.workflow_id),
                                    'workflow_name': 'loan_origination',
                                    'initial_queue_id': str(call_routing.initial_queue_id),
                                    'initial_queue_name': 'test', 'greeting_id': str(call_routing.greeting_id),
                                    'priority': 0, 'admin': False, 'active': True, 'operating_mode': 'normal',
                                    'created_at': call_routing.created_at.isoformat(),
                                    'updated_at': call_routing.updated_at.isoformat()}
        admin_response = test_client.get("api/v1/call_routing?include_admin=true", headers=auth_header)
        assert admin_response.status_code == 200
        assert len(admin_response.json) == 2

    def test_get_call_routing_for_number(self, db_session, test_client, api_credential: ApiCredential, auth_header, call_routing,
                               admin_call_routing):
        response = test_client.get("api/v1/call_routing?phone_number=15555555556", headers=auth_header)
        json = response.json
        assert response.status_code == 200
        assert len(json) == 1
        assert json[0] == {'id': str(call_routing.id),
                                    'inbound_target': '15555555556',
                                    'workflow_id': str(call_routing.workflow_id),
                                    'workflow_name': 'loan_origination',
                                    'initial_queue_id': str(call_routing.initial_queue_id),
                                    'initial_queue_name': 'test', 'greeting_id': str(call_routing.greeting_id),
                                    'priority': 0, 'admin': False, 'active': True, 'operating_mode': 'normal',
                                    'created_at': call_routing.created_at.isoformat(),
                                    'updated_at': call_routing.updated_at.isoformat()}

    def test_get_call_routing(self, test_client, api_credential: ApiCredential, auth_header, call_routing):
        response = test_client.get(f"api/v1/call_routing/{call_routing.id}", headers=auth_header)
        json = response.json
        assert response.status_code == 200
        assert json == {'id': str(call_routing.id),
                        'inbound_target': '15555555556',
                        'workflow_id': str(call_routing.workflow_id),
                        'workflow_name': 'loan_origination',
                        'initial_queue_id': str(call_routing.initial_queue_id),
                        'initial_queue_name': 'test', 'greeting_id': str(call_routing.greeting_id),
                        'priority': 0, 'admin': False, 'active': True, 'operating_mode': 'normal',
                        'created_at': call_routing.created_at.isoformat(),
                        'updated_at': call_routing.updated_at.isoformat()}

    def test_get_invalid_call_routing(self, test_client, api_credential: ApiCredential, auth_header, call_routing):
        not_uuid_response = test_client.get("api/v1/call_routing/abc", headers=auth_header)
        assert not_uuid_response.status_code == 404
        not_correct_uuid = test_client.get(f"api/v1/call_routing/{uuid4()}", headers=auth_header)
        assert not_correct_uuid.status_code == 404

    def test_get_missing_call_routing(self, test_client):
        form = {"CallSid": "test",
                "To": "+15555555557",
                "Digits": "1234"}
        missing_response = test_client.post("/api/v1/twilio/new", data=form)
        assert missing_response.status_code == 404
