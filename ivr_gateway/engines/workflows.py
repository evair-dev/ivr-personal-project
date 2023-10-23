import enum
from typing import Union, Tuple, Optional

from sqlalchemy.orm import Session as SQLAlchemySession
from ddtrace import tracer

from ivr_gateway.engines.steps import StepEngine
from ivr_gateway.exit_paths import ExitPath, CurrentQueueExitPath
from ivr_gateway.logger import ivr_logger
from ivr_gateway.models.enums import WorkflowState
from ivr_gateway.models.workflows import WorkflowRun, WorkflowStepRun
from ivr_gateway.services.workflows import WorkflowService
from ivr_gateway.steps.api.v1 import InputStep, BranchWorkflowStep, PlayMessageStep, NoopStep, \
    AddFieldToWorkflowSessionStep, UpdateCallStep, BooleanLogicStep, AddFieldsToWorkflowSessionStep, \
    CopySessionVariable, CallExternalServiceStep
from ivr_gateway.steps.api.v1.Iivr_basic_workflow import AvantBasicWorkflowStep
from ivr_gateway.steps.base import Step, NextStepOrExit
from ivr_gateway.steps.inputs import StepInput
from ivr_gateway.steps.result import StepExitQueue, StepResult, StepError, StepSuccess, StepReplay


class WorkflowEngineException(Exception):

    def __init__(self, message, step_error: Optional[StepError] = None, *args):
        new_args = [message] + list(args)
        super().__init__(*new_args)
        self.step_error = step_error


class WorkflowEngineInitializationException(WorkflowEngineException):
    pass


class WorkflowEngineInvalidStateException(WorkflowEngineException):
    pass


class WorkflowEngineUnrecoverableException(WorkflowEngineException):
    pass


class WorkflowEngineState(enum.Enum):
    uninitialized = "uninitialized"
    initialized = "initialized"
    step_in_progress = "step_in_progress"
    error = "error"
    finished = "finished"


valid_run_states = (
    WorkflowEngineState.initialized,
    WorkflowEngineState.step_in_progress
)

invalid_run_states = (
    WorkflowEngineState.uninitialized,
    WorkflowEngineState.error,
    WorkflowEngineState.finished,
)


class MissingExternalWorkflowDependency(Exception):
    pass


class WorkflowEngine:
    """
    Responsible for running and executing workflow_run steps in the context of a request from an external IVR system

    Constructed by passing in a workflow_run and database session.

    Remember to call WorkflowEngine#initialize after creating the engine before trying to run a step
    """

    def __init__(self, db_session: SQLAlchemySession, workflow_run: WorkflowRun):
        """
        :param db_session: SQLAlchemySession for persisting and storing status updates to steps/workflow_run
        :param workflow_run: The workflow_run object w/ config to run
        """
        self.state = WorkflowEngineState.uninitialized
        self.session = db_session
        self.workflow_run = workflow_run
        self.workflow_service = WorkflowService(
            db_session
        )
        # Initialize a step engine we will use to run a workflow_run step
        self.step_engine = StepEngine(self.session, self.workflow_run)

    def initialize(self) -> None:
        """
        Initialized the workflow_run engine and ensures that it is ready to run a step for a workflow_run. Must be
        called at beginning of any interaction after constructing the engine. Will setup state and initialize the first
        workflow_run step if it has not been initialized so this can create external network calls.
        """
        # Setup Step engine and registering the first workflow_run step
        if self.workflow_run.step_run_count == 0:
            ivr_logger.debug(f"WorkflowEngine.initialize StepRunCount: 0, workflow_run: {self.workflow_run}")
            step = self._get_initial_step_for_workflow_from_config()
            ivr_logger.debug(f"WorkflowEngine.initialize step: {step}")
            # Register first step
            self.workflow_run.initialize_first_step.set(step)
            # Create state for step if needed and initialize a step engine for the current step
            step.step_run = self.workflow_run.get_current_step_run()
            ivr_logger.debug(f"WorkflowEngine.initialize step_run: {step.step_run}")
            self.step_engine.initialize(step)
        else:
            ivr_logger.debug(f"WorkflowEngine.initialize StepRunCount: {self.workflow_run.step_run_count}")
            current_step_run = self.workflow_run.get_current_step_run()
            ivr_logger.debug(f"WorkflowEngine.initialize current_step_run: {current_step_run}")
            step = self.workflow_service.create_step_for_workflow(self.workflow_run, current_step_run.name)
            ivr_logger.debug(f"WorkflowEngine.initialize step: {step}")
            step.step_run = current_step_run
            self.step_engine.initialize(step)
        self.session.add(self.workflow_run)
        self.session.add(step.step_run)
        self.session.add_all(self.workflow_run.workflow_step_runs)
        self.session.commit()
        # Mark that we are initialized and ready to run the step
        self._initialize_engine_state_from_workflow()

    def get_current_step(self) -> Optional[Step]:
        return self.step_engine.current_step

    def get_current_workflow_step_run(self) -> Optional[WorkflowStepRun]:
        return self.workflow_run.get_current_workflow_step_run()

    @tracer.wrap()
    def run_current_workflow_step(self, step_input: StepInput = None) -> Tuple[StepResult, Union[Step, ExitPath]]:
        """
        External control point for services
        Used when:
        * Given input from a user try to execute a workflow_run that has either been initialized or running
        * Runs the step returns a
        :param step_input:

        :return: (step_result, next_step_or_exit): Will contain the result of the step run [a subclass of StepSuccess],
        as well as a link to the next step (or if the workflow_run is complete an exit path)

        :raises WorkflowError: When executing a step creates an error or there are external network or client errors,
        the WorkflowEngine will mark its internal state as in WorkflowEngineState.error, and raise a WorkflowError
        containing the relevant StepError if it exists
        """
        ivr_logger.info(f"WorkflowEngine.run_current_workflow_step StepInput: {step_input}")
        result, next_step_or_exit = self._prepare_for_step_engine_execution(step_input=step_input)
        # we should expect a (True, True)
        if result is not True:
            ivr_logger.debug(f"WorkflowEngine.run_current_workflow_step result: {result}")
            return result, next_step_or_exit
        # Use step engine to run the workflow_run step
        try:
            result = self.step_engine.run_step(step_input=step_input)
            ivr_logger.debug(f"WorkflowEngine.run_current_workflow_step result: {result}")
        except StepError as e:
            ivr_logger.warning(f"WorkflowEngine.run_current_workflow_step StepError: {e.msg}")
            result = e

        return self._handle_step_response(result)

    def can_current_step_retry(self) -> bool:
        """
        Inspects the current step run and determines if it is in an error state can we retry
        :return:
        """
        if self.state == WorkflowEngineState.uninitialized:
            raise WorkflowEngineInvalidStateException(
                message="Workflow engine method can only be called after engine is initialized"
            )
        return self.step_engine.can_current_step_retry()

    def _prepare_for_step_engine_execution(self, step_input: StepInput = None) \
            -> Union[Tuple[bool, bool], Tuple[StepSuccess, NextStepOrExit]]:
        """
        Preps the engine to be executed by setting state variables and validating inputs

        :param step_input:
        :return:
        """

        ivr_logger.info(
            f"WorkflowEngine._prepare_for_step_engine_execution StepInput: {step_input}, State: {self.state}")
        # Make sure if we are running a step for the first time
        # we have an initialized workflow_run, and triggered a "start" event transition
        if self.state == WorkflowEngineState.initialized:
            self.workflow_run.start.set()
            self.session.add(self.workflow_run)
            self.session.commit()
            self.state = WorkflowEngineState.step_in_progress

        ivr_logger.debug(f"WorkflowEngine._prepare_for_step_engine_execution workflow_run: {self.workflow_run}")

        # Validate we are in the correct run state before proceeding
        if self.state in invalid_run_states:
            exception = WorkflowEngineInvalidStateException('Workflow engine can only be called from initialized')
            ivr_logger.critical(f"WorkflowEngine._prepare_for_step_engine_execution: {exception}")
            raise exception

        # Depending on step type we do some other preflight checks
        current_step = self.get_current_step()
        ivr_logger.debug(f"WorkflowEngine._prepare_for_step_engine_execution current_step: {current_step}")
        span = tracer.current_span()
        if span is not None:
            span.set_tags({'branch_name': self.workflow_run.current_step_branch_name,
                           'step_name': current_step.name,
                           'workflow_name': self.workflow_run.workflow.workflow_name})
        if isinstance(current_step, InputStep):
            # When requesting input, if our current state is requesting, then we should be applying on this run
            if self.workflow_run.state == WorkflowState.requesting_user_input:
                # Register the input for processing with the workflow_run
                ivr_logger.info(
                    "WorkflowEngine._prepare_for_step_engine_execution, Workflow run set to process user input")
                self.workflow_run.processing_user_input.set(step_input)
            else:
                # Otherwise this could be a cold start issue, lets mark the workflow_run as requesting input and make
                # sure the step is registered
                self.workflow_run.request_user_input.set(current_step)
                self.session.add(current_step.step_run)
                self.session.add(self.workflow_run)
                self.session.commit()
                # Return the step options to the caller and input prompt
                return StepSuccess(result=current_step.input_prompt), current_step
            # Persist updates and exit
            self.session.add(self.workflow_run)
            self.session.commit()
        return True, True

    def _handle_step_response(self, result: StepResult) -> Tuple[StepResult, NextStepOrExit]:
        """
        Process step engine results allowing us to customize the behavior for different
        types of step operations

        :param result:
        :return:
        """
        # Persist the result's step state with an attachment to the specific StepState that was generated during the run
        current_wsr = self.get_current_workflow_step_run()
        current_wsr.step_state = result.step_state
        self.session.add(current_wsr)
        if isinstance(result, StepError):
            return self._handle_step_error(result)
        elif isinstance(result, StepReplay):
            return self._handle_step_replay(result)
        elif isinstance(result, StepExitQueue):
            return self._handle_step_press_zero_transfer_queue(result)
        elif isinstance(result, StepSuccess):
            return self._handle_step_success(result)
        else:
            raise WorkflowEngineException(f"Cannot process result type of {result.__class__.__name__}")

    def _handle_step_press_zero_transfer_queue(self, result: StepExitQueue) -> Tuple[StepResult, NextStepOrExit]:
        current_exit_path = CurrentQueueExitPath()
        self.workflow_run.finish.set()
        self.workflow_run.exit_path_type = current_exit_path.get_type_string()
        self.workflow_run.exit_path_kwargs = current_exit_path.kwargs
        self.session.add(self.workflow_run)
        self.session.commit()
        self.state = WorkflowEngineState.finished
        return result, current_exit_path

    def _handle_step_error(self, result: StepError) -> Tuple[StepResult, NextStepOrExit]:
        # On a step error mark the internal state as in error and raise an exception
        self.state = WorkflowEngineState.error
        self.workflow_run.register_error.set(result)
        current_step = self.get_current_step()
        ivr_logger.debug(str(current_step))
        if result.retryable:
            if current_step.on_error_reset_to_step:
                run_count = self.workflow_run.get_branch_step_run(self.workflow_run.current_step_branch_name,
                                                                  current_step.on_error_reset_to_step).run_count
                retry_count = self.workflow_run.get_step_retry_count(self.workflow_run.current_step_branch_name,
                                                                     current_step.on_error_reset_to_step)
            else:
                run_count = self.step_engine.get_current_step_run().run_count
                retry_count = self.get_current_step().retry_count

            if run_count >= retry_count:
                # Switch branches on error if specified
                if current_step.on_error_switch_to_branch is not None:
                    return self._handle_switch_branch_on_error(current_step, result)

                ivr_logger.error("Unrecoverable Step Error: retry count reached")
                raise WorkflowEngineUnrecoverableException(
                    f"Step Error retry count reached for workflow: {result.msg}", step_error=result
                )
            # Check to see if the step has a step to reset to on errors
            if current_step.on_error_reset_to_step is not None:
                # Reset the error on the engine since we will be retrying
                step = self.workflow_service.create_step_for_workflow(
                    self.workflow_run, current_step.on_error_reset_to_step
                )
                ivr_logger.info(f"Reset to step: {step}")
                existing_step_run = self.workflow_run.get_branch_step_run(
                    self.workflow_run.current_step_branch_name, step.name
                )

                ivr_logger.debug(f"Reset to step, step_run: {existing_step_run}")
                self.session.refresh(existing_step_run)
                if isinstance(step, InputStep) and self.workflow_run.state != WorkflowState.requesting_user_input:
                    ivr_logger.warning("retrying input step")
                    self.workflow_run.retry_input_step.set(step=step, retry_step_run=existing_step_run)
                elif self.workflow_run.state != WorkflowState.step_in_progress:
                    ivr_logger.warning("retrying step run")
                    self.workflow_run.retry_step.set(step=step, retry_step_run=existing_step_run)
                step.step_run = existing_step_run
            else:
                step = current_step
                ivr_logger.debug(str(step))
                if isinstance(step, InputStep):
                    ivr_logger.warning("retrying input step")
                    self.workflow_run.retry_input_step.set(step=step, retry_step_run=step.step_run)
                else:
                    ivr_logger.warning("retrying warning step")
                    self.workflow_run.retry_step.set(step=step, retry_step_run=step.step_run)

            self.session.add_all([self.workflow_run, step.step_run])
            self.session.commit()
            self._initialize_engine_state_from_workflow()
            self.step_engine.initialize(step)
            return result, step
        else:
            # Switch branches on error if specified
            if current_step.on_error_switch_to_branch is not None:
                return self._handle_switch_branch_on_error(current_step, result)

            ivr_logger.critical(f"Unrecoverable Step Error: {result.msg}")
            raise WorkflowEngineUnrecoverableException(
                f"Step Error Triggered in workflow: {result.msg}", step_error=result
            )

    def _handle_switch_branch_on_error(self, current_step: Step, result: StepError):
        wsr = self.get_current_workflow_step_run()
        wsr.branched_on_error = current_step.on_error_switch_to_branch
        self.workflow_run.switch_step_branch(wsr.branched_on_error)

        # Reset WorkflowState and WorkflowEngineState
        self.workflow_run.unregister_error.set(msg="switched branches due to error")
        self.step_engine.state = WorkflowEngineState.step_in_progress

        # Process step as we would in _handle_step_success
        next_step_or_exit = self.workflow_service.process_step_result(self.workflow_run)
        self.workflow_run.advance_step.set(next_step_or_exit)
        self.session.add(self.workflow_run)
        self.session.commit()
        self.state = WorkflowEngineState.step_in_progress
        self.step_engine.initialize(next_step_or_exit)

        # Swallowing StepError here to allow for continued workflow processing after branch switch
        return StepSuccess(f"Switched branch due to error: {result.msg}"), next_step_or_exit

    def _handle_step_replay(self, result: StepReplay) -> Tuple[StepResult, NextStepOrExit]:
        ivr_logger.info(f"result: {result}")
        current_step = self.get_current_step()
        # Replay_step, don't change step runs.
        ivr_logger.debug(f"current_step: {current_step}, workflow_run: {self.workflow_run}")
        self.workflow_run.replay_step.set(current_step)
        self.session.add(self.workflow_run)
        self.session.commit()
        self.state = WorkflowEngineState.step_in_progress
        # Load the next step in case this is an interactive or multi run use
        self.step_engine.initialize(current_step)
        return result, current_step

    def _handle_step_success(self, result: StepSuccess):
        ivr_logger.info(f"result: {result}")
        current_step = self.get_current_step()
        ivr_logger.debug(f"current step: {current_step}")
        if isinstance(current_step, BranchWorkflowStep):
            # Trigger the branch
            ivr_logger.info(f"branching: {current_step}")
            self.workflow_run.switch_step_branch(result.result)
            # Use workflow service to process the result into a next step or exit 
        next_step_or_exit = self.workflow_service.process_step_result(self.workflow_run)
        ivr_logger.info(f"next_step_or_exit: {next_step_or_exit}")
        if isinstance(next_step_or_exit, ExitPath):
            # When we receive an exit path the workflow_run is completed so mark it as "finished"
            # and update the engine state
            self.workflow_run.finish.set()
            self.workflow_run.exit_path_type = next_step_or_exit.get_type_string()
            self.workflow_run.exit_path_kwargs = next_step_or_exit.kwargs
            self.session.add(self.workflow_run)
            self.session.commit()
            self.state = WorkflowEngineState.finished
        elif isinstance(next_step_or_exit, Step):
            # If we are requesting input, mark that with the workflow_run
            # Otherwise, we have another step to complete so advance the workflow_run
            if isinstance(next_step_or_exit, InputStep):
                self.workflow_run.request_user_input.set(next_step_or_exit)
            elif isinstance(next_step_or_exit, (NoopStep, PlayMessageStep, BranchWorkflowStep, BooleanLogicStep,
                                                AddFieldToWorkflowSessionStep, AddFieldsToWorkflowSessionStep,
                                                AvantBasicWorkflowStep, UpdateCallStep, CopySessionVariable,
                                                CallExternalServiceStep)):
                self.workflow_run.advance_step.set(next_step_or_exit)
            else:
                ivr_logger.critical(f"Cannot register next step with workflow_run. Step: {next_step_or_exit}")
                raise WorkflowEngineException(
                    f"Cannot register next step with workflow_run. Step: {next_step_or_exit}")
            self.session.add(self.workflow_run)
            self.session.commit()
            self.state = WorkflowEngineState.step_in_progress
            # Load the next step in case this is an interactive or multi run use
            self.step_engine.initialize(next_step_or_exit)
        return result, next_step_or_exit

    def _get_initial_step_for_workflow_from_config(self) -> Step:
        initial_step_template = self.workflow_run.workflow_config.step_tree.branches[0].steps[0]
        step_name = initial_step_template.name
        return self.workflow_service.create_step_for_workflow(self.workflow_run, step_name)

    def _initialize_engine_state_from_workflow(self):
        if self.workflow_run.state == WorkflowState.initialized:
            self.state = WorkflowEngineState.initialized
        elif self.workflow_run.state in (
                WorkflowState.step_in_progress,
                WorkflowState.requesting_user_input,
        ):
            # WorkflowRun already has a step registered
            self.state = WorkflowEngineState.step_in_progress
        else:
            self.state = WorkflowEngineState.error
