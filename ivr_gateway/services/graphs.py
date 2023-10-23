import random
from typing import List

import graphviz

from ivr_gateway.models.workflows import Workflow, WorkflowConfig
from ivr_gateway.steps.config import Step


class StepTreeGraph:
    def __init__(self, workflow: Workflow, workflow_config: WorkflowConfig):
        self.workflow = workflow
        self.workflow_name = workflow.workflow_name
        self.workflow_config = workflow_config
        self.workflow_branches = workflow_config.branches
        self.dot = graphviz.Digraph('workflow', comment='Workflow Graph', filename=self.workflow_name)

    def node_exists(self, node: str) -> bool:
        existing_nodes = self.dot.body
        for node_name in existing_nodes:
            if node in node_name:
                return True

        return False

    def create_graph(self):
        for branch in self.workflow_branches:
            branch_name = branch.name
            steps = branch.steps
            color = "#" + "%06x" % random.randint(0, 0xFFFFFF)  # nosec

            self.dot.node(branch_name, shape='rectangle', color=color)
            self.create_nodes_for_step(branch_name, steps, color)

    def create_node(self, new_node: str, color: str, shape: str = 'oval', style:str = 'solid', previous_node: str = None):

        # only create a new node if one doesn't already exist
        if not self.node_exists(new_node):
            self.dot.node(new_node, shape=shape, color=color)

        # create an edge between new node and previous node
        if previous_node:
            self.dot.edge(previous_node, new_node, style=style, color=color)

    def create_nodes_for_branch_step(self, branch_step: Step, color: str):
        step_name = branch_step.name
        step_kwargs = branch_step.step_kwargs
        branch_destinations = list(branch_step.step_kwargs['branches'].values())

        if "default_branch" in step_kwargs:
            default_branch = step_kwargs["default_branch"]
            branch_destinations.append(default_branch)

        branch_destinations = list(set(branch_destinations))

        for branch in branch_destinations:
            self.create_node(branch, color, 'rectangle', previous_node=step_name)

    def create_nodes_for_step(self, branch_name: str, steps: List[Step], color: str):
        previous_node = branch_name

        for step in steps:
            step_kwargs = step.step_kwargs

            if self.node_exists(step.name):
                step.name = f"{branch_name}.{step.name}"

            self.create_node(step.name, color=color, previous_node=previous_node)

            # check for error branches and steps
            if 'on_error_reset_to_step' in step_kwargs:
                error_step = step_kwargs['on_error_reset_to_step']
                self.create_node(error_step, color='red', style="dashed", previous_node=step.name)

            if 'on_error_switch_to_branch' in step_kwargs:
                error_branch = step_kwargs['on_error_switch_to_branch']
                self.create_node(error_branch, color='red', style="dashed", shape='rectangle', previous_node=step.name)

            if step.step_type == "ivr_gateway.steps.api.v1.BranchMapWorkflowStep":
                self.create_nodes_for_branch_step(step, color=color)

            previous_node = step.name

        self.save_graph()

    def save_graph(self):
        self.dot.render(directory='graphs').replace('\\', '/')
