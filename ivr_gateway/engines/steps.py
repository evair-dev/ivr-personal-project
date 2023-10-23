from typing import Optional

from sqlalchemy.orm import Session as SQLAlchemySession

from ivr_gateway.logger import ivr_logger
from ivr_gateway.models.steps import StepState, StepRun
from ivr_gateway.models.workflows import WorkflowRun
from ivr_gateway.models.enums import StringEnum
from ivr_gateway.services.amount.workflow_runner import WorkflowRunnerService
from ivr_gateway.services.queues import QueueService
from ivr_gateway.services.workflows import WorkflowService
from ivr_gateway.services.workflows.fields import FieldSessionService
from ivr_gateway.steps.api import v1
from ivr_gateway.steps.base import Step
from ivr_gateway.steps.inputs import StepInput
from ivr_gateway.steps.result import StepError, StepResult


class StepEngineState(StringEnum):
    uninitialized = "uninitialized"
    initialized = "initialized"
    step_in_progress = "step_in_progress"
    step_error = "step_error"
    step_complete = "step_complete"


class StepEngine:
    _valid_step_types = v1.REGISTRY

    def __init__(self, db_session: SQLAlchemySession, workflow_run: WorkflowRun):
        self.db_session = db_session
        self.workflow_run = workflow_run
        self.state = StepEngineState.uninitialized
        self.workflow_service = WorkflowService(db_session)
        self.current_step: Optional[Step] = None

    def initialize(self, step: Step):
        # Make sure we have a step run object
        step_run = self.workflow_run.get_current_step_run() if step.step_run is None else step.step_run
        # Make sure we are setup for run by committing the run and state
        self.db_session.add(step_run)
        self.db_session.commit()
        self.current_step = step
        self.state = StepEngineState.initialized
        ivr_logger.info(f"step initalized: {step.name}")
        ivr_logger.debug(f"step:{step}, step_run: {step_run}")

    def run_step(self, step_input: StepInput = None) -> StepResult:
        result: Optional[StepResult]
        new_step_state: Optional[StepState]

        ivr_logger.debug(f"run_step: step_input: {step_input}")
        if self.state != StepEngineState.initialized:
            error = StepError("Cannot run engine that is not initialized", retryable=False)
            ivr_logger.critical(error)
            raise error
        assert self.current_step is not None  # nosec
        self.state = StepEngineState.step_in_progress
        ivr_logger.debug(f"run_step current_step: {self.current_step}")

        # Steps can throw RunStepExceptions or errors in processing results can raise them
        try:
            result = self._run_step_and_process_result(step_input=step_input)
        except StepError as e:
            # Try to persist the step state in case the step engine blew up
            self.db_session.add(self.current_step.step_run)
            self.db_session.commit()
            self.state = StepEngineState.step_error
            ivr_logger.warning(f"Exception: {e.msg}, StepRun: {self.current_step.step_run}")
            raise e

        # If we don't have a result, then we didnt match on the step type, raises exceptions
        if result is None:
            ivr_logger.critical(str(StepError("Step type not matched", retryable=False)))
            raise StepError("Step type not matched", retryable=False)
        if isinstance(result, StepError):
            self.state = StepEngineState.step_error
            raise result
        # Update the step state object from the run result
        ivr_logger.debug(str(result))
        self.db_session.add(self.current_step.step_run)
        self.db_session.commit()
        self.state = StepEngineState.step_complete
        return result

    def get_step_error_message(self) -> Optional[str]:
        if self.current_step.step_run.state.error:
            return self.current_step.step_run.state.result['message']

    def get_current_step_run(self) -> StepRun:
        return self.current_step.step_run

    def can_current_step_retry(self) -> bool:
        if self.current_step.step_run.run_count > 0 and \
                self.current_step.step_run.state.error and \
                not self.current_step.step_run.state.retryable:
            return False
        else:
            return True

    def _run_step_and_process_result(self, step_input: StepInput = None) -> StepResult:
        if isinstance(self.current_step, v1.APIV1Step):
            return self._run_v1_step_and_process_result(self.current_step, step_input)
        else:
            raise StepError(
                f"StepEngine cannot process step {self.current_step}, valid step types are {self._valid_step_types}",
                retryable=False
            )

    def _run_v1_step_and_process_result(self, step: v1.APIV1Step, step_input: StepInput = None) \
            -> StepResult:
        ivr_logger.info(f"branch: {self.workflow_run.current_step_branch_name}, step: {step.name}")
        ivr_logger.debug(f"_run_v1_step_and_process_result step: {step}")
        if isinstance(step, v1.InputStep):
            ivr_logger.info("step_type: v1.InputStep")
            return step.run(step_input=step_input)
        elif isinstance(step, (v1.AddFieldToWorkflowSessionStep, v1.AddFieldsToWorkflowSessionStep)):
            ivr_logger.info("step_type: v1.AddFieldToWorkflowSessionStep")
            return step.run(service=FieldSessionService(self.db_session))
        elif isinstance(step, v1.AvantBasicWorkflowStep):
            ivr_logger.info("step_type: v1.AvantBasicWorkflowStep")
            return step.run(workflow_runner_service=WorkflowRunnerService(self.db_session))
        elif isinstance(step, v1.UpdateCurrentQueueStep):
            ivr_logger.info("step_type: v1.UpdateCurrentQueueStep")
            return step.run(queue_service=QueueService(self.db_session))
        elif isinstance(step, (v1.NoopStep, v1.PlayMessageStep, v1.BranchWorkflowStep, v1.BooleanLogicStep,
                               v1.UpdateCallStep, v1.CopySessionVariable)):
            ivr_logger.info("step_type: v1.NoopStep, v1.PlayMessageStep, v1.BranchWorkflowStep, v1.BooleanLogicStep, "
                            "v1.UpdateCallStep, v1.CopySessionVariable")
            return step.run()
        elif isinstance(step, v1.CallExternalServiceStep):
            ivr_logger.info("step_type: v1.CallExternalServiceStep")
            return step.run(db_session=self.db_session)

        else:
            error =StepError(
                f"StepEngine cannot process step {self.current_step}, valid step types are {self._valid_step_types}",
                retryable=False
            )

            ivr_logger.error(error)

            raise error
