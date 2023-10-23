import hashlib
import uuid
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING, Dict

from sqlalchemy import Integer, types, event, UniqueConstraint, or_, Enum
from sqlalchemy.dialects.postgresql.base import UUID
from sqlalchemy.dialects.postgresql.json import JSONB
from sqlalchemy.orm import relationship, object_session, Query
from sqlalchemy.sql.schema import Column, ForeignKey
from sqlalchemy.sql.sqltypes import String, DateTime
from sqlalchemy.sql.type_api import TypeEngine
from sqlalchemy_fsm import FSMField, transition
from sqlalchemy_utils.types.encrypted.encrypted_type import StringEncryptedType, AesEngine

from ivr_gateway.exceptions import NonUpdateableModelError
from ivr_gateway.logger import ivr_logger
from ivr_gateway.models import Base
from ivr_gateway.models.encryption import EncryptableJSONB, encryption_key, EncryptionFingerprintedMixin
from ivr_gateway.models.enums import WorkflowState
from ivr_gateway.models.exceptions import UninitializedWorkflowActionException
from ivr_gateway.models.steps import StepState, StepRun
from ivr_gateway.serde.steps.config import StepTreeSchema
from ivr_gateway.steps.base import DEFAULT_RETRY_COUNT
from ivr_gateway.steps.config import StepBranch, StepTree
from ivr_gateway.steps.inputs import StepInput
from ivr_gateway.steps.result import StepError
from ivr_gateway.utils import get_model_changes
from ivr_gateway.models.enums import Partner

if TYPE_CHECKING:
    from ivr_gateway.steps.base import Step

__all__ = [
    "WorkflowRun",
    "Workflow",
    "WorkflowConfig",
    "WorkflowStepRun",
    "StepTreeType"
]


class StepTreeType(types.TypeDecorator):
    impl = JSONB
    schema = StepTreeSchema()

    def coerce_compared_value(self, op, value) -> TypeEngine:
        # noinspection PyArgumentList
        return self.impl.coerce_compared_value(op, value)

    def process_bind_param(self, value, dialect) -> dict:
        return self.schema.dump(value)

    def process_result_value(self, value, dialect) -> StepTree:
        return self.schema.load(value)


class WorkflowConfig(Base):
    __tablename__ = "workflow_config"
    step_tree: StepTree
    step_tree_serde = StepTreeSchema()

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflow.id", ondelete="CASCADE"), index=True, nullable=True)
    step_tree = Column(StepTreeType, default={"branches": []}, nullable=True)
    step_tree_sha = Column(String, nullable=True)
    tag = Column(String, nullable=True, index=True)
    minimum_version = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('workflow_id', 'tag', name='unique_workflow_config_tag_for_workflow'),
    )

    workflow = relationship("Workflow", back_populates="configs")
    workflow_runs = relationship("WorkflowRun", back_populates="workflow_config", passive_deletes=True)

    @property
    def branches(self) -> List[StepBranch]:
        return self.step_tree.branches

    def _generate_step_tree_hash(self):
        content = self.step_tree_serde.dumps(self.step_tree)
        return hashlib.sha256(bytes(content, "utf-8")).hexdigest()

    def update_step_tree_sha(self):
        self.step_tree_sha = self._generate_step_tree_hash()

    @property
    def run_count(self) -> Integer:
        session = object_session(self)
        return (session.query(WorkflowRun)
                .filter(WorkflowRun.workflow_config_id == self.id)
                .count())


@event.listens_for(WorkflowConfig, 'before_insert')
def calculate_workflow_hash_on_save(mapper, connection, target: WorkflowConfig):
    ivr_logger.info(f"target: {target}")
    target.update_step_tree_sha()


@event.listens_for(WorkflowConfig, 'before_update')
def receive_before_update(mapper, connection, target: WorkflowConfig):
    ivr_logger.info("WorkflowConfig.receive_before_update")
    ivr_logger.info(f"{target} modified")
    # Do not modify live configs

    object_changes = get_model_changes(target)
    ivr_logger.debug(f"object_changed, {object_changes}")
    has_been_modified = bool(object_changes)
    if has_been_modified:
        if target.run_count > 0:
            raise NonUpdateableModelError(target)
        else:
            target.update_step_tree_sha()


class Workflow(Base):
    step_tree: StepTree

    __tablename__ = "workflow"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    # URL safe or convertible safe name, # joinable to find for WorkflowRun
    partner = Column(Enum(Partner), nullable=True)
    workflow_name = Column(String, nullable=False, index=True, unique=True)
    active_config_tag = Column(String, nullable=True, default="latest")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    inbound_routings = relationship("InboundRouting", back_populates="workflow")
    workflow_runs = relationship("WorkflowRun", back_populates="workflow", passive_deletes=True)
    configs = relationship("WorkflowConfig", back_populates="workflow", passive_deletes=True)

    def __repr__(self):  # pragma: no cover
        return f"<Workflow {self.id}, workflow_name={self.workflow_name}, active_config_tag={self.active_config_tag}>"

    @property
    def latest_config(self) -> WorkflowConfig:
        session = object_session(self)
        return (session.query(WorkflowConfig)
                .filter(WorkflowConfig.workflow_id == self.id)
                .order_by(WorkflowConfig.created_at.desc())
                .first())

    @property
    def active_config(self) -> WorkflowConfig:
        if self.active_config_tag in (None, "", "latest"):
            return self.latest_config
        else:
            session = object_session(self)
            return (session.query(WorkflowConfig)
                    .filter(WorkflowConfig.workflow_id == self.id)
                    .filter(or_(WorkflowConfig.tag == self.active_config_tag,
                                WorkflowConfig.step_tree_sha == self.active_config_tag))
                    .one())


class WorkflowStepRun(Base):
    __tablename__ = "workflow_step_run"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    workflow_run_id = Column(UUID(as_uuid=True), ForeignKey("workflow_run.id"), index=True, nullable=False)
    step_run_id = Column(UUID(as_uuid=True), ForeignKey("step_run.id"), index=True, nullable=False)
    step_state_id = Column(UUID(as_uuid=True), ForeignKey("step_state.id"), index=True, nullable=True)
    run_order = Column(Integer, nullable=False)
    branched_on_error = Column(String, nullable=True)

    workflow_run = relationship(
        "WorkflowRun",
        uselist=False,
        back_populates="workflow_step_runs",
        lazy="joined"
    )
    step_run = relationship(
        "StepRun",
        uselist=False,
        back_populates="workflow_step_runs",
        lazy="joined"
    )
    step_state = relationship(
        "StepState",
        uselist=False,
        backref="workflow_step_run",
        lazy="joined"
    )

    def __repr__(self):  # pragma: no cover
        return f"<WorkflowStepRun {self.id}, workflow_run_id={self.workflow_run_id}, step_run_id={self.step_run_id}>"


class WorkflowRun(EncryptionFingerprintedMixin, Base):
    __tablename__ = "workflow_run"
    __default_step_branch__ = "root"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    state = Column(FSMField, nullable=False)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflow.id", ondelete="CASCADE"), index=True, nullable=False)
    workflow_config_id = Column(UUID(as_uuid=True), ForeignKey("workflow_config.id", ondelete="CASCADE"), index=True,
                                nullable=False)
    # current_queue = Column(String, nullable=True)
    current_queue_id = Column(UUID(as_uuid=True), ForeignKey("queue.id"), index=True, nullable=True)
    session = Column(StringEncryptedType(EncryptableJSONB, encryption_key, AesEngine, 'pkcs5'),
                     nullable=True, default={})
    current_step_branch_name = Column(String, nullable=False, index=True, default=__default_step_branch__)
    # Maybe store slug
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Relationships
    contact_leg = relationship("ContactLeg", uselist=False, back_populates="workflow_run")
    workflow = relationship("Workflow", back_populates="workflow_runs")
    workflow_config = relationship("WorkflowConfig", back_populates="workflow_runs")
    exit_path_type = Column(String, nullable=True)
    exit_path_kwargs = Column(JSONB, nullable=True, default={})

    workflow_step_runs = relationship(
        "WorkflowStepRun",
        uselist=True,
        back_populates="workflow_run",
        passive_deletes=True
    )
    current_queue = relationship("Queue", uselist=False, back_populates="workflow_runs")

    def __repr__(self):  # pragma: no cover
        return f"<WorkflowRun {self.id}, workflow_id={self.workflow_id}, workflow_config_id={self.workflow_config_id}," \
               f"current_queue_id={self.current_queue_id}, state={self.state}, current_step_branch_name={self.current_step_branch_name}>"

    def __init__(self, *args, **kwargs):
        self.state = WorkflowState.uninitialized
        self.current_step_branch_name = self.__default_step_branch__
        super().__init__(*args, **kwargs)

    # def __repr__(self):  # pragma: no cover
    #     return f"<WorkflowRun {self.id}, workflow_id={self.workflow_id}, call_leg_id={self.call_leg_id}>"

    @property
    def step_runs_unordered(self) -> Query:
        return (object_session(self).query(StepRun)
                .join(WorkflowStepRun)
                .join(WorkflowRun)
                .filter(WorkflowRun.id == self.id))

    @property
    def step_runs(self) -> Query:
        return (self.step_runs_unordered
                .order_by(WorkflowStepRun.run_order.asc()))

    @property
    def step_run_count(self) -> Integer:
        return len(self.workflow_step_runs)

    @transition(source=[
        WorkflowState.uninitialized,
    ], target=WorkflowState.initialized)
    def initialize_first_step(self, step: "Step"):
        """
        Appends the step to the workflow_run tracking session and moves the state to in progress
        :param step: Step to append to the tracking state of the workflow_run
        :return:
        """
        ivr_logger.info(f"initialize_first_step: {step.name}")
        ivr_logger.info(f"WorkflowRun: {self.id} - Initializing first step_run: {step.name}")
        ivr_logger.debug(str(step))
        self.append_step_run_to_workflow(step, initialize=True)

    @transition(source=WorkflowState.initialized, target=WorkflowState.step_in_progress)
    def start(self):
        """
        Kicks off workflow_run
        :return:
        """
        ivr_logger.info(f"start Beginning Step {self.get_current_step_run().name}")

    @transition(source=[
        WorkflowState.initialized,
        WorkflowState.step_in_progress,
        WorkflowState.processing_input
    ], target=WorkflowState.step_in_progress)
    def advance_step(self, step: "Step"):
        """
        Appends the step to the workflow_run tracking session and moves the state to in progress
        :param step: Step to append to the tracking state of the workflow_run
        :return:
        """
        ivr_logger.info(f"advance_step: WorkflowRun: {self.id} - Advancing to step: {step.name}")
        self.append_step_run_to_workflow(step)

    @transition(source=[
        WorkflowState.processing_input
    ], target=WorkflowState.requesting_user_input)
    def replay_step(self, step: "Step"):
        """
        Replay the current step, requested by user.
        :param step: Step that is replayed
        :return:
        """
        ivr_logger.info(f"replay_step: WorkflowRun: {self.id} - Replaying step: {step.name}")
        ivr_logger.debug(str(step))
        self.append_step_run_to_workflow(step, retry_step_run=step.step_run)

    @transition(source=[WorkflowState.step_in_progress, WorkflowState.processing_input],
                target=WorkflowState.requesting_user_input)
    def request_user_input(self, step: "Step"):
        ivr_logger.info(f"request_user_input, WorkflowRun: {self.id} - Requesting user input.")
        ivr_logger.info(str(step))
        # When the first step of a workflow_run is a RequestInputStep, we run it once, to get the input prompt but
        # do not advance the step list as we need to run it 2x to apply the user input
        if self.get_current_step_name() != step.name:
            # Not currently on that step so "advance"
            self.append_step_run_to_workflow(step)
        else:
            ivr_logger.info(
                "Must be a workflow_run w/ first step of requesting input, not duplicate appending,"
                f"step {step}"
            )

    @transition(source=WorkflowState.requesting_user_input, target=WorkflowState.processing_input)
    def processing_user_input(self, user_input: StepInput):
        ivr_logger.info(
            f"processing_user_input, WorkflowRun: {self.id} - Processing input: {user_input}"
        )

    @transition(source=[
        WorkflowState.step_in_progress,
        WorkflowState.processing_input
    ], target=WorkflowState.finished)
    def finish(self):
        ivr_logger.info(
            f"finish, WorkflowRun Complete: {self.id}"
        )
        ivr_logger.debug(f"finish, {self}")

    @transition(source=[
        WorkflowState.step_in_progress,
        WorkflowState.processing_input
    ], target=WorkflowState.error)
    def register_error(self, e: StepError):
        appositive_adjective_phase = "a recoverable" if e.retryable else "an"
        ivr_logger.info(f"register_error, WorkflowRun: {self.id}, experienced {appositive_adjective_phase} error")
        ivr_logger.info(f"StepError: {e.msg}")

        if not e.retryable:
            ivr_logger.critical(f"StepError: {e.msg}")

    @transition(source=[
        WorkflowState.error,
    ], target=WorkflowState.requesting_user_input)
    def retry_input_step(self, step: "Step" = None, retry_step_run: StepRun = None):
        ivr_logger.info(f"WorkflowRun: {self.id}, attempting to recover from error")
        ivr_logger.debug(str(step))
        if retry_step_run is not None:
            ivr_logger.debug(str(retry_step_run))
            self.append_step_run_to_workflow(step, retry_step_run=retry_step_run)

    @transition(source=[
        WorkflowState.error
    ], target=WorkflowState.step_in_progress)
    def retry_step(self, step: "Step" = None, retry_step_run: StepRun = None):
        ivr_logger.info(f"retry_step, WorkflowRun: {self.id}, attempting to recover from error")
        if retry_step_run is not None:
            ivr_logger.info(f"retry_step, Retrying step run: {retry_step_run}, Step: {step.name}")
            ivr_logger.debug(f"retry_step {retry_step_run}")
            self.append_step_run_to_workflow(step, retry_step_run=retry_step_run)

    @transition(source=[
        WorkflowState.error
    ], target=WorkflowState.step_in_progress)
    def unregister_error(self, msg: str = None):
        ivr_logger.info(f"Changing WorkflowState from error to step_in_progress; {msg}")

    def switch_step_branch(self, branch_name: str):
        ivr_logger.info(f"Switching workflow to branch: {branch_name}")
        self.current_step_branch_name = branch_name

    def get_workflow_step_runs_for_branch_step(self, branch_name: str, step_name: str) -> [WorkflowStepRun]:
        return [wsr for wsr in self.workflow_step_runs if
                wsr.step_run.name == step_name and wsr.step_run.branch == branch_name]

    def get_branch_step_run(self, branch_name: str, step_name: str) -> Optional[StepRun]:
        matching_runs = self.get_workflow_step_runs_for_branch_step(branch_name, step_name)
        if len(matching_runs) == 0:
            return None
        return matching_runs[0].step_run

    def get_step_retry_count(self, branch_name: str, step_name: str) -> int:
        for branch in self.workflow_config.branches:
            if branch.name == branch_name:
                for step in branch.steps:
                    if step.name == step_name:
                        if 'retry_count' in step.step_kwargs:
                            return step.step_kwargs['retry_count']
                        else:
                            return DEFAULT_RETRY_COUNT
        return DEFAULT_RETRY_COUNT

    def get_workflow_step_runs_for_branch(self, branch_name: str) -> [WorkflowStepRun]:
        return [wsr for wsr in self.workflow_step_runs if wsr.step_run.branch == branch_name]

    def get_last_step_run_on_branch(self, branch_name: str) -> Optional[StepRun]:
        branch_runs = self.get_workflow_step_runs_for_branch(branch_name)
        branch_runs.sort(key=lambda wsr: wsr.run_order, reverse=True)
        if len(branch_runs) == 0:
            return None
        return branch_runs[0].step_run

    def get_step_run_state(self, branch_name: str, step_name: str) -> Optional[StepState]:
        matching_runs = self.get_workflow_step_runs_for_branch_step(branch_name, step_name)
        matching_runs.sort(key=lambda wsr: wsr.run_order, reverse=True)
        maybe_step_run = matching_runs[0]
        # Check if step has been run
        if maybe_step_run is None:
            raise Exception(f"Step {branch_name}.{step_name} has not been run so no results are available")
        # Return step result
        return maybe_step_run.step_state

    def is_valid_step_branch(self, branch_name: str) -> bool:
        step_tree = self.workflow_config.step_tree
        valid_branch = next((x for x in step_tree.branches if x.name == branch_name), None)
        return valid_branch is not None

    def get_current_step_name(self) -> str:
        return self.get_current_step_run().name

    def get_current_workflow_step_run(self) -> WorkflowStepRun:
        sorted_runs = sorted(self.workflow_step_runs, key=lambda wsr: wsr.run_order, reverse=True)
        maybe_workflow_step_run = sorted_runs[0]
        if maybe_workflow_step_run is None:
            raise UninitializedWorkflowActionException("Workflow is not initialized with a step")
        return maybe_workflow_step_run

    def get_current_step_run(self) -> StepRun:
        return self.get_current_workflow_step_run().step_run

    def append_step_run_to_workflow(self, step: "Step", initialize: bool = False, retry_step_run: StepRun = None):
        session = object_session(self)
        if retry_step_run is None:
            initialization = {
                "args": step.args,
                "kwargs": step.kwargs,
                "session": self.session
            }
            step_run = StepRun(
                name=step.name,
                branch=self.current_step_branch_name,
                step_type=step.get_type_string(),
                initialization=initialization
            )
            session.add(step_run)
        else:
            step_run = retry_step_run

        wsr = WorkflowStepRun(
            workflow_run=self,
            step_run=step_run,
            run_order=0 if initialize else self.step_run_count
        )
        step.step_run = step_run
        session.add(wsr)

    def store_session_variable(self, input_key: str, value):
        self.store_session_variables({input_key: value})

    def store_session_variables(self, values: Dict):
        db_session = object_session(self)
        session = self.session.copy()
        session.update(values)
        self.session = session
        db_session.add(self)

# def on_state_change(instance, source, target):
#     print("State changed")
#
# event.listen(WorkflowRun, 'before_state_change', on_state_change)
# event.listen(WorkflowRun, 'after_state_change', on_state_change)
