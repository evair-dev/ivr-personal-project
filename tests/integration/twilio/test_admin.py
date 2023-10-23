from typing import Dict
import pytest
from sqlalchemy import orm
from sqlalchemy.orm import Session as SQLAlchemySession, joinedload

from ivr_gateway.exit_paths import HangUpExitPath
from ivr_gateway.models.admin import (AdminUser,
                                      AdminCallTo,
                                      AdminCallFrom,
                                      AdminPhoneNumber,
                                      AdminCall,
                                      ApiCredential,
                                      ScheduledCall)
from ivr_gateway.models.contacts import Greeting, InboundRouting, ContactLeg
from ivr_gateway.models.enums import AdminRole
from ivr_gateway.models.workflows import Workflow
from ivr_gateway.services.auth import AuthService
from ivr_gateway.services.admin import AdminService
from ivr_gateway.steps.api.v1 import PlayMessageStep, InputStep
from ivr_gateway.steps.config import StepTree, StepBranch, Step
from tests.factories import workflow as wcf


class TestTwilioAdmin:

    @pytest.fixture
    def greeting(self, db_session) -> Greeting:
        greeting = Greeting(message='greeting')
        db_session.add(greeting)
        db_session.commit()
        return greeting

    @pytest.fixture
    def admin_call(self, db_session: SQLAlchemySession, admin_user: AdminUser, admin_call_routing: InboundRouting) -> AdminCall:
        admin_call = AdminCall(
            contact_system="test",
            contact_system_id="test",
            user_id=admin_user.id,
            ani="4425556666",
            dnis="4425552222",
            inbound_routing_id=admin_call_routing.id,
            verified=True,
            original_ani="original_ani",
            original_dnis="original_dnis"
        )

        db_session.add(admin_call)
        db_session.commit()
        return admin_call

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
    def simple_workflow(self, db_session: SQLAlchemySession) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "main_menu", step_tree=StepTree(
            branches=[
                StepBranch(
                    name="root",
                    steps=[
                        Step(
                            name="step-1",
                            step_type=InputStep.get_type_string(),
                            step_kwargs={
                                "name": "enter_number",
                                "input_key": "number",
                                "input_prompt": "Please enter a number and then press pound",
                            },
                        ),
                        Step(
                            name="step-2",
                            step_type=PlayMessageStep.get_type_string(),
                            step_kwargs={
                                "template": "You input the following value, {{ step_1_input }}. That was a good number. Goodbye.",
                                "fieldset": [
                                    ("step[root:step-1].input.value", "step_1_input")
                                ]
                            },
                            exit_path={
                                "exit_path_type": HangUpExitPath.get_type_string(),
                            },
                        ),
                    ]
                )

            ]
        ))
        return workflow_factory.create()

    @pytest.fixture
    def workflow_call_routing(self, db_session, simple_workflow: Workflow, greeting: Greeting) -> InboundRouting:
        call_routing = InboundRouting(
            inbound_target="15555555556",
            workflow=simple_workflow,
            active=True,
            greeting=greeting,
            operating_mode="normal",
            priority=0
        )
        db_session.add(call_routing)
        db_session.commit()
        return call_routing

    @pytest.fixture
    def second_workflow_call_routing(self, db_session, simple_workflow: Workflow, greeting: Greeting) -> InboundRouting:
        call_routing = InboundRouting(
            inbound_target="15555555556",
            workflow=simple_workflow,
            active=True,
            greeting=greeting,
            operating_mode="normal",
            priority=10
        )
        db_session.add(call_routing)
        db_session.commit()
        return call_routing

    @pytest.fixture
    def admin_user(self, db_session) -> AdminUser:
        admin_user = AdminUser(
            pin="1234",
            role=AdminRole.admin,
            name="admin test",
            short_id="10"
        )
        db_session.add(admin_user)
        db_session.commit()
        return admin_user

    @pytest.fixture
    def ops_user(self, db_session) -> AdminUser:
        ops_user = AdminUser(
            pin="5678",
            role=AdminRole.user,
            name="ops test"
        )
        db_session.add(ops_user)
        db_session.commit()
        return ops_user

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
    def admin_phone_number(self, db_session, admin_user) -> AdminPhoneNumber:
        phone_number = AdminPhoneNumber(
            phone_number="11235813213",
            user=admin_user
        )
        db_session.add(phone_number)
        db_session.commit()
        return phone_number

    @pytest.fixture
    def ops_phone_number(self, db_session, ops_user) -> AdminPhoneNumber:
        phone_number = AdminPhoneNumber(
            phone_number="13141592653",
            user=ops_user
        )
        db_session.add(phone_number)
        db_session.commit()
        return phone_number

    @pytest.fixture
    def multi_phone_number(self, db_session) -> AdminPhoneNumber:
        phone_number = AdminPhoneNumber(
            phone_number="12718281828",
            user=None
        )
        db_session.add(phone_number)
        db_session.commit()
        return phone_number

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

    def test_new_call(self, db_session, simple_workflow, greeting, admin_call_routing, workflow_call_routing,
                      second_workflow_call_routing, admin_user, ops_user, test_client, admin_phone_number):
        call_form = {"CallSid": "test1",
                     "From": "+11235813213",
                     "To": "+15555555555",
                     "Digits": "1234"}

        start_admin_response = test_client.post("/api/v1/twilio/new", data=call_form)
        assert start_admin_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/verify" actionOnEmptyResult="true" timeout="10"><Say>Please enter your pin</Say></Gather></Response>'

        pin_admin_response = test_client.post("/api/v1/twilio/admin/verify", data=call_form)
        assert pin_admin_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/ani" actionOnEmptyResult="true" timeout="10"><Say>Please enter the customer phone number or ID</Say></Gather></Response>'

        set_ani_call_form = {"CallSid": "test1",
                             "From": "+11235813213",
                             "To": "+15555555555",
                             "Digits": "12345678900"}

        ani_admin_response = test_client.post("/api/v1/twilio/admin/ani", data=set_ani_call_form)
        assert ani_admin_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/dnis" actionOnEmptyResult="true" timeout="10"><Say>Please enter the target phone number or ID</Say></Gather></Response>'

        set_dnis_call_form = {"CallSid": "test1",
                              "From": "+11235813213",
                              "To": "+15555555555",
                              "Digits": "15555555556"}

        dnis_admin_response = test_client.post("/api/v1/twilio/admin/dnis", data=set_dnis_call_form)
        assert dnis_admin_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/routing" actionOnEmptyResult="true" timeout="10"><Say>Please enter the routing priority</Say></Gather></Response>'

        routing_call_form = {"CallSid": "test1",
                             "From": "+11235813213",
                             "To": "+15555555555",
                             "Digits": "0"}

        routing_response = test_client.post("/api/v1/twilio/admin/routing", data=routing_call_form)
        assert routing_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>greeting</Say><Gather action="/api/v1/twilio/continue" actionOnEmptyResult="true" timeout="6"><Say>Please enter a number and then press pound</Say></Gather></Response>'

        workflow_response = test_client.post("/api/v1/twilio/continue", data=call_form)
        assert workflow_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You input the following' \
                                         b' value, 1234. That was a good number. Goodbye.</Say><Hangup /></Response>'

        call_legs = (db_session.query(ContactLeg).
                     options(joinedload(ContactLeg.contact))
                     .filter(ContactLeg.contact_system_id == "test1")
                     .all())
        assert len(call_legs) == 1
        first_leg = call_legs[0]
        contact = first_leg.contact
        assert contact.device_identifier == "12345678900"
        assert contact.inbound_target == "15555555556"
        assert first_leg.workflow_run.workflow.id == simple_workflow.id

    def test_single_route(self, db_session, simple_workflow, greeting, admin_call_routing, workflow_call_routing,
                          admin_user, ops_user, test_client, admin_phone_number):
        call_form = {"CallSid": "test1",
                     "From": "+11235813213",
                     "To": "+15555555555",
                     "Digits": "1234"}

        start_admin_response = test_client.post("/api/v1/twilio/new", data=call_form)
        assert start_admin_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/verify" actionOnEmptyResult="true" timeout="10"><Say>Please enter your pin</Say></Gather></Response>'

        pin_admin_response = test_client.post("/api/v1/twilio/admin/verify", data=call_form)
        assert pin_admin_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/ani" actionOnEmptyResult="true" timeout="10"><Say>Please enter the customer phone number or ID</Say></Gather></Response>'

        set_ani_call_form = {"CallSid": "test1",
                             "From": "+11235813213",
                             "To": "+15555555555",
                             "Digits": "12345678900"}

        ani_admin_response = test_client.post("/api/v1/twilio/admin/ani", data=set_ani_call_form)
        assert ani_admin_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/dnis" actionOnEmptyResult="true" timeout="10"><Say>Please enter the target phone number or ID</Say></Gather></Response>'

        set_dnis_call_form = {"CallSid": "test1",
                              "From": "+11235813213",
                              "To": "+15555555555",
                              "Digits": "15555555556"}

        dnis_admin_response = test_client.post("/api/v1/twilio/admin/dnis", data=set_dnis_call_form)
        assert dnis_admin_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>greeting</Say><Gather action="/api/v1/twilio/continue" actionOnEmptyResult="true" timeout="6"><Say>Please enter a number and then press pound</Say></Gather></Response>'

        workflow_response = test_client.post("/api/v1/twilio/continue", data=call_form)
        assert workflow_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You input the following' \
                                         b' value, 1234. That was a good number. Goodbye.</Say><Hangup /></Response>'

    def test_ten_digit_route(self, db_session, simple_workflow, greeting, admin_call_routing, workflow_call_routing,
                          admin_user, ops_user, test_client, admin_phone_number):
        call_form = {"CallSid": "test1",
                     "From": "+11235813213",
                     "To": "+15555555555",
                     "Digits": "1234"}

        start_admin_response = test_client.post("/api/v1/twilio/new", data=call_form)
        assert start_admin_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/verify" actionOnEmptyResult="true" timeout="10"><Say>Please enter your pin</Say></Gather></Response>'

        pin_admin_response = test_client.post("/api/v1/twilio/admin/verify", data=call_form)
        assert pin_admin_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/ani" actionOnEmptyResult="true" timeout="10"><Say>Please enter the customer phone number or ID</Say></Gather></Response>'

        set_ani_call_form = {"CallSid": "test1",
                             "From": "+11235813213",
                             "To": "+15555555555",
                             "Digits": "2345678900"}

        ani_admin_response = test_client.post("/api/v1/twilio/admin/ani", data=set_ani_call_form)
        assert ani_admin_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/dnis" actionOnEmptyResult="true" timeout="10"><Say>Please enter the target phone number or ID</Say></Gather></Response>'

        no_routing_number_form = {"CallSid": "test1",
                            "From": "+13141592653",
                            "To": "+15555555555",
                            "Digits": "2345678999"}

        no_routing_response = test_client.post("/api/v1/twilio/admin/dnis", data=no_routing_number_form)
        assert no_routing_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/dnis" actionOnEmptyResult="true" timeout="10"><Say>Invalid number, Please enter the target phone number or ID</Say></Gather></Response>'

        set_dnis_call_form = {"CallSid": "test1",
                              "From": "+11235813213",
                              "To": "+15555555555",
                              "Digits": "5555555556"}

        dnis_admin_response = test_client.post("/api/v1/twilio/admin/dnis", data=set_dnis_call_form)
        assert dnis_admin_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>greeting</Say><Gather action="/api/v1/twilio/continue" actionOnEmptyResult="true" timeout="6"><Say>Please enter a number and then press pound</Say></Gather></Response>'

        workflow_response = test_client.post("/api/v1/twilio/continue", data=call_form)
        assert workflow_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You input the following' \
                                         b' value, 1234. That was a good number. Goodbye.</Say><Hangup /></Response>'

    def test_short_cuts(self, db_session, simple_workflow, greeting, admin_call_routing, workflow_call_routing,
                        admin_user, ops_user, ani_shortcut, dnis_shortcut, test_client, admin_phone_number):
        call_form = {"CallSid": "test1",
                     "From": "+11235813213",
                     "To": "+15555555555",
                     "Digits": "1234"}

        start_admin_response = test_client.post("/api/v1/twilio/new", data=call_form)
        assert start_admin_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/verify" actionOnEmptyResult="true" timeout="10"><Say>Please enter your pin</Say></Gather></Response>'

        pin_admin_response = test_client.post("/api/v1/twilio/admin/verify", data=call_form)
        assert pin_admin_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/ani" actionOnEmptyResult="true" timeout="10"><Say>Please enter the customer phone number or ID</Say></Gather></Response>'

        shortcut_form = {"CallSid": "test1",
                         "From": "+11235813213",
                         "To": "+15555555555",
                         "Digits": "10"}

        ani_admin_response = test_client.post("/api/v1/twilio/admin/ani", data=shortcut_form)
        assert ani_admin_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/dnis" actionOnEmptyResult="true" timeout="10"><Say>Please enter the target phone number or ID</Say></Gather></Response>'

        dnis_admin_response = test_client.post("/api/v1/twilio/admin/dnis", data=shortcut_form)
        assert dnis_admin_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>greeting</Say><Gather action="/api/v1/twilio/continue" actionOnEmptyResult="true" timeout="6"><Say>Please enter a number and then press pound</Say></Gather></Response>'

        workflow_response = test_client.post("/api/v1/twilio/continue", data=call_form)
        assert workflow_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You input the following' \
                                         b' value, 1234. That was a good number. Goodbye.</Say><Hangup /></Response>'

    def test_ops_bad_input(self, db_session, simple_workflow, greeting, admin_call_routing, workflow_call_routing,
                           second_workflow_call_routing, admin_user, ops_user, ani_shortcut, dnis_shortcut, test_client,
                           ops_phone_number, admin_phone_number):
        call_form = {"CallSid": "test1",
                     "From": "+13141592653",
                     "To": "+15555555555",
                     "Digits": "5678"}
        start_ops_response = test_client.post("/api/v1/twilio/new", data=call_form)

        assert start_ops_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/verify" actionOnEmptyResult="true" timeout="10"><Say>Please enter your pin</Say></Gather></Response>'

        pin_ops_response = test_client.post("/api/v1/twilio/admin/verify", data=call_form)
        assert pin_ops_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/ani" actionOnEmptyResult="true" timeout="10"><Say>Please enter the ID for the customer number</Say></Gather></Response>'

        shortcut_form = {"CallSid": "test1",
                         "From": "+13141592653",
                         "To": "+15555555555",
                         "Digits": "10"}

        missing_shortcut_form = {"CallSid": "test1",
                                 "From": "+13141592653",
                                 "To": "+15555555555",
                                 "Digits": "11"}

        full_number_form = {"CallSid": "test1",
                            "From": "+13141592653",
                            "To": "+15555555555",
                            "Digits": "12345678900"}

        ani_ops_full_response = test_client.post("/api/v1/twilio/admin/ani", data=full_number_form)
        assert ani_ops_full_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/ani" actionOnEmptyResult="true" timeout="10"><Say>Invalid number, Please enter the ID for the customer number</Say></Gather></Response>'

        ani_ops_missing_response = test_client.post("/api/v1/twilio/admin/ani", data=missing_shortcut_form)
        assert ani_ops_missing_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/ani" actionOnEmptyResult="true" timeout="10"><Say>Invalid number, Please enter the ID for the customer number</Say></Gather></Response>'

        ani_ops_response = test_client.post("/api/v1/twilio/admin/ani", data=shortcut_form)
        assert ani_ops_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/dnis" actionOnEmptyResult="true" timeout="10"><Say>Please enter the ID for the target number</Say></Gather></Response>'

        dnis_ops_full_response = test_client.post("/api/v1/twilio/admin/dnis", data=full_number_form)
        assert dnis_ops_full_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/dnis" actionOnEmptyResult="true" timeout="10"><Say>Invalid number, Please enter the ID for the target number</Say></Gather></Response>'

        dnis_ops_missing_response = test_client.post("/api/v1/twilio/admin/dnis", data=missing_shortcut_form)
        assert dnis_ops_missing_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/dnis" actionOnEmptyResult="true" timeout="10"><Say>Invalid number, Please enter the ID for the target number</Say></Gather></Response>'

        dnis_ops_response = test_client.post("/api/v1/twilio/admin/dnis", data=shortcut_form)
        assert dnis_ops_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/routing" actionOnEmptyResult="true" timeout="10"><Say>Please enter the routing priority</Say></Gather></Response>'

        routing_bad_priority_response = test_client.post("/api/v1/twilio/admin/routing", data=missing_shortcut_form)
        assert routing_bad_priority_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/routing" actionOnEmptyResult="true" timeout="10"><Say>Invalid routing priority, Please enter the routing priority</Say></Gather></Response>'

        routing_good_priority_response = test_client.post("/api/v1/twilio/admin/routing", data=shortcut_form)
        assert routing_good_priority_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>greeting</Say><Gather action="/api/v1/twilio/continue" actionOnEmptyResult="true" timeout="6"><Say>Please enter a number and then press pound</Say></Gather></Response>'

        workflow_response = test_client.post("/api/v1/twilio/continue", data=call_form)
        assert workflow_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>You input the following' \
                                         b' value, 5678. That was a good number. Goodbye.</Say><Hangup /></Response>'

    def test_phone_number_checks(self, db_session, simple_workflow, greeting, admin_call_routing, workflow_call_routing,
                                 second_workflow_call_routing, admin_user, ops_user, ani_shortcut, dnis_shortcut,
                                 test_client,
                                 ops_phone_number, admin_phone_number, multi_phone_number):
        bad_number_form = {"CallSid": "test_bad",
                           "From": "+11111111111",
                           "To": "+15555555555",
                           "Digits": "5678"}
        bad_number_response = test_client.post("/api/v1/twilio/new", data=bad_number_form)
        assert bad_number_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Hangup /></Response>'

        admin_form = {"CallSid": "test_admin",
                      "From": "+13141592653",
                      "To": "+15555555555",
                      "Digits": "10"}
        admin_response = test_client.post("/api/v1/twilio/new", data=admin_form)
        assert admin_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/verify" actionOnEmptyResult="true" timeout="10"><Say>Please enter your pin</Say></Gather></Response>'

        multi_form = {"CallSid": "test_multi",
                      "From": "+12718281828",
                      "To": "+15555555555",
                      "Digits": "10"}
        multi_response = test_client.post("/api/v1/twilio/new", data=multi_form)
        assert multi_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/login" actionOnEmptyResult="true" timeout="10"><Say>Please enter your user ID shortcode</Say></Gather></Response>'

        user_select_response = test_client.post("/api/v1/twilio/admin/login", data=multi_form)
        assert user_select_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/verify" actionOnEmptyResult="true" timeout="10"><Say>Please enter your pin</Say></Gather></Response>'

        multi_form_bad_id = {"CallSid": "test_multi",
                             "From": "+12718281828",
                             "To": "+15555555555",
                             "Digits": "11"}
        multi_response = test_client.post("/api/v1/twilio/new", data=multi_form_bad_id)
        assert multi_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/login" actionOnEmptyResult="true" timeout="10"><Say>Please enter your user ID shortcode</Say></Gather></Response>'

        bad_user_id_response = test_client.post("/api/v1/twilio/admin/login", data=bad_number_form)
        assert bad_user_id_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Invalid User ID</Say><Hangup /></Response>'

    def test_call_verification(self, db_session, simple_workflow, greeting, admin_call_routing, workflow_call_routing,
                               admin_user, admin_phone_number, test_client):
        bad_number_form = {"CallSid": "test_bad",
                           "From": "+11111111111",
                           "To": "+15555555555",
                           "Digits": "5678"}
        bad_number_response = test_client.post("/api/v1/twilio/new", data=bad_number_form)
        assert bad_number_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Hangup /></Response>'


        unverified_response = test_client.post("/api/v1/twilio/admin/verify", data=bad_number_form)
        assert unverified_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Hangup /></Response>'

        unverified_ani_response = test_client.post("/api/v1/twilio/admin/ani", data=bad_number_form)
        assert unverified_ani_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Hangup /></Response>'

        unverified_dnis_response = test_client.post("/api/v1/twilio/admin/dnis", data=bad_number_form)
        assert unverified_dnis_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Hangup /></Response>'

        unverified_routing_response = test_client.post("/api/v1/twilio/admin/routing", data=bad_number_form)
        assert unverified_routing_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Hangup /></Response>'

        good_number_invalid_pin_form = {"CallSid": "test_invalid_pin",
                           "From": "+11235813213",
                           "To": "+15555555555",
                           "Digits": "5678"}

        create_call_response = test_client.post("/api/v1/twilio/new", data=good_number_invalid_pin_form)
        assert create_call_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/verify" actionOnEmptyResult="true" timeout="10"><Say>Please enter your pin</Say></Gather></Response>'

        invalid_pin_response = test_client.post("/api/v1/twilio/admin/verify", data=good_number_invalid_pin_form)
        assert invalid_pin_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Invalid Pin</Say><Hangup /></Response>'



    def test_scheduled_call(self, db_session, simple_workflow, greeting, admin_call_routing, workflow_call_routing,
                            admin_user, admin_phone_number, test_client):
        call_form = {"CallSid": "test1",
                     "From": "+11235813213",
                     "To": "+15555555555",
                     "Digits": "1234"}

        start_admin_response = test_client.post("/api/v1/twilio/new", data=call_form)
        assert start_admin_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/verify" actionOnEmptyResult="true" timeout="10"><Say>Please enter your pin</Say></Gather></Response>'

        pin_admin_response = test_client.post("/api/v1/twilio/admin/verify", data=call_form)
        assert pin_admin_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/ani" actionOnEmptyResult="true" timeout="10"><Say>Please enter the customer phone number or ID</Say></Gather></Response>'

        scheduled_call = ScheduledCall()
        scheduled_call.user = admin_user
        scheduled_call.inbound_routing = workflow_call_routing
        scheduled_call.ani = "12345678900"
        scheduled_call.dnis = "15555555556"
        db_session.add(scheduled_call)
        db_session.commit()

        call_form2 = {"CallSid": "test2",
                     "From": "+11235813213",
                     "To": "+15555555555",
                     "Digits": "1234"}

        scheduled_admin_response = test_client.post("/api/v1/twilio/new", data=call_form2)
        assert scheduled_admin_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/verify" actionOnEmptyResult="true" timeout="10"><Say>Please enter your pin</Say></Gather></Response>'

        pin_response = test_client.post("/api/v1/twilio/admin/verify", data=call_form2)
        assert pin_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>greeting</Say><Gather action="/api/v1/twilio/continue" actionOnEmptyResult="true" timeout="6"><Say>Please enter a number and then press pound</Say></Gather></Response>'

        call_legs = (db_session.query(ContactLeg).
                     options(joinedload(ContactLeg.contact))
                     .filter(ContactLeg.contact_system_id == "test2")
                     .all())
        assert len(call_legs) == 1
        first_leg = call_legs[0]
        contact = first_leg.contact
        assert contact.device_identifier == "12345678900"
        assert contact.inbound_target == "15555555556"
        assert first_leg.workflow_run.workflow.id == simple_workflow.id

        call_form3 = {"CallSid": "test3",
                     "From": "+11235813213",
                     "To": "+15555555555",
                     "Digits": "1234"}

        start_admin_response = test_client.post("/api/v1/twilio/new", data=call_form3)
        assert start_admin_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/verify" actionOnEmptyResult="true" timeout="10"><Say>Please enter your pin</Say></Gather></Response>'

        pin_admin_response = test_client.post("/api/v1/twilio/admin/verify", data=call_form3)
        assert pin_admin_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/ani" actionOnEmptyResult="true" timeout="10"><Say>Please enter the customer phone number or ID</Say></Gather></Response>'

    def test_scheduled_call_no_routing(self, db_session, simple_workflow, greeting, admin_call_routing, admin_user, admin_phone_number, admin_call, test_client):
        call_form = {"CallSid": "test1",
                     "From": "+11235813213",
                     "To": "+15555555555",
                     "Digits": "1234"}

        start_admin_response = test_client.post("/api/v1/twilio/new", data=call_form)
        assert start_admin_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/verify" actionOnEmptyResult="true" timeout="10"><Say>Please enter your pin</Say></Gather></Response>'

        pin_admin_response = test_client.post("/api/v1/twilio/admin/verify", data=call_form)
        assert pin_admin_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/ani" actionOnEmptyResult="true" timeout="10"><Say>Please enter the customer phone number or ID</Say></Gather></Response>'

        scheduled_call = ScheduledCall()
        scheduled_call.user = admin_user
        scheduled_call.workflow_id = simple_workflow.id
        db_session.add(scheduled_call)
        db_session.commit()
        admin_call.scheduled_call_id = scheduled_call
        db_session.add(admin_call)
        db_session.commit()

        call_form2 = {"CallSid": "test2",
                      "From": "+11235813213",
                      "To": "+15555555555",
                      "Digits": "1234"}

        scheduled_admin_response = test_client.post("/api/v1/twilio/new", data=call_form2)
        assert scheduled_admin_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/verify" actionOnEmptyResult="true" timeout="10"><Say>Please enter your pin</Say></Gather></Response>'

        pin_response = test_client.post("/api/v1/twilio/admin/verify", data=call_form2)
        assert pin_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/continue" actionOnEmptyResult="true" timeout="6"><Say>Please enter a number and then press pound</Say></Gather></Response>'

        call_legs = (db_session.query(ContactLeg).
                     options(joinedload(ContactLeg.contact))
                     .filter(ContactLeg.contact_system_id == "test2")
                     .all())
        assert len(call_legs) == 1
        first_leg = call_legs[0]
        assert first_leg.workflow_run.workflow.id == simple_workflow.id

        call_form3 = {"CallSid": "test3",
                      "From": "+11235813213",
                      "To": "+15555555555",
                      "Digits": "1234"}

        start_admin_response = test_client.post("/api/v1/twilio/new", data=call_form3)
        assert start_admin_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/verify" actionOnEmptyResult="true" timeout="10"><Say>Please enter your pin</Say></Gather></Response>'

        pin_admin_response = test_client.post("/api/v1/twilio/admin/verify", data=call_form3)
        assert pin_admin_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/ani" actionOnEmptyResult="true" timeout="10"><Say>Please enter the customer phone number or ID</Say></Gather></Response>'

    def test_bad_auth(self, monkeypatch, test_client):
        monkeypatch.setenv("TELEPHONY_AUTHENTICATION_REQUIRED", "true")
        call_form = {"CallSid": "test1",
                     "From": "+11235813213",
                     "To": "+15555555555",
                     "Digits": "1234"}
        response = test_client.post("/api/v1/twilio/new", data=call_form)
        assert response.status == '401 UNAUTHORIZED'

    def test_scheduled_call_through_admin_endpoint(self, db_session, simple_workflow, greeting, admin_call_routing, workflow_call_routing,
                            admin_user, admin_phone_number, test_client, api_credential: ApiCredential, auth_header):

        request_json = {
            "user_id": str(admin_user.id),
            "dnis": "15555555556",
            "ani": "12345678900",
            "call_routing_id": workflow_call_routing.id
        }

        response = test_client.post("api/v1/admin/scheduled_calls", json=request_json, headers=auth_header)
        assert response.status_code == 200

        call_form = {"CallSid": "test",
                     "From": "+11235813213",
                     "To": "+15555555555",
                     "Digits": "1234"}

        scheduled_admin_response = test_client.post("/api/v1/twilio/new", data=call_form)
        assert scheduled_admin_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/verify" actionOnEmptyResult="true" timeout="10"><Say>Please enter your pin</Say></Gather></Response>'

        pin_response = test_client.post("/api/v1/twilio/admin/verify", data=call_form)
        assert pin_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Say>greeting</Say><Gather action="/api/v1/twilio/continue" actionOnEmptyResult="true" timeout="6"><Say>Please enter a number and then press pound</Say></Gather></Response>'

        call_legs = (db_session.query(ContactLeg).
                     options(joinedload(ContactLeg.contact))
                     .filter(ContactLeg.contact_system_id == "test")
                     .all())
        assert len(call_legs) == 1
        first_leg = call_legs[0]
        contact = first_leg.contact
        assert contact.device_identifier == "12345678900"
        assert contact.inbound_target == "15555555556"
        assert first_leg.workflow_run.workflow.id == simple_workflow.id

        call_form2 = {"CallSid": "test2",
                      "From": "+11235813213",
                      "To": "+15555555555",
                      "Digits": "1234"}

        start_admin_response = test_client.post("/api/v1/twilio/new", data=call_form2)
        assert start_admin_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/verify" actionOnEmptyResult="true" timeout="10"><Say>Please enter your pin</Say></Gather></Response>'

        pin_admin_response = test_client.post("/api/v1/twilio/admin/verify", data=call_form2)
        assert pin_admin_response.data == b'<?xml version="1.0" encoding="UTF-8"?><Response><Gather action="/api/v1/twilio/admin/ani" actionOnEmptyResult="true" timeout="10"><Say>Please enter the customer phone number or ID</Say></Gather></Response>'
