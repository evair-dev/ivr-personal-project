import json
from typing import Dict

import click

from commands.base import DbCommandBase
from commands.workflow_registry import workflow_step_tree_registry

from ivr_gateway.models.contacts import TransferRouting
from ivr_gateway.models.enums import TransferType
from ivr_gateway.models.queues import Queue
from ivr_gateway.services.admin import AdminService
from ivr_gateway.services.queues import QueueService
from ivr_gateway.services.workflows import WorkflowService


class Update(DbCommandBase):

    @property
    def admin_service(self):
        return AdminService(self.db_session)

    @property
    def workflow_service(self):
        return WorkflowService(self.db_session)

    @property
    def queue_service(self):
        return QueueService(self.db_session)

    @click.command()
    @click.option("--workflow-name", prompt="What workflow would you like to update?  (e.g. Iivr.workflow_name)",
                  type=click.STRING)
    @click.option("--workflow-tag", prompt="What would you like to tag this workflow config?  (e.g. 1.0.0)",
                  type=click.STRING)
    @click.option("--active", prompt="Set active?", type=click.BOOL)
    def workflow_config(self, workflow_name, workflow_tag, active) -> None:

        step_tree = workflow_step_tree_registry.get(workflow_name)
        if step_tree is None:
            click.echo("Step tree for specified workflow does not exist")
            return

        workflow = self.workflow_service.get_workflow_by_name(workflow_name)
        if workflow is None:
            click.echo("Specified workflow does not exist")
            return

        self.workflow_service.create_config_for_workflow(workflow, step_tree, workflow_tag)
        if active:
            self.workflow_service.update_active_workflow_config(workflow, workflow_tag)

    @click.command()
    @click.option("--workflow-name", prompt="What workflow would you like to update?  (e.g. Iivr.workflow_name)",
                  type=click.STRING)
    @click.option("--workflow-tag", prompt="What would you like to tag this workflow config?  (e.g. v1.0.0)",
                  type=click.STRING)
    def active_workflow_config(self, workflow_name, workflow_tag) -> None:

        workflow = self.workflow_service.get_workflow_by_name(workflow_name)
        if workflow is None:
            click.echo("Specified workflow does not exist")
            return

        self.workflow_service.update_active_workflow_config(workflow, workflow_tag)
        click.echo(f"{workflow_tag} is now the active version of {workflow_name}")

    @click.command()
    @click.option("--queue-config-file", prompt="Config file to use?")
    def transfer_routings_from_config_file(self, queue_config_file) -> None:
        with open(queue_config_file) as config_file:
            queues = json.load(config_file)
        for queue_dict in queues:
            queue = self.update_queue_transfer_routings(queue_dict)
            click.echo(f"Updated queue: {queue}")

    def update_queue_transfer_routings(self, queue_dict: Dict) -> Queue:

        queue = self.queue_service.get_queue_by_name(queue_dict.get("name"))
        if queue is None:
            raise Exception("Queue doesn't exist")

        current_routings = queue.transfer_routings
        current_routings_set = set(current_routings)
        for transfer_routing_dict in queue_dict.get("transfer_routings"):
            type = transfer_routing_dict.get("type")
            priority = transfer_routing_dict.get("priority")
            weight = transfer_routing_dict.get("weight", 0)
            destination = None
            system = None
            transfer_type = None
            if type == "pstn":
                destination = transfer_routing_dict.get("pstn_number")
                system = transfer_routing_dict.get("phone_system")
                transfer_type = TransferType.PSTN
            elif type == "flex":
                destination = transfer_routing_dict.get("workflow_sid")
                system = "twilio"
                transfer_type = TransferType.INTERNAL
            elif type == "queue":
                destination = transfer_routing_dict.get("queue_name")
                system = "ivr-gateway"
                transfer_type = TransferType.QUEUE
            existing_routing = None
            for routing in current_routings_set:
                if routing.destination == destination and routing.destination_system == system and routing.transfer_type == transfer_type:
                    existing_routing = routing
            if existing_routing:
                existing_routing.priority = priority
                existing_routing.weight = weight
                current_routings_set.remove(existing_routing)
            else:
                new_routing = TransferRouting(
                    transfer_type=transfer_type,
                    destination=destination,
                    destination_system=system,
                    operating_mode="normal",
                    queue=queue,
                    priority=priority,
                    weight=weight
                )
                self.db_session.add(new_routing)

        for routing in current_routings_set:
            routing.priority = -1

        self.db_session.commit()

        return queue
