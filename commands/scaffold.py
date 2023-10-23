import json
import os
from typing import Optional, Dict

import click
import sys

from commands import Db
from commands.base import DbCommandBase
from ivr_gateway.exceptions import InvalidRoutingConfigException
from ivr_gateway.api.exceptions import MissingInboundRoutingException

from ivr_gateway.models.admin import AdminCallFrom, AdminCallTo
from ivr_gateway.models.contacts import InboundRouting, Greeting, TransferRouting
from ivr_gateway.models.enums import TransferType, Partner, ContactType
from ivr_gateway.models.queues import Queue
from ivr_gateway.models.workflows import Workflow
from ivr_gateway.services.admin import AdminService
from ivr_gateway.services.calls import CallService
from ivr_gateway.services.operating_times import HolidayHoursService
from ivr_gateway.services.queues import QueueService
from ivr_gateway.services.workflows import WorkflowService
from ivr_gateway.services.graphs import StepTreeGraph

from commands.workflow_registry import workflow_step_tree_registry


class Scaffold(DbCommandBase):

    @property
    def admin_service(self):
        return AdminService(self.db_session)

    @property
    def workflow_service(self):
        return WorkflowService(self.db_session)

    @click.command()
    @click.option("--confirm", prompt="Are you sure you want to clear out the database?", type=click.BOOL)
    @click.pass_context
    def delete_all_dev_data(context, self, confirm) -> None:
        if os.getenv("IVR_APP_ENV") not in ["local", "dev", "uat", "test"]:
            click.echo("Exiting because command cannot be run in production mode")
            sys.exit(1)
        # Test for reset
        if not confirm:
            click.echo("Quitting due to lack of confirmation")
            sys.exit(1)
        else:
            click.echo("Deleting data")

        context.invoke(Db.clear_workflow_runs)
        context.invoke(Db.clear_call_inbound_transfer_and_admin_data)
        context.invoke(Db.clear_queues)

    @click.command()
    @click.option("--config-file-path", prompt="Path to holiday queue hour config file?", type=click.STRING)
    def create_holiday_hours(self, config_file_path):
        """
        :param config_file_path: "/path/to/config.json"
                Example Config File:
                    [
                      {
                        "name": "TestHoliday1",
                        "date": "2021-05-27",
                        "queue_configs": [
                          {
                            "queues": [
                              "AFC.LN.CUS"
                            ],
                            "message": "It is the 27th of May 2021 and we are closed after 2PM.",
                            "start_time": "09:00",
                            "end_time": "14:00"
                          },
                          {
                            "queues": [
                              "AFC.LN.ORIG"
                            ],
                            "message": "It is the 27th of May 2021 originations is closed all day."
                          }
                        ]
                      },
                      {
                        "name": "TestHoliday2",
                        "date": "2021-05-28",
                        "queue_configs": [
                          {
                            "queues": [
                              "AFC.LN.CUS"
                            ],
                            "message": "It is the 27th of May 2021 and we are closed after 2PM.",
                            "start_time": "09:00",
                            "end_time": "14:00"
                          },
                          {
                            "queues": [
                              "AFC.LN.ORIG"
                            ],
                            "message": "It is the 27th of May 2021 originations is closed all day."
                          }
                        ]
                      }
                    ]

        :return:
        """
        with open(config_file_path) as config_file:
            holiday_queue_configs = json.load(config_file)
        holiday_hours_service = HolidayHoursService(self.db_session)
        for holiday_queue_config in holiday_queue_configs:
            click.echo(f"Creating holiday hours for {holiday_queue_config.get('name')}")
            holiday_hours_service.create_holiday_hours_from_config(holiday_queue_config)
            click.echo(f"Holiday hours for {holiday_queue_config.get('name')} created")
        click.echo("All holiday hours successfully created.")

    @click.command()
    @click.option("--config-file-path", prompt="Path to the config file?", type=click.STRING)
    @click.option("--upsert", prompt="Overwrite existing inbound routings? (set all existing routings that match the "
                                     "inbound target to inactive)", is_flag=True)
    def create_inbound_routings(self, config_file_path, upsert):
        # TODO add ability to upsert routings; make sure to set existing routing "active=False"
        with open(config_file_path) as config_file:
            call_routing_configs = json.load(config_file)

        route_configs = [call_routing_config["routes"] for call_routing_config in call_routing_configs]
        inbound_targets = [route["inbound_target"] for route_config in route_configs for route in route_config]
        call_service = CallService(self.db_session)
        existing_inbound_routings = [inbound_routing for inbound_routing in
                                     call_service.get_routings_for_numbers_in_list(inbound_targets)]
        existing_inbound_routings_numbers = [routing.inbound_target for routing in existing_inbound_routings]
        if len(existing_inbound_routings) > 0:
            click.echo(
                f"There are inbound routings that exist for the following numbers: {existing_inbound_routings_numbers}")
            click.echo("You can add the '--upsert' flag to update these existing inbound routings.")
            if upsert:
                call_service.set_active_routings_inactive(existing_inbound_routings)
            else:
                return

        for call_routing_config in call_routing_configs:
            click.echo(f"Creating inbound routing config for: {call_routing_config}")
            for route in call_routing_config["routes"]:
                try:
                    self.create_inbound_routing_with_params(
                        contact_type=route.get('contact_type'),
                        inbound_target=route.get('inbound_target'),
                        greeting_message=call_routing_config.get('greeting_message'),
                        workflow_name=call_routing_config.get('workflow_name'),
                        active=route.get('active', True),
                        admin=route.get('admin', False),
                        queue_name=route.get('queue_name')
                    )
                except KeyError as key_error:
                    click.echo("Invalid Key Error")
                    click.echo(key_error)
                except InvalidRoutingConfigException as invalid_config_error:
                    click.echo("Invalid Config Error")
                    click.echo(invalid_config_error)

        click.echo("Inbound routing configs created.")

    @click.command()
    @click.option("--contact-type", prompt="What is the contact type associated with the inbound routing?",
                  type=click.Choice(['IVR', 'SMS', 'CHAT'], case_sensitive=False))
    @click.option("--inbound-target", prompt="What is the target associated with the inbound routing?",
                  type=click.STRING)
    @click.option("--greeting-message", prompt="Enter the greeting message to associate with the inbound routing.",
                  type=click.STRING)
    @click.option("--workflow-name",
                  prompt="Enter a workflow name to associate with the inbound routing (press enter if none).",
                  default="", type=click.STRING)
    @click.option("--is-active", prompt="Should this inbound routing be set as active?", type=click.BOOL, default=True)
    @click.option("--is-admin", prompt="Is this an admin inbound routing?", type=click.BOOL, default=False)
    @click.option("--initial-queue-name", prompt="Enter the name of the initial queue (if none, press enter).",
                  default="")
    @click.option("--upsert", prompt="Overwrite existing inbound routing? (set any existing routing that match the "
                                     "inbound target to inactive)", is_flag=True)
    def create_inbound_routing(self, contact_type: str, inbound_target: str, greeting_message: str,
                               workflow_name: str = None, is_active=True, is_admin=False,
                               initial_queue_name: str = None, upsert: bool = False) -> None:
        call_service = CallService(self.db_session)
        existing_inbound_routings = call_service.get_routings_for_number(inbound_target)
        if len(existing_inbound_routings) > 0:
            click.echo(f"An inbound routing already exists for {inbound_target}.")
            click.echo("You can add the '--upsert' flag to update this existing inbound routing.")
            if upsert:
                call_service.set_active_routings_inactive(existing_inbound_routings)
            else:
                return

        click.echo("Setting up inbound routing.")
        self.create_inbound_routing_with_params(contact_type, inbound_target, greeting_message, workflow_name,
                                                is_active, is_admin, initial_queue_name)
        click.echo("Inbound routing setup successfully.")

    @click.command()
    @click.option("--main-menu-phone-number", prompt="What is your main menu phone number?  (e.g. 14432351191)",
                  type=click.STRING)
    @click.option("--admin-routing-phone-number", prompt="What is your admin routing phone number?  (e.g. 14432351191)",
                  type=click.STRING)
    @click.option("--queue-config-file", default="./commands/configs/queue_config.json")
    def setup_dev(self, main_menu_phone_number, admin_routing_phone_number, queue_config_file) -> None:
        workflows_in_database = self.db_session.query(Workflow).count() > 0
        if workflows_in_database:
            click.echo("There was an error with your request.")
            click.echo(
                "Please clear the database of workflow runs and call configuration using the flask scaffold delete-all-dev-data command before running setup-dev.")
            sys.exit(2)

        with open(queue_config_file) as config_file:
            initial_queues = json.load(config_file)
        for queue_dict in initial_queues:
            self.configure_queue(queue_dict)

        click.echo("Initial queues and their routings are set up.")

        workflows_dict: Dict[str, Workflow] = {}
        # TODO: We should probably version these step trees once we get stable and allow loading
        # from a configured filepath including version
        for workflow_name in workflow_step_tree_registry:
            workflows_dict[workflow_name] = self.workflow_service.create_workflow(
                workflow_name,
                step_tree=workflow_step_tree_registry[workflow_name], tag="1.0.0"
            )

        greeting = self._create_Iivr_greeting()
        self.add_inbound_routing(
            contact_type=ContactType.IVR,
            inbound_target=main_menu_phone_number,
            workflow=workflows_dict["Iivr.ingress"],
            greeting=greeting
        )
        # self.add_call_routing(main_menu_phone_number, None, greeting)
        click.echo("Inbound routings set up.")

        admin_greeting = Greeting(message="This number is for authorized personal only")
        self.db_session.add(admin_greeting)

        self.add_inbound_routing(
            contact_type=ContactType.IVR,
            inbound_target=admin_routing_phone_number,
            workflow=None,
            greeting=admin_greeting,
            admin=True
        )

        self.add_dnis_shortcut("9", main_menu_phone_number)

        click.echo("Admin inbound routings set up.")

    @click.command()
    @click.option("--call-routing-config-file", default="./commands/configs/inbound_routing_config.json")
    @click.option("--queue-config-file", default="./commands/configs/queue_config.json")
    def setup_dev_from_config_files(self, call_routing_config_file, queue_config_file) -> None:
        workflows_in_database = self.db_session.query(Workflow).count() > 0
        if workflows_in_database:
            click.echo("There was an error with your request.")
            click.echo(
                "Please clear the database of workflow runs and call configuration using the flask scaffold "
                "delete-all-dev-data command before running setup-dev.")
            sys.exit(2)

        queues = {}

        with open(queue_config_file) as config_file:
            initial_queues = json.load(config_file)
        for queue_dict in initial_queues:
            queue = self.configure_queue(queue_dict)
            queues[queue.name] = queue

        click.echo("Initial queues and their routings are set up.")
        workflows_dict: Dict[str, Workflow] = {}

        for workflow_name in workflow_step_tree_registry:
            workflows_dict[workflow_name] = self.workflow_service.create_workflow(
                workflow_name,
                step_tree=workflow_step_tree_registry[workflow_name], tag="1.0.0"
            )

        with open(call_routing_config_file) as config_file:
            initial_call_routes = json.load(config_file)

        for call_routing_config in initial_call_routes:
            click.echo(f"Creating inbound routing config for: {call_routing_config}")
            for route in call_routing_config["routes"]:
                self.create_inbound_routing_with_params(
                    contact_type=route.get('contact_type'),
                    inbound_target=route.get('inbound_target'),
                    greeting_message=call_routing_config.get('greeting_message'),
                    workflow_name=call_routing_config.get('workflow_name'),
                    active=route.get('active', True),
                    admin=route.get('admin', False),
                    queue_name=route.get('queue_name')
                )

                short_number = route.get("short_number")
                if short_number is not None:
                    self.add_dnis_shortcut(short_number, route.get('inbound_target'))

        click.echo("setup finished")

    @click.command()
    @click.option("--workflow-name", prompt="Name of the workflow to turn into a graph", type=click.STRING)
    def setup_graph_from_workflow(self, workflow_name: str) -> None:
        workflow_service = WorkflowService(self.db_session)
        workflows = workflow_service.get_workflows()
        workflow_names = [workflow.workflow_name for workflow in workflows]

        if workflow_name in workflow_names:
            workflow = workflow_service.get_workflow_by_name(workflow_name)
            workflow_config = workflow_service.get_config_for_workflow(workflow)
            step_tree_graph = StepTreeGraph(workflow, workflow_config)
            step_tree_graph.create_graph()
            click.echo("Graph Created Successfully")
        else:
            click.echo("Invalid Workflow Name")

    def configure_queue(self, queue_dict: Dict) -> Queue:
        queue = Queue(name=queue_dict["name"], active=True, partner=Partner(queue_dict["partner"]),
                      past_due_cents_amount=queue_dict.get("past_due_cents_amount", 0),
                      closed_message=queue_dict.get("closed_message", None))
        self.db_session.add(queue)
        self.db_session.commit()

        if "hours_of_operation" in queue_dict:
            hours_of_op_arr = queue_dict["hours_of_operation"]
            for day_num in range(7):
                for hours_of_op_dict in hours_of_op_arr[day_num]:
                    self.add_hours_of_operation_to_queue(queue, day_num, hours_of_op_dict)

        for transfer_routing_dict in queue_dict.get("transfer_routings"):
            type = transfer_routing_dict.get("type")
            priority = transfer_routing_dict.get("priority")
            if type == "pstn":
                number = transfer_routing_dict.get("pstn_number")
                system = transfer_routing_dict.get("phone_system")
                self.add_pstn_routing(queue, priority, number, system)
            elif type == "flex":
                task_sid = transfer_routing_dict.get("workflow_sid")
                self.add_flex_routing(queue, priority, task_sid)
            elif type == "queue":
                queue_name = transfer_routing_dict.get("queue_name")
                self.add_queue_transfer_routing(queue, priority, queue_name)

        return queue

    def add_hours_of_operation_to_queue(self, queue, day, hours_of_operation_dict):
        queue_service = QueueService(self.db_session)
        queue_service.add_hours_of_operations_for_day(
            queue,
            day,
            hours_of_operation_dict["start"],
            hours_of_operation_dict["end"]
        )

    def create_inbound_routing_with_params(self, contact_type: str = None, inbound_target: str = None,
                                           greeting_message: str = None, workflow_name: str = None, active=True,
                                           admin=False, queue_name: str = None):
        call_service = CallService(self.db_session)
        greeting = call_service.create_greeting_if_not_exists(greeting_message)

        queue = None
        if queue_name:
            queue_service = QueueService(self.db_session)
            queue = queue_service.get_queue_by_name(queue_name)
            if queue is None:
                raise InvalidRoutingConfigException("invalid queue name")
            if workflow_name is None:
                raise InvalidRoutingConfigException("admin mismatch")

        workflow = None
        if workflow_name:
            workflow_service = WorkflowService(self.db_session)
            workflow = workflow_service.get_workflow_by_name(workflow_name)
            if workflow is None:
                raise InvalidRoutingConfigException("invalid workflow name")

            if workflow.partner is not None and queue is not None:
                if workflow.partner != queue.partner:
                    raise InvalidRoutingConfigException("queue and workflow partner mismatch")

        self.add_inbound_routing(
            contact_type=ContactType[contact_type],
            inbound_target=inbound_target,
            workflow=workflow,
            greeting=greeting,
            active=active,
            admin=admin,
            initial_queue=queue
        )

    def add_inbound_routing(self, contact_type: ContactType, inbound_target: str, workflow: Optional[Workflow],
                            greeting: Greeting, active: bool = True, admin: bool = False,
                            initial_queue: Queue = None) -> InboundRouting:
        call_routing = InboundRouting(
            contact_type=contact_type,
            inbound_target=inbound_target,
            workflow=workflow,
            active=active,
            admin=admin,
            greeting=greeting,
            operating_mode="normal",
            initial_queue=initial_queue
        )
        self.db_session.add(call_routing)
        self.db_session.commit()
        return call_routing

    def add_pstn_routing(self, queue: Queue, priority: int, phone_number: str, phone_system: str) -> TransferRouting:
        return self.add_transfer_routing(queue, priority, TransferType.PSTN, phone_number, phone_system)

    def add_sip_routing(self, queue: Queue, priority: int, sip_address: str, phone_system: str) -> TransferRouting:
        return self.add_transfer_routing(queue, priority, TransferType.SIP, sip_address, phone_system)

    def add_flex_routing(self, queue: Queue, priority: int, task_sid: str) -> TransferRouting:
        return self.add_transfer_routing(queue, priority, TransferType.INTERNAL, task_sid, "twilio")

    def add_queue_transfer_routing(self, queue: Queue, priority: int, destination_queue_name: str):
        return self.add_transfer_routing(queue, priority, TransferType.QUEUE, destination_queue_name, "ivr-gateway")

    def add_transfer_routing(self, queue: Queue, priority: int, transfer_type: str, destination: str,
                             system: str) -> TransferRouting:
        transfer_routing = TransferRouting(
            transfer_type=transfer_type,
            destination=destination,
            destination_system=system,
            operating_mode="normal",
            queue=queue,
            priority=priority
        )

        self.db_session.add(transfer_routing)
        self.db_session.commit()
        return transfer_routing

    def add_ani_shortcut_to_db(self, phone_number: str, shortcut_number: str, name: str = None,
                               customer: str = None) -> AdminCallFrom:
        admin_call_from = AdminCallFrom(
            full_number=phone_number,
            short_number=shortcut_number,
            name=name,
            customer=customer
        )
        self.db_session.add(admin_call_from)
        self.db_session.commit()
        return admin_call_from

    def add_dnis_shortcut(self, short_number: str, full_number: str) -> AdminCallTo:
        admin_call_from_lookup = self.admin_service.find_shortcut_dnis(short_number)
        if admin_call_from_lookup is not None:
            return
        dnis_shortcut = AdminCallTo(
            short_number=short_number,
            full_number=full_number
        )
        self.db_session.add(dnis_shortcut)
        self.db_session.commit()
        return dnis_shortcut

    def _create_Iivr_greeting(self):
        message = 'Thank you for calling <phoneme alphabet="ipa" ph="əˈvɑnt">Avant</phoneme>. ' \
                  'Please be advised that your call will be monitored or recorded for quality and training purposes.'
        call_service = CallService(self.db_session)
        return call_service.create_greeting_if_not_exists(message)

    @click.command()
    @click.option('--phone_number', prompt="Enter phone number (e.g. 14432351191)")
    @click.option('--short_number', prompt="Short number the phone number should map to")
    @click.option('--name', prompt="Name of phone number")
    @click.option('--customer', prompt="Customer name or id")
    def add_ani_shortcut(self, phone_number, short_number, name, customer) -> None:
        """
        flask admin add-phone-number
        :param phone_number:
        :param short_id:
        :param name:
        :param customer:
        :return:
        """
        """Creates an admin phone number"""
        admin_call_from_lookup = self.admin_service.find_shortcut_ani(short_number)
        if admin_call_from_lookup is not None:
            click.echo(
                f"Short id {admin_call_from_lookup.short_number} is already used for {admin_call_from_lookup.full_number}")
            return
        admin_call_from = self.add_ani_shortcut_to_db(phone_number, short_number, name=name,
                                                      customer=customer)
        click.echo(
            f"Your shortcut for {admin_call_from.short_number} to {admin_call_from.full_number} has been created.")

    @click.command()
    @click.option("--workflow-name", prompt="What workflow would you like to update?  (e.g. Iivr.workflow_name)",
                  type=click.STRING)
    @click.option("--workflow-tag", prompt="What would you like to tag this workflow config?  (e.g. 1.0.0)",
                  type=click.STRING)
    @click.option("--partner", type=click.STRING)
    def add_workflow(self, workflow_name, workflow_tag, partner) -> None:
        step_tree = workflow_step_tree_registry.get(workflow_name)
        if step_tree is None:
            click.echo("Step tree for specified workflow does not exist")
            return

        workflow = self.workflow_service.get_workflow_by_name(workflow_name)
        if workflow is not None:
            click.echo("Specified workflow already exists")
            return

        workflow = self.workflow_service.create_workflow(workflow_name, step_tree, tag=workflow_tag, partner=partner)
        click.echo(f"Added {workflow}")

    @click.command()
    @click.option("--queue-config-file", prompt="Config file to use?")
    def setup_queues_from_config_file(self, queue_config_file) -> None:
        with open(queue_config_file) as config_file:
            queues = json.load(config_file)
        for queue_dict in queues:
            queue = self.configure_queue(queue_dict)
            click.echo(f"Added queue: {queue}")

    @click.command()
    @click.option("--greeting-message", prompt="Enter the greeting message to associate with the inbound routing.",
                  type=click.STRING)
    @click.option("--inbound-target", prompt="What is the target associated with the inbound routing?",
                  type=click.STRING)
    def update_greeting_message(self, greeting_message: str, inbound_target: str):
        call_service = CallService(self.db_session)
        routing = call_service.get_routing_for_number(inbound_target)
        if not routing:
            raise MissingInboundRoutingException(f"Resource not found for inbound-target: {inbound_target}")
        current_greeting = routing.greeting
        if current_greeting.message != greeting_message:
            new_greeting = call_service.create_greeting_if_not_exists(greeting_message)
            routing.greeting = new_greeting
            self.db_session.add(routing)
            self.db_session.commit()
            click.echo(f"Set greeting message for {inbound_target} to: {greeting_message}")
        else:
            click.echo(f"The greeting message for {inbound_target} is already set to: {greeting_message}")

    @click.command()
    @click.option("--config-file-path", prompt="Path to the updated message config file?", type=click.STRING)
    def update_greeting_message_from_config(self, config_file_path: str):
        call_service = CallService(self.db_session)
        with open(config_file_path) as config_file:
            message_updates = json.load(config_file)

        for message_update in message_updates:
            greeting_message = message_update.get("greeting_message", None)
            new_greeting = call_service.create_greeting_if_not_exists(greeting_message)
            if not greeting_message:
                click.echo(f"No greeting message found in config file at {config_file_path}")
                return
            routes = message_update.get("routes", [])
            for inbound_target in routes:
                routing = call_service.get_routing_for_number(inbound_target)
                if not routing:
                    raise MissingInboundRoutingException(f"Resource not found for inbound-target: {inbound_target}")
                routing.greeting = new_greeting
                self.db_session.add(routing)
                self.db_session.commit()
        click.echo("Greeting message configs updated.")
