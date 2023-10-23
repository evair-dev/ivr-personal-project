from datetime import date

import pytest
import uuid

import time_machine
from sqlalchemy import orm

from commands.db import Db
from ivr_gateway.exit_paths import HangUpExitPath
from ivr_gateway.models.admin import AdminCall, AdminUser, AdminPhoneNumber, ApiCredential, ScheduledCall, \
    AdminCallFrom, AdminCallTo
from ivr_gateway.models.contacts import Greeting, InboundRouting, Contact, TransferRouting
from ivr_gateway.models.queues import Queue, QueueHoliday, QueueHoursOfOperation
from ivr_gateway.models.steps import StepRun, StepState
from ivr_gateway.models.workflows import Workflow, WorkflowRun
from ivr_gateway.services.admin import AdminService
from ivr_gateway.services.queues import QueueService
from ivr_gateway.steps.api.v1 import InputStep, PlayMessageStep
from ivr_gateway.steps.config import StepTree, StepBranch, Step
from tests.factories import workflow as wcf
from tests.factories import queues as qf


class TestDbCommand:

    @pytest.fixture
    def queue_service(self, db_session: orm.Session):
        return QueueService(db_session)

    @pytest.fixture
    def workflow(self, db_session: orm.Session) -> Workflow:
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
                                "template": "You input the following value, {{ session.number }}. That was a good number. Goodbye.",
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
    def greeting(self, db_session) -> Greeting:
        greeting = Greeting(message='hello from <phoneme alphabet="ipa" ph="əˈvɑnt">Iivr</phoneme>.')
        db_session.add(greeting)
        db_session.commit()
        return greeting

    @pytest.fixture
    def Iivr_any_queue(self, db_session) -> Queue:
        queue = qf.queue_factory(db_session).create(
            name="Iivr.LN.ANY")
        return queue

    @pytest.fixture
    def Iivr_any_queue_with_holiday(self, db_session, Iivr_any_queue, queue_service: QueueService):
        traveller = time_machine.travel("2020-12-23 19:00")
        traveller.start()
        queue_service.add_holiday_for_queue(Iivr_any_queue, "Christmas", date(2020, 12, 25))
        traveller.stop()
        return Iivr_any_queue

    @pytest.fixture
    def call_routing(self, db_session, workflow: Workflow, greeting: Greeting) -> InboundRouting:
        call_routing = InboundRouting(
            inbound_target="15555555555",
            workflow=workflow,
            active=True,
            greeting=greeting,
            operating_mode="normal"
        )
        db_session.add(call_routing)
        db_session.commit()
        return call_routing

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
    def admin_user(self, db_session: orm.Session) -> AdminUser:
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
    def admin_phone_number(self, db_session: orm.Session, admin_user: AdminUser) -> AdminPhoneNumber:
        admin_phone_number = AdminPhoneNumber(
            user_id=admin_user.id,
            phone_number="4108339999",
            name="Some Weird Phone Number"
        )

        db_session.add(admin_phone_number)
        db_session.commit()
        return admin_phone_number


    @pytest.fixture
    def scheduled_call(self, db_session: orm.Session, admin_user: AdminUser):
        scheduled_call = ScheduledCall()
        scheduled_call.user = admin_user
        scheduled_call.ani = "12345678900"
        scheduled_call.dnis = "15555555556"

        return scheduled_call


    @pytest.fixture
    def admin_call(self, db_session: orm.Session, admin_user: AdminUser) -> AdminCall:
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
    def ani_shortcut(self, db_session) -> AdminCallFrom:
        ani = AdminCallFrom(
            short_number="10",
            full_number="12345678900"
        )
        db_session.add(ani)
        db_session.commit()
        return ani

    @pytest.fixture
    def dnis_shortcut(self, db_session) -> AdminCallTo:
        dnis = AdminCallTo(
            short_number="10",
            full_number="15555555556"
        )
        db_session.add(dnis)
        db_session.commit()
        return dnis

    def test_cleaning_database(self, db_session, test_client, test_cli_runner, workflow, call_routing):
        # Add some calls
        form = {"CallSid": "test",
                "To": "+15555555555",
                "Digits": "1234"}
        for i in range(10):
            form["CallSid"] = f"test-{i}"
            test_client.post("/api/v1/twilio/new", data=form)
            test_client.post("/api/v1/twilio/continue", data=form)
        assert db_session.query(WorkflowRun).count() == 10
        result = test_cli_runner.invoke(Db.clear_workflow_runs)
        assert "Runs Cleared." in result.output
        assert db_session.query(WorkflowRun).count() == 0
        assert db_session.query(Workflow).count() == 1
        assert db_session.query(StepRun).count() == 0
        assert db_session.query(StepState).count() == 0

    def test_clear_call_routing_transfer_and_admin_data(self, db_session, test_client, test_cli_runner, workflow,
                                                        call_routing, admin_call_routing, admin_call, scheduled_call):
        # Add some calls
        form = {"CallSid": "test",
                "To": "+15555555555",
                "Digits": "1234"}
        for i in range(10):
            form["CallSid"] = f"test-{i}"
            test_client.post("/api/v1/twilio/new", data=form)
            test_client.post("/api/v1/twilio/continue", data=form)
        assert db_session.query(WorkflowRun).count() == 10
        test_cli_runner.invoke(Db.clear_workflow_runs)
        test_cli_runner.invoke(Db.clear_call_inbound_transfer_and_admin_data)
        assert db_session.query(Contact).count() == 0
        assert db_session.query(TransferRouting).count() == 0
        assert db_session.query(InboundRouting).count() == 0
        assert db_session.query(Greeting).count() == 0
        assert db_session.query(AdminCall).count() == 0
        assert db_session.query(ScheduledCall).count() == 0

    def test_clear_queues(self, db_session, test_cli_runner, Iivr_any_queue_with_holiday):
        test_cli_runner.invoke(Db.clear_queues)

        assert db_session.query(Queue).count() == 0
        assert db_session.query(QueueHoliday).count() == 0
        assert db_session.query(QueueHoursOfOperation).count() == 0

    def clear_admin_shortcuts(self, db_session, test_cli_runner, dnis_shortcut, ani_shortcut):
        test_cli_runner.invoke(Db.clear_admin_shortcuts)

        assert db_session.query(AdminCallTo).count() == 0
        assert db_session.query(AdminCallFrom).count == 0



