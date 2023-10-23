import uuid

import pytest

from ivr_gateway.models.admin import AdminUser, AdminPhoneNumber, AdminCall, ScheduledCall, AdminCallFrom, AdminCallTo
from ivr_gateway.models.contacts import Greeting, InboundRouting
from ivr_gateway.models.workflows import Workflow
from ivr_gateway.services.admin import AdminService

from tests.factories import workflow as wcf
from tests.fixtures.step_trees.loan_origination import loan_origination_step_tree


class TestAdmin:
    @pytest.fixture
    def workflow(self, db_session) -> Workflow:
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
    def admin_service(self, db_session):
        return AdminService(db_session)

    @pytest.fixture
    def admin_user(self, db_session) -> AdminUser:
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
    def admin_phone_number(self, db_session, admin_user) -> AdminPhoneNumber:
        phone_number = AdminPhoneNumber(
            phone_number="11235813213",
            user=admin_user
        )
        db_session.add(phone_number)
        db_session.commit()
        return phone_number

    @pytest.fixture
    def scheduled_call(self, db_session, admin_user: AdminUser) -> ScheduledCall:
        scheduled_call = ScheduledCall()
        scheduled_call.user = admin_user
        scheduled_call.ani = "12345678900"
        scheduled_call.dnis = "15555555556"
        db_session.add(scheduled_call)
        db_session.commit()
        return scheduled_call

    @pytest.fixture
    def dnis_shortcut(self, db_session) -> AdminCallTo:
        dnis = AdminCallTo(
            short_number="10",
            full_number="15555555556"
        )
        db_session.add(dnis)
        db_session.commit()
        return dnis

    @pytest.fixture
    def ani_shortcut(self, db_session) -> AdminCallFrom:
        ani = AdminCallFrom(
            short_number="10",
            full_number="12345678900"
        )
        db_session.add(ani)
        db_session.commit()
        return ani

    @pytest.fixture
    def admin_call(self, db_session, admin_user: AdminUser) -> AdminCall:
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

    @pytest.fixture
    def greeting(self, db_session) -> Greeting:
        greeting = Greeting(message='greeting')
        db_session.add(greeting)
        db_session.commit()
        return greeting

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

    def test_get_all_admin_users(self, db_session, admin_service, admin_user):
        results = admin_service.get_all_admin_users()
        expected_list = [admin_user.id]
        result_list = [admin_user.id for admin_user in results]
        assert expected_list == result_list

    def test_get_all_phone_numbers(self, db_session, admin_service, admin_phone_number, admin_user):
        results = admin_service.get_all_phone_numbers()
        expected_list = [admin_phone_number.id]
        result_list = [phone_number.id for phone_number in results]
        assert expected_list == result_list

    def test_get_all_phone_numbers_by_user_id(self, db_session, admin_service, admin_phone_number, admin_user):
        results = admin_service.get_all_phone_numbers_by_user_id(admin_user.id)
        expected_list = [admin_phone_number.id]
        result_list = [phone_number.id for phone_number in results]
        assert expected_list == result_list

    def test_get_all_calls(self, db_session, admin_service, admin_user, admin_call):
        results = admin_service.get_all_calls()
        expected_list = [admin_call.id]
        result_list = [call.id for call in results]
        assert expected_list == result_list

    def test_get_all_scheduled_calls(self, db_session, admin_service, scheduled_call, admin_user):
        results = admin_service.get_all_scheduled_calls()
        expected_list = [scheduled_call.id]
        result_list = [call.id for call in results]
        assert expected_list == result_list

    def test_find_admin_phone_number_by_id(self, db_session, admin_service, admin_phone_number, admin_user):
        result = admin_service.find_admin_phone_number_by_id(admin_phone_number.id)
        assert result.id == admin_phone_number.id

    def test_find_admin_phone_number(self, db_session, admin_service, admin_phone_number, admin_user):
        result = admin_service.find_admin_phone_number(admin_phone_number.phone_number)
        assert result.id == admin_phone_number.id

    def test_find_admin_user_by_phone_number(self, db_session, admin_service, admin_phone_number, admin_user):
        result = admin_service.find_admin_user_by_phone_number(admin_phone_number.phone_number)
        assert result.id == admin_user.id

    def test_find_admin_user_by_short_id(self, db_session, admin_service, admin_user):
        result = admin_service.find_admin_user_by_short_id(admin_user.short_id)
        assert result.id == admin_user.id

    def test_find_admin_user(self, db_session, admin_service, admin_user):
        result = admin_service.find_admin_user(admin_user.id)
        assert result.id == admin_user.id

    def test_find_admin_call(self, db_session, admin_service, admin_call):
        result = admin_service.find_admin_call(admin_call.contact_system, admin_call.contact_system_id)
        assert result.id == admin_call.id

    def test_find_admin_call_by_id(self, db_session, admin_service, admin_call):
        result = admin_service.find_admin_call_by_id(admin_call.id)
        assert result.id == admin_call.id

    def test_find_scheduled_call_by_id(self, db_session, admin_service, scheduled_call):
        result = admin_service.find_scheduled_call_by_id(scheduled_call.id)
        assert result.id == scheduled_call.id

    def test_find_scheduled_call(self, db_session, admin_service, scheduled_call, admin_user):
        result = admin_service.find_scheduled_call(admin_user)
        assert result.id == scheduled_call.id

    def test_create_admin_user(self, db_session, admin_service):
        result = admin_service.create_admin_user("Justin", "12345", "123", "admin")
        assert result.name == "Justin"
        assert result.short_id == "12345"
        assert result.pin == "123"

    def test_update_admin_user(self, db_session, admin_service, admin_user):
        result = admin_service.update_admin_user(admin_user.id, name="Jay")
        assert result.name == "Jay"

    def test_delete_admin_user(self, db_session, admin_service, admin_user):
        admin_service.delete_admin_user(admin_user.id)
        assert not admin_service.find_admin_user(admin_user.id)

    def test_create_admin_phone_number_with_user_id(self, db_session, admin_service, admin_user):
        result = admin_service.create_admin_phone_number_with_user_id(
            admin_user.id,
            "Test Number",
            "14438342310"
        )

        assert result.user.id == admin_user.id
        assert result.name == "Test Number"
        assert result.phone_number == "14438342310"

    def test_create_admin_phone_number(self, db_session, admin_service, admin_user):
        result = admin_service.create_admin_phone_number(
            admin_user.short_id,
            "Test Number",
            "14438342310"
        )

        assert result.user.id == admin_user.id
        assert result.name == "Test Number"
        assert result.phone_number == "14438342310"

    def test_update_admin_phone_number(self, db_session, admin_service, admin_phone_number):
        result = admin_service.update_admin_phone_number(admin_phone_number.id, name="Blah")
        assert result.name == "Blah"

    def test_delete_admin_phone_number(self, db_session, admin_service, admin_phone_number):
        admin_service.delete_admin_phone_number(admin_phone_number.id)
        assert not admin_service.find_admin_phone_number_by_id(admin_phone_number.id)

    def test_create_admin_call(self, db_session, admin_service, admin_user):
        result = admin_service.create_admin_call("test system", "test_system_id", admin_user, "4438342310",
                                                 "14445556666")
        assert result.user.id == admin_user.id
        assert result.contact_system == "test system"
        assert result.contact_system_id == "test_system_id"

    def test_create_scheduled_call(self, db_session, admin_service, admin_user, admin_call_routing, admin_call):
        result = admin_service.create_scheduled_call(
            admin_user.id,
            "4445556666",
            "4344443333",
            admin_call_routing.id
        )

        assert result.user.id == admin_user.id
        assert result.ani == "4445556666"
        assert result.dnis == "4344443333"
        assert result.inbound_routing.id == admin_call_routing.id

    def test_update_scheduled_call(self, db_session, admin_service, scheduled_call):
        result = admin_service.update_scheduled_call(scheduled_call.id, ani="14438342310")
        assert result.ani == "14438342310"

    def test_verify_admin_call(self, db_session, admin_service, admin_call, admin_user):
        assert admin_service.verify_admin_call(admin_call, "5678")
        assert not admin_service.verify_admin_call(admin_call, "1234")
        assert not admin_service.verify_admin_call(None, "5678")

    def test_add_ani(self, db_session, admin_service, admin_call):
        result = admin_service.add_ani(admin_call, ani="15556667777")
        assert result.ani == "15556667777"

    def test_add_dnis(self, db_session, admin_service, admin_call):
        result = admin_service.add_dnis(admin_call, dnis="7778889999")
        assert result.dnis == "7778889999"

    def test_find_shortcut_ani(self, db_session, admin_service, ani_shortcut):
        result = admin_service.find_shortcut_ani(ani_shortcut.short_number)
        assert result.short_number == ani_shortcut.short_number

    def test_find_shortcut_dnis(self, db_session, admin_service, dnis_shortcut):
        result = admin_service.find_shortcut_dnis(dnis_shortcut.short_number)
        assert result.short_number == dnis_shortcut.short_number

    def test_create_scheduled_call_from_workflow(self, db_session, admin_service, workflow, admin_user, ):
        result = admin_service.create_scheduled_call_from_workflow(
            workflow,
            user_id=admin_user.id,
        )

        assert result.user.id == admin_user.id
        assert result.workflow_id == workflow.id
