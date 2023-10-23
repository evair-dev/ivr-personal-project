from typing import Optional, List

from sqlalchemy import orm, or_

from ivr_gateway.models.contacts import ContactLeg
from ivr_gateway.models.enums import Partner
from ivr_gateway.models.steps import StepState, StepRun
from ivr_gateway.models.workflows import WorkflowRun, Workflow, WorkflowConfig, WorkflowStepRun
from ivr_gateway.services.workflows.exceptions import CreateStepForWorkflowException, MissingWorkflowConfigException, \
    InvalidWorkflowConfigTagException
from ivr_gateway.services.workflows.utils import get_step_template_from_workflow, get_step_branch_from_workflow
from ivr_gateway.steps.base import Step, NextStepOrExit
from ivr_gateway.steps.config import StepTree
from ivr_gateway.steps.exceptions import StepInitializationException
from ivr_gateway.utils import dynamic_class_loader, without


class WorkflowService:

    def __init__(self, db_session: orm.Session):
        self.session = db_session

    def get_workflows(self) -> Optional[List[Workflow]]:
        return (self.session.query(Workflow)
                .all())

    def get_workflow_for_id(self, workflow_id: str) -> Workflow:
        return (self.session.query(Workflow)
                .filter(Workflow.id == workflow_id)
                .one_or_none())

    def get_workflow_by_name(self, workflow_name: str) -> Workflow:
        return (self.session.query(Workflow)
                .filter(Workflow.workflow_name == workflow_name)
                .one_or_none())

    def get_workflow_run_by_id(self, workflow_id: str) -> Optional[Workflow]:
        return (self.session.query(WorkflowRun)
                .filter(WorkflowRun.id == workflow_id)
                .one_or_none())

    def get_workflow_steps_by_workflow_run_id(self, workflow_run_id: str):
        return (self.session
                .query(WorkflowRun.id, ContactLeg.ani, Workflow.workflow_name, StepRun.branch,
                       StepRun.name, StepState.id, StepState.input, StepState.result)
                .outerjoin(ContactLeg, ContactLeg.workflow_run_id == WorkflowRun.id)
                .outerjoin(WorkflowStepRun, WorkflowStepRun.workflow_run_id == WorkflowRun.id)
                .outerjoin(StepRun, StepRun.id == WorkflowStepRun.step_run_id)
                .outerjoin(StepState, StepState.step_run_id == StepRun.id)
                .outerjoin(Workflow, Workflow.id == WorkflowRun.workflow_id)
                .filter(WorkflowRun.id == workflow_run_id)
                .group_by(WorkflowRun.id, ContactLeg.ani, Workflow.workflow_name, StepRun.branch, StepRun.name,
                          StepState.id, StepState.input, StepState.result, WorkflowRun.created_at, StepRun.created_at)
                .order_by(WorkflowRun.created_at.desc(), StepRun.created_at.asc())
                .all())

    def get_contact_legs_by_phone_number(self, phone_number: str) -> List[Optional[ContactLeg]]:
        return (self.session.query(ContactLeg)
                .filter(ContactLeg.ani == phone_number)
                .order_by(ContactLeg.created_at.asc())
                .all())

    def get_contact_legs_by_contact_id(self, contact_id: str) -> List[Optional[ContactLeg]]:
        return (self.session.query(ContactLeg)
                .filter(ContactLeg.contact_id == contact_id)
                .order_by(ContactLeg.created_at.asc())
                .all())

    def create_workflow(self, name: str, step_tree: StepTree = None,
                        partner=Partner.IVR, tag: str = None) -> Workflow:
        workflow = Workflow()
        workflow.workflow_name = name
        workflow.partner = partner
        workflow_config = WorkflowConfig(step_tree=step_tree, tag=tag)

        self.session.add(workflow_config)
        workflow.configs = [workflow_config]

        self.session.add(workflow)
        self.session.flush()
        # Ensure we create the workflow w/ an active tag
        workflow.active_config_tag = tag or workflow_config.step_tree_sha
        self.session.add(workflow)
        self.session.commit()
        return workflow

    def create_config_for_workflow(self, workflow: Workflow, step_tree: StepTree, tag: str) -> WorkflowConfig:
        # Check that a workflow config doesn't already exist with this tag
        if tag is not None:
            config = self.get_config_for_sha_or_tag(workflow, tag)
            if config is not None:
                raise InvalidWorkflowConfigTagException()
        workflow_config = WorkflowConfig(step_tree=step_tree, tag=tag, workflow=workflow)
        self.session.add(workflow_config)
        self.session.commit()
        return workflow_config

    def update_active_workflow_config(self, workflow: Workflow, sha_or_tag: str):
        config = self.get_config_for_sha_or_tag(workflow, sha_or_tag)
        if config is None:
            raise MissingWorkflowConfigException()
        workflow.active_config_tag = sha_or_tag
        self.session.add(workflow)
        self.session.commit()

    def get_config_for_sha_or_tag(self, workflow: Workflow, sha_or_tag: str) -> Optional[WorkflowConfig]:
        return (self.session.query(WorkflowConfig)
                .filter(WorkflowConfig.workflow_id == workflow.id)
                .filter(or_(WorkflowConfig.tag == sha_or_tag, WorkflowConfig.step_tree_sha == sha_or_tag))
                .first())

    def get_config_for_workflow(self, workflow: Workflow) -> Optional[WorkflowConfig]:
        return (self.session.query(WorkflowConfig)
                .filter(WorkflowConfig.workflow_id == workflow.id)
                .first())

    def process_step_result(self, workflow_run: "WorkflowRun") -> NextStepOrExit:
        """
        Used to handle the response of a workflow run when the step has been successfully executed and we need to
        construct the next step or exit path depending

        :param workflow_run:
        :return:
        """
        current_step_run = workflow_run.get_current_step_run()
        # Using the current step run because we might have branched
        step_template = get_step_template_from_workflow(workflow_run, current_step_run.name,
                                                        branch_name=current_step_run.branch)

        if step_template.exit_path is not None:
            # If we have an exit path, then we need to map this out using the dynamic class loader
            exit_path_config = step_template.exit_path
            exit_path_type = exit_path_config["exit_path_type"]
            exit_path_kwargs = exit_path_config.get("exit_path_kwargs", {})
            exit_path_class = dynamic_class_loader(exit_path_type)
            exit_path = exit_path_class(**exit_path_kwargs)
            return exit_path

        # Otherwise we will create a step dynamically using the last step run as an anchor to find the next
        # Step template for the current step branch (we may have no runs if we are initializing or have just swapped
        # branches)
        current_branch_name = workflow_run.current_step_branch_name
        step_branch = get_step_branch_from_workflow(workflow_run, current_branch_name)
        # last_step_run: StepRun = (self.session.query(StepRun)
        #                           .join(WorkflowStepRun)
        #                           .filter(WorkflowStepRun.workflow_run_id == workflow_run.id,
        #                                   StepRun.branch == workflow_run.current_step_branch_name
        #                                   )
        #                           .order_by(WorkflowStepRun.run_order.desc())
        #                           .first())

        # get the last step that's already been run on the new branch
        last_step_run = workflow_run.get_last_step_run_on_branch(workflow_run.current_step_branch_name)
        # if we're switching to a branch where restart = True, act as though we haven't run any steps on that branch
        if current_step_run.branch != step_branch.name and step_branch.reset_on_switch:
            last_step_run = None

        # Initialize our index at 0, if we do not have preexisting step runs on this branch then we will start
        # at the first step
        next_step_on_branch_index = 0
        if last_step_run is not None:
            for idx, st in enumerate(step_branch.steps):
                # if the last_step_run is this step, then we store it's index + 1, and use that to access the branch
                # step list
                if st.name == last_step_run.name:
                    next_step_on_branch_index = idx + 1
                    break
        next_step_config = step_branch.steps[next_step_on_branch_index]
        step = self.create_step_for_workflow(
            workflow_run, next_step_config.name, current_branch_name
        )
        return step

    def create_step_for_workflow(self, workflow_run: WorkflowRun,
                                 step_name: str, branch_name=None) -> Step:
        """
        Will instantiate a step object using a workflow_run and step name.

        TODO: Need to add in concept of immutable state records, right now we only write to the current state object
        :param workflow_run:
        :param step_name:
        :param branch_name:
        :param step_state_index:
        :return:
        """
        step_template = get_step_template_from_workflow(workflow_run, step_name, branch_name=branch_name)
        step_type = step_template.step_type
        step_kwargs = step_template.step_kwargs
        if "NumberedInputActionStep" in step_type:
            step_actions = step_template.get_numbered_actions_if_exists()
        else:
            step_actions = step_template.get_actions_if_exists()
        # Check if the arguments attached were dict rather than
        if len(step_actions) > 0:
            step_kwargs["actions"] = step_actions
        # Create the class so that we can now update our record/state
        step_cls = dynamic_class_loader(step_type)
        try:
            step = step_cls(step_name, **without(step_kwargs, "name"))
        except StepInitializationException as e:
            raise CreateStepForWorkflowException(
                f"Error Creating step {step_name} for branch {branch_name}. Error: {e}"
            )

        return step
