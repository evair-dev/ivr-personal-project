from typing import Dict

import pytest
from sqlalchemy import orm
from sqlalchemy.orm import Session as SQLAlchemySession

from ivr_gateway.models.admin import AdminUser, ApiCredential
from ivr_gateway.models.contacts import InboundRouting, Greeting
from ivr_gateway.models.enums import Partner
from ivr_gateway.models.queues import Queue
from ivr_gateway.models.workflows import Workflow
from ivr_gateway.services.admin import AdminService

from ivr_gateway.services.auth import AuthService

from tests.factories import workflow as wcf
from tests.factories import queues as qf
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
            name="AFC.LN.PAY.INT")
        return queue

    @pytest.fixture
    def external_queue(self, db_session) -> Queue:
        queue = qf.queue_factory(db_session).create(
            name="AFC.LN.PAY.EXT",
        )
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

    def test_get_queues(self, db_session, test_client, api_credential: ApiCredential, auth_header,
                        queue, external_queue):
        response = test_client.get("api/v1/queue", headers=auth_header)
        assert response.status_code == 200
        assert len(response.json) == 2

    def test_get_queue(self, db_session, test_client, api_credential: ApiCredential, auth_header,
                       queue, external_queue):
        response = test_client.get("api/v1/queue/AFC.LN.PAY.INT", headers=auth_header)
        assert response.status_code == 200
        assert response.json["name"] == "AFC.LN.PAY.INT"
        assert response.json["id"] == str(queue.id)
        assert response.json["partner"] == Partner.IVR.value
        assert len(response.json["hours_of_operation"]) == 7
        assert response.json["hours_of_operation"][0]["start_time"] == "08:00:00"
        assert response.json["hours_of_operation"][0]["end_time"] == "16:00:00"
        assert len(response.json["transfer_routings"]) == 1
        assert response.json["transfer_routings"][0]["transfer_type"] == "PSTN"
        assert response.json["transfer_routings"][0]["destination"] == "12345678901"

    def test_get_invalid_queue(self, db_session, test_client, api_credential: ApiCredential, auth_header,
                       queue, external_queue):
        not_uuid_response = test_client.get("api/v1/queue/abc", headers=auth_header)
        assert not_uuid_response.status_code == 404
