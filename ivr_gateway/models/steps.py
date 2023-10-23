import uuid
from datetime import datetime
from typing import Optional, Dict, TYPE_CHECKING

from sqlalchemy import event, Boolean
from sqlalchemy.dialects.postgresql.base import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.orm.session import object_session
from sqlalchemy.sql.schema import Column, ForeignKey
from sqlalchemy.sql.sqltypes import DateTime, String
from sqlalchemy_utils.types.encrypted.encrypted_type import StringEncryptedType, AesEngine

from ivr_gateway.exceptions import NonUpdateableModelError
from ivr_gateway.logger import ivr_logger
from ivr_gateway.models import Base
from ivr_gateway.models.encryption import encryption_key, EncryptableJSONB, EncryptionFingerprintedMixin
from ivr_gateway.utils import get_model_changes

if TYPE_CHECKING:
    from ivr_gateway.models.workflows import WorkflowRun


class StepState(EncryptionFingerprintedMixin, Base):
    __tablename__ = "step_state"
    input: Dict
    result: Dict

    # ID as GUID
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    step_run_id = Column(UUID(as_uuid=True), ForeignKey("step_run.id", ondelete='CASCADE'), index=True, nullable=False)
    input = Column(StringEncryptedType(EncryptableJSONB, encryption_key, AesEngine, 'pkcs5'),
                   nullable=True, default={})
    result = Column(StringEncryptedType(EncryptableJSONB, encryption_key, AesEngine, 'pkcs5'),
                    nullable=True, default={})
    error = Column(Boolean, default=False, nullable=False)
    retryable = Column(Boolean, default=None)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    step_run = relationship("StepRun", back_populates="step_states")

    # workflow_step_run = relationship("WorkflowStepRun", uselist=False, backref="step_state")

    def __repr__(self):  # pragma: no cover
        return f"<StepState {self.id}, step_run_id={self.step_run_id}>"


@event.listens_for(StepState, 'before_update')
def receive_before_update(mapper, connection, target):
    ivr_logger.info(f"on_before_update_step_state target: {target} - Checking for modification")
    object_changes = get_model_changes(target)
    has_been_modified = bool(object_changes)
    ivr_logger.info(f"on_before_update_step_state, "
                    f"target: {target} - "
                    f"Modified: {has_been_modified} - "
                    f"keys updated: {list(object_changes.keys())}")
    if has_been_modified:
        error = NonUpdateableModelError(target)
        ivr_logger.critical(f"receive_before_update {error}")
        raise error


class StepRun(EncryptionFingerprintedMixin, Base):
    __tablename__ = "step_run"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    name = Column(String, nullable=False, index=True)
    branch = Column(String, nullable=False, index=True)
    step_type = Column(String, nullable=False)
    initialization = Column(StringEncryptedType(EncryptableJSONB, encryption_key, AesEngine, 'pkcs5'),
                            nullable=True, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    step_states = relationship("StepState", back_populates="step_run", passive_deletes=True)
    workflow_step_runs = relationship(
        "WorkflowStepRun",
        uselist=True,
        back_populates="step_run",
    )

    def __repr__(self):  # pragma: no cover
        return f"<StepRun {self.id}, step_type: {self.step_type}, branch: {self.branch}, name: {self.name}>"

    def get_state(self, run_index: int = -1) -> Optional[StepState]:
        step_states = sorted(self.step_states, key=lambda ss: ss.created_at)
        run_count = len(step_states)
        if run_index < -1 or run_index >= run_count:
            raise IndexError(f"run index out of range, run count: {run_count}")
        elif run_count == 0:
            return None
        else:
            return step_states[run_index]

    @property
    def workflow_run(self) -> Optional["WorkflowRun"]:
        if len(self.workflow_step_runs) > 0:
            return self.workflow_step_runs[0].workflow_run

    @property
    def state(self) -> Optional[StepState]:
        step_states = sorted(self.step_states, key=lambda ss: ss.created_at)
        if len(step_states) == 0:
            return None
        return step_states[0]

    @property
    def run_count(self) -> int:
        """
        Returns the number of times the step has been run
        :return: run count
        """
        return len(self.step_states)

    def create_state_update(self, step_input: Optional[Dict] = None, step_result: Optional[Dict] = None,
                            error: bool = False, retryable: Optional[bool] = None) -> StepState:
        session = object_session(self)
        step_state = StepState(
            step_run=self,
            input=step_input or {},
            result=step_result or {},
            error=error,
            retryable=retryable
        )
        session.add(step_state)
        return step_state
