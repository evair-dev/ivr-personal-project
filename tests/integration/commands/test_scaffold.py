import os
from datetime import datetime

import pytest
import time_machine
from sqlalchemy import orm

from commands.scaffold import Scaffold
from ivr_gateway.exit_paths import HangUpExitPath
from ivr_gateway.models.contacts import InboundRouting, TransferRouting, Greeting
from ivr_gateway.models.queues import Queue, QueueHoursOfOperation, QueueHoliday
from ivr_gateway.models.workflows import Workflow, WorkflowConfig
from ivr_gateway.services.admin import AdminService
from ivr_gateway.services.queues import QueueService
from ivr_gateway.services.workflows import WorkflowService
from ivr_gateway.steps.api.v1 import PlayMessageStep, InputStep
from ivr_gateway.steps.config import StepBranch, Step, StepTree
from tests.factories import workflow as wcf
from tests.factories import queues as qf


class TestScaffoldCommand:
    @pytest.fixture
    def queue_service(self, db_session):
        return QueueService(db_session)

    @pytest.fixture
    def admin_service(self, db_session):
        return AdminService(db_session)

    @pytest.fixture
    def workflow_service(self, db_session):
        return WorkflowService(db_session)

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
    def Iivr_test_queue(self, db_session) -> Queue:
        queue = qf.queue_factory(db_session).create(
            name="Iivr.test.queue", hours_of_operation=[])
        return queue

    @pytest.fixture
    def Iivr_test_queue_two(self, db_session) -> Queue:
        queue = qf.queue_factory(db_session).create(
            name="Iivr.test.two", hours_of_operation=[])
        return queue

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

    @time_machine.travel("2020-12-29 19:00")
    def test_create_holiday_hours_valid_payload(self, test_cli_runner, Iivr_any_queue):
        config_file_path = f"{os.path.dirname(__file__)}/test_holiday_hours_config.json"
        result = test_cli_runner.invoke(
            Scaffold.create_holiday_hours,
            args=['--config-file-path', config_file_path])
        assert "Creating holiday hours for test_holiday" in result.output
        assert "Holiday hours for test_holiday created" in result.output
        assert "All holiday hours successfully created." in result.output

    @time_machine.travel("2020-12-29 19:00")
    def test_create_holiday_hours_valid_payload_nested(self, db_session, test_cli_runner, Iivr_any_queue,
                                                       Iivr_test_queue, Iivr_test_queue_two):
        config_file_path = f"{os.path.dirname(__file__)}/test_holiday_hours_config_nested.json"
        result = test_cli_runner.invoke(
            Scaffold.create_holiday_hours,
            args=['--config-file-path', config_file_path])
        assert "Creating holiday hours for test_holiday" in result.output
        assert "Holiday hours for test_holiday created" in result.output
        assert "All holiday hours successfully created." in result.output

        holiday_result = (db_session.query(QueueHoliday)
                          .join(Queue)
                          .filter(Queue.id == Iivr_any_queue.id)
                          .first())
        assert holiday_result.name == "test_holiday"
        assert holiday_result.start_time == datetime.strptime("09:00", '%H:%M').time()
        assert holiday_result.end_time == datetime.strptime("14:00", '%H:%M').time()
        assert holiday_result.date == datetime.fromisoformat("2021-12-31").date()

        holiday_result = (db_session.query(QueueHoliday)
                          .join(Queue)
                          .filter(Queue.id == Iivr_test_queue.id)
                          .first())
        assert holiday_result.name == "test_holiday"
        assert holiday_result.start_time == datetime.strptime("09:00", '%H:%M').time()
        assert holiday_result.end_time == datetime.strptime("14:00", '%H:%M').time()
        assert holiday_result.date == datetime.fromisoformat("2021-12-31").date()

        holiday_result = (db_session.query(QueueHoliday)
                          .join(Queue)
                          .filter(Queue.id == Iivr_test_queue_two.id)
                          .first())
        assert holiday_result.name == "test_holiday"
        assert holiday_result.start_time is None
        assert holiday_result.end_time is None
        assert holiday_result.date == datetime.fromisoformat("2021-12-31").date()

    def test_create_holiday_hours_invalid_payload(self, test_cli_runner):
        config_file_path = f"{os.path.dirname(__file__)}/test_holiday_hours_config.json"
        result = test_cli_runner.invoke(
            Scaffold.create_holiday_hours,
            args=['--config-file-path', config_file_path])
        assert "One of the queue names provided does not exist" == str(result.exception)

    def test_create_inbound_routing(self, test_cli_runner, db_session, greeting, Iivr_any_queue, workflow):
        phone_number = '17738885555'
        result = test_cli_runner.invoke(
            Scaffold.create_inbound_routing,
            args=['--contact-type', 'IVR',
                  '--inbound-target', '17738885555',
                  '--greeting-message', f"{greeting.message}",
                  '--workflow-name', workflow.workflow_name,
                  '--is-active', f"{True}",
                  '--initial-queue-name', Iivr_any_queue.name])

        assert "Inbound routing setup successfully." in result.output
        assert db_session.query(InboundRouting).filter(InboundRouting.inbound_target == phone_number).one_or_none()

    def test_create_inbound_routing_upsert(self, test_cli_runner, db_session, greeting, Iivr_any_queue, workflow):
        phone_number = '17738885555'

        test_cli_runner.invoke(
            Scaffold.create_inbound_routing,
            args=['--contact-type', 'IVR',
                  '--inbound-target', '17738885555',
                  '--greeting-message', f"{greeting.message}",
                  '--workflow-name', workflow.workflow_name,
                  '--is-active', f"{True}",
                  '--initial-queue-name', Iivr_any_queue.name])

        result = test_cli_runner.invoke(
            Scaffold.create_inbound_routing,
            args=['--contact-type', 'IVR',
                  '--inbound-target', '17738885555',
                  '--greeting-message', f"{greeting.message}",
                  '--workflow-name', workflow.workflow_name,
                  '--is-active', f"{True}",
                  '--is-admin', f"{False}",
                  '--initial-queue-name', Iivr_any_queue.name,
                  '--upsert'])

        assert "An inbound routing already exists for 17738885555." in result.output
        assert "Inbound routing setup successfully." in result.output
        assert db_session.query(InboundRouting).filter(InboundRouting.inbound_target == phone_number).filter(
            InboundRouting.active).one_or_none()

    def test_create_inbound_routing_contact_types(self, test_cli_runner, db_session, greeting, Iivr_any_queue,
                                                  workflow):
        inbound_routings = [('123', 'IVR'), ('456', 'SMS'), ('CreditSesame', 'CHAT')]

        for target, contact_type in inbound_routings:
            test_cli_runner.invoke(
                Scaffold.create_inbound_routing,
                args=['--contact-type', contact_type,
                      '--inbound-target', target,
                      '--greeting-message', f"{greeting.message}",
                      '--workflow-name', workflow.workflow_name,
                      '--is-active', f"{True}",
                      '--initial-queue-name', Iivr_any_queue.name])

        assert db_session.query(InboundRouting).filter(
            InboundRouting.inbound_target == '123').one_or_none().contact_type == 'ivr'
        assert db_session.query(InboundRouting).filter(
            InboundRouting.inbound_target == '456').one_or_none().contact_type == 'sms'
        assert db_session.query(InboundRouting).filter(
            InboundRouting.inbound_target == 'CreditSesame').one_or_none().contact_type == 'chat'

    def test_create_inbound_routing_invalid_contact_types(self, test_cli_runner, db_session, greeting, Iivr_any_queue,
                                                          workflow):
        invalid_contact_type = 'TELEPHONE'

        result = test_cli_runner.invoke(
            Scaffold.create_inbound_routing,
            args=['--contact-type', invalid_contact_type,
                  '--inbound-target', '17738885555',
                  '--greeting-message', f"{greeting.message}",
                  '--workflow-name', workflow.workflow_name,
                  '--is-active', f"{True}",
                  '--initial-queue-name', Iivr_any_queue.name])

        assert f"Invalid value for '--contact-type': '{invalid_contact_type}'" in result.output

    def test_create_inbound_routings_invalid_contact_types(self, test_cli_runner, db_session, greeting, Iivr_any_queue,
                                                           workflow):
        config_file_path = f"{os.path.dirname(__file__)}/test_inbound_routing_invalid_contact_type_config.json"

        result = test_cli_runner.invoke(
            Scaffold.create_inbound_routings,
            args=['--config-file-path', config_file_path])

        assert "Invalid Key Error" in result.output

    def test_create_duplicate_inbound_routing(self, test_cli_runner, db_session, greeting, Iivr_any_queue, workflow):
        test_cli_runner.invoke(
            Scaffold.create_inbound_routing,
            args=['--contact-type', 'IVR',
                  '--inbound-target', '17738885555',
                  '--greeting-message', f"{greeting.message}",
                  '--workflow-name', workflow.workflow_name,
                  '--is-active', f"{True}",
                  '--initial-queue-name', Iivr_any_queue.name])

        result = test_cli_runner.invoke(
            Scaffold.create_inbound_routing,
            args=['--contact-type', 'IVR',
                  '--inbound-target', '17738885555',
                  '--greeting-message', f"{greeting.message}",
                  '--workflow-name', workflow.workflow_name,
                  '--is-active', f"{True}",
                  '--initial-queue-name', Iivr_any_queue.name])

        assert "An inbound routing already exists for 17738885555." in result.output

    def test_create_inbound_routings_valid_case(self, test_cli_runner, db_session, greeting, Iivr_any_queue, workflow):
        config_file_path = f"{os.path.dirname(__file__)}/test_inbound_routing_config.json"
        result = test_cli_runner.invoke(
            Scaffold.create_inbound_routings,
            args=['--config-file-path', config_file_path])
        assert "Inbound routing configs created." in result.output
        assert db_session.query(InboundRouting).filter(InboundRouting.inbound_target == "17732073682").one_or_none()
        assert db_session.query(InboundRouting).filter(InboundRouting.inbound_target == "17732073700").one_or_none()
        assert db_session.query(InboundRouting).filter(InboundRouting.inbound_target == "1234567890").one_or_none()

    def test_create_inbound_routings_duplicate_routing(self, test_cli_runner, db_session, greeting, Iivr_any_queue,
                                                       workflow):
        config_file_path = f"{os.path.dirname(__file__)}/test_inbound_routing_config.json"
        test_cli_runner.invoke(Scaffold.create_inbound_routings, args=['--config-file-path', config_file_path])
        result = test_cli_runner.invoke(
            Scaffold.create_inbound_routings,
            args=['--config-file-path', config_file_path])
        assert "There are inbound routings that exist for the following numbers:" in result.output

    def test_create_inbound_routings_upsert(self, test_cli_runner, db_session, greeting, Iivr_any_queue, workflow):
        config_file_path = f"{os.path.dirname(__file__)}/test_inbound_routing_config.json"
        test_cli_runner.invoke(
            Scaffold.create_inbound_routings,
            args=['--config-file-path', config_file_path])
        result = test_cli_runner.invoke(
            Scaffold.create_inbound_routings,
            args=['--config-file-path', config_file_path, '--upsert'])

        assert "There are inbound routings that exist for the following numbers:" in result.output
        assert "Inbound routing configs created." in result.output

    def test_create_inbound_routing_no_preexisting_greeting(self, test_cli_runner, db_session, Iivr_any_queue,
                                                            workflow):
        phone_number = '17738885555'
        result = test_cli_runner.invoke(
            Scaffold.create_inbound_routing,
            args=['--contact-type', 'IVR',
                  '--inbound-target', '17738885555',
                  '--greeting-message', "Woah - a new greeting for Avant!",
                  '--workflow-name', workflow.workflow_name,
                  '--is-active', f"{True}",
                  '--initial-queue-name', Iivr_any_queue.name])

        assert "Inbound routing setup successfully." in result.output
        assert db_session.query(InboundRouting).filter(InboundRouting.inbound_target == phone_number).one_or_none()
        assert db_session.query(Greeting).filter(Greeting.message == "Woah - a new greeting for Avant!").one_or_none()

    def test_setup_dev(self, db_session, test_cli_runner):
        expected_workflows = [
            "Iivr.ingress",
            "Iivr.main_menu",
            "Iivr.secure_call",
            "Iivr.self_service_menu",
            "Iivr.make_payment",
            "Iivr.loan_origination",
            "shared.ivr_customer_lookup",
            "Iivr.ivr.activate_card"
            "Iivr.sms.make_payment_sms",
            "shared.ivr.noop_queue_transfer",
            "shared.ivr_telco_customer_lookup",
            "shared.ivr_customer_lookup",
            "shared.banking_menu"
        ]

        expected_queues = [
            "AFC.LN.PAY.INT",
            "AFC.LN.PAY.EXT",
            "AFC.LN.PAY.AH",
            "AFC.LN.CUS",
            "AFC.LN.ORIG",
            "AFC.CC.CUS",
            "AFC.CC.ORIG",
            "AFC.CC.PAY.INT",
            "AFC.CC.PAY.EXT",
            "Iivr.unsecured.ANY",
            "Iivr.unsecured.PAY"
        ]

        result = test_cli_runner.invoke(
            Scaffold.setup_dev,
            args=['--main-menu-phone-number', '17738885555',
                  '--admin-routing-phone-number', '14438342310'])

        assert "Initial queues and their routings are set up." in result.output
        assert "Inbound routings set up." in result.output
        assert "Admin inbound routings set up." in result.output
        assert db_session.query(InboundRouting).count() == 2
        assert db_session.query(TransferRouting).count() == 13
        assert db_session.query(QueueHoursOfOperation).count() == 80
        assert db_session.query(Queue).count() == len(expected_queues)
        assert db_session.query(Workflow).count() == len(expected_workflows)
        assert db_session.query(WorkflowConfig).filter(WorkflowConfig.tag.isnot(None)).count() == len(
            expected_workflows)

    def test_setup_dev_from_config_files(self, test_cli_runner, db_session):
        expected_workflows = [
            "Iivr.ingress",
            "Iivr.main_menu",
            "Iivr.secure_call",
            "Iivr.self_service_menu",
            "Iivr.make_payment",
            "Iivr.loan_origination",
            "Iivr.sms.make_payment_sms",
            "shared.ivr.noop_queue_transfer",
            "shared.ivr_telco_customer_lookup",
            "shared.ivr_customer_lookup",
            "Iivr.ivr.activate_card",
            "shared.ivr.banking_menu"
        ]

        expected_queues = [
            "AFC.LN.PAY.INT",
            "AFC.LN.PAY.EXT",
            "AFC.LN.PAY.AH",
            "AFC.LN.CUS",
            "AFC.LN.ORIG",
            "AFC.CC.CUS",
            "AFC.CC.ORIG",
            "AFC.CC.PAY.INT",
            "AFC.CC.PAY.EXT",
            "Iivr.unsecured.ANY",
            "Iivr.unsecured.PAY"
        ]

        test_cli_runner.invoke(
            Scaffold.setup_dev_from_config_files)

        assert db_session.query(InboundRouting).count() == 5
        assert db_session.query(TransferRouting).count() == 13
        assert db_session.query(QueueHoursOfOperation).count() == 80
        assert db_session.query(Queue).count() == len(expected_queues)
        assert db_session.query(Workflow).count() == len(expected_workflows)

    def test_reset_dev(self, test_cli_runner):
        result = test_cli_runner.invoke(
            Scaffold.delete_all_dev_data,
            input='Y\n'
        )
        assert "Deleting data" in result.output
        assert "Runs Cleared." in result.output
        assert "Data Cleared." in result.output

    def test_reset_dev_no_stops_command(self, test_cli_runner):
        result = test_cli_runner.invoke(
            Scaffold.delete_all_dev_data,
            input='N\n'
        )
        assert "Deleting data" not in result.output
        assert "Quitting due to lack of confirmation" in result.output

    def test_add_ani_shortcut(self, test_cli_runner, db_session, admin_service):
        phone_number = "14438342310"
        short_number = "123456"
        result = test_cli_runner.invoke(
            Scaffold.add_ani_shortcut,
            args=[
                "--phone_number", phone_number,
                "--short_number", short_number,
                "--name", "test number",
                "--customer", "customer"
            ]
        )

        assert f"Your shortcut for {short_number} to {phone_number} has been created." in result.output
        assert admin_service.find_shortcut_ani(short_number)

    def test_add_workflow(self, test_cli_runner, db_session):
        result = test_cli_runner.invoke(
            Scaffold.add_workflow,
            args=['--workflow-name', 'Iivr.ingress',
                  '--workflow-tag', '1.0.0',
                  '--partner', 'Iivr'])
        assert 'workflow_name=Iivr.ingress' in result.output
        workflow_service = WorkflowService(db_session)
        workflow = workflow_service.get_workflow_by_name('Iivr.ingress')

        assert workflow.active_config_tag == "1.0.0"

    def test_closed_message(self, test_cli_runner, db_session):
        test_cli_runner.invoke(
            Scaffold.setup_dev_from_config_files,
            args=['--queue-config-file', './commands/configs/queue_config.json'])

        assert db_session.query(Queue).filter(
            Queue.name == 'AFC.LN.PAY.INT').one_or_none().closed_message == '<break time="500ms"/> We are currently closed. Please try us back during our normal business hours of 7am-10pm central time. We apologize for this inconvenience and look forward to speaking with you then.'
        assert db_session.query(Queue).filter(
            Queue.name == 'AFC.LN.PAY.AH').one_or_none().closed_message == 'Sorry the call center is currently closed.'

    def test_update_greeting_message(self, test_cli_runner, db_session, greeting, Iivr_any_queue, workflow):
        inbound_target = '17738885555'
        new_message = "Updated greeting message"
        test_cli_runner.invoke(
            Scaffold.create_inbound_routing,
            args=['--contact-type', 'IVR',
                  '--inbound-target', inbound_target,
                  '--greeting-message', "Initial greeting message",
                  '--workflow-name', workflow.workflow_name,
                  '--is-active', f"{True}",
                  '--initial-queue-name', Iivr_any_queue.name]
        )
        result = test_cli_runner.invoke(
            Scaffold.update_greeting_message,
            args=['--greeting-message', new_message,
                  '--inbound-target', inbound_target]
        )

        assert f"Set greeting message for {inbound_target} to: {new_message}" in result.output
        assert db_session.query(Greeting).filter(Greeting.message == new_message).one_or_none()

        result = test_cli_runner.invoke(
            Scaffold.update_greeting_message,
            args=['--greeting-message', new_message, '--inbound-target', inbound_target])
        assert f"The greeting message for {inbound_target} is already set to: {new_message}" in result.output

    def test_update_greeting_message_from_config(self, test_cli_runner, db_session, greeting, Iivr_any_queue,
                                                 workflow):
        new_message = "Updated greeting message"
        inbound_config_file_path = f"{os.path.dirname(__file__)}/test_inbound_routing_config.json"
        update_config_file_path = f"{os.path.dirname(__file__)}/test_update_greeting_config.json"

        result_create = test_cli_runner.invoke(
            Scaffold.create_inbound_routings,
            args=['--config-file-path', inbound_config_file_path])
        assert "Inbound routing configs created." in result_create.output
        assert db_session.query(InboundRouting).filter(InboundRouting.inbound_target == "17732073682").first()
        assert db_session.query(InboundRouting).filter(InboundRouting.inbound_target == "17732073700").first()
        assert db_session.query(InboundRouting).filter(InboundRouting.inbound_target == "1234567890").first()
        result = test_cli_runner.invoke(
            Scaffold.update_greeting_message_from_config,
            args=['--config-file-path', update_config_file_path])

        assert "Greeting message configs updated." in result.output
        routing1 = db_session.query(InboundRouting).filter(InboundRouting.inbound_target == "17732073682").first()
        assert routing1.greeting.message == new_message
        routing2 = db_session.query(InboundRouting).filter(InboundRouting.inbound_target == "17732073700").first()
        assert routing2.greeting.message == new_message
        routing3 = db_session.query(InboundRouting).filter(InboundRouting.inbound_target == "1234567890").first()
        assert routing3.greeting.message == "Thank you for calling TD."

    def test_setup_graph_from_workflow(self, test_cli_runner, db_session, workflow):
        result_step_tree_graph = test_cli_runner.invoke(
            Scaffold.setup_graph_from_workflow,
            args=['--workflow-name', 'main_menu'])

        assert "Graph Created Successfully" in result_step_tree_graph.output

