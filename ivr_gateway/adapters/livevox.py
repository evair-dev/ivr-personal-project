from typing import Tuple

import sqlalchemy
from flask import Request

from ivr_gateway.adapters import BaseSMSAdapter
from ivr_gateway.engines.workflows import WorkflowEngine, WorkflowEngineUnrecoverableException
from ivr_gateway.exit_paths import ExitPath, WorkflowExitPath, SMSExitPath
from ivr_gateway.logger import ivr_logger
from ivr_gateway.models.contacts import ContactLeg, InboundRouting
from ivr_gateway.models.enums import WorkflowState
from ivr_gateway.steps.api.v1 import PlayMessageStep, InputStep, InputActionStep, NumberedInputActionStep
from ivr_gateway.steps.base import Step, NextStepOrExit
from ivr_gateway.steps.inputs import MenuActionInput, NumberedMenuActionInput
from ivr_gateway.steps.result import StepError, StepResult, StepReplay, UserStepError
from ivr_gateway.utils import format_as_sentence


class LiveVoxRequestAdapter(BaseSMSAdapter):

    def __init__(self, name: str, vendor_url: str, base_url: str, session: sqlalchemy.orm.Session):
        super().__init__(name, vendor_url, base_url, session)
        self.current_response = {
            "error": None,
            "text_array": [""],
            "finished": False
        }

    def get_contact_id(self, request: Request) -> str:
        json = request.get_json()
        return json.get("thread_id", "")

    def get_inbound_target(self, request: Request) -> str:
        json = request.get_json()
        return json.get("workflow", "")

    def get_device_identifier(self, request: Request) -> str:
        json = request.get_json()
        phone_number = json.get("phone_number", "")
        if isinstance(phone_number, list):  # Might come as an array
            return phone_number[0]
        return phone_number

    def get_customer_id(self, request: Request) -> str:
        json = request.get_json()
        return json.get("customer_id", "")

    def get_initial_settings(self, request: Request) -> dict:
        json = request.get_json()
        initial_settings = json.get("initial_settings", {})
        final_settings = {}
        for key in initial_settings:
            value = initial_settings.get(key)
            if isinstance(value, list):
                # Copy over the first item in an array if it is an array, sometimes LiveVox will wrap single items
                # in an array, everything should be a single item
                final_settings.update({key: value[0]})
            else:
                final_settings.update({key: value})
        return final_settings

    def process_new_sms(self, sms_leg: ContactLeg, routing: InboundRouting, request: Request):
        ivr_logger.warning(f"LiveVoxRequestAdapter.process_new_sms, SMS: {sms_leg.contact_id}")
        ivr_logger.debug(f"sms_leg: {sms_leg}, routing: {routing}, request: {request}")
        return self.process_sms_leg(request, sms_leg)

    def process_sms_leg(self, request: Request, sms_leg: ContactLeg):
        # Logging as an info here as we may run this method multiple times for the same request
        # so we go to INFO to see inter and intra request spanning info
        ivr_logger.info(f"LiveVoxRequestAdapter.process_sms_leg, SMS: {sms_leg.contact_id}")
        ivr_logger.debug(f"request: {request}, sms_leg: {sms_leg}")

        # If we are currently in the requesting_user_input state then we are applying input
        applying_input = sms_leg.workflow_run.state == WorkflowState.requesting_user_input
        # Run the step, build the response, and capture any errors
        try:
            json_response = request.get_json()
            engine, current_step, result, next_step_or_exit = \
                self._run_workflow_step_for_sms_leg(sms_leg, user_input=json_response.get('input', None))
            ivr_logger.debug(f"current_step: {current_step}, result: {result}, next_step_or_exit: {next_step_or_exit}")
        except WorkflowEngineUnrecoverableException as wee:
            ivr_logger.error(f"caught workflow engine exception: {wee}")
            exit_path = SMSExitPath(exit_msg="Sorry! There was an issue processing your payment. Call 800-712-5407 "
                                             "to speak to an agent.",
                                    overwrite_response=True)
            return self.process_exit_path(
                request, exit_path, sms_leg
            )
        if isinstance(result, StepError):
            # engine.reset_step_error()
            if isinstance(next_step_or_exit, InputStep):
                self._build_message_for_step(next_step_or_exit, previous_error=result)
                return self.current_response
            else:
                # TODO: Handle various step types differently
                return self.process_sms_leg(request, sms_leg)

        elif isinstance(next_step_or_exit, ExitPath):
            ivr_logger.debug("branching to exit path")
            # Build a message for the step we just ran
            if not applying_input:
                self._build_message_for_step(current_step)
            # Handle the exit path since this might transfer to another workflow we can just start
            return self.process_exit_path(request, next_step_or_exit, sms_leg=sms_leg)
        else:
            # If we didn't just apply input (which doesn't need a message built for it)
            if not applying_input:
                # Build a message for the current step
                self._build_message_for_step(current_step)
            # If the next step is an input step and if we aren't cold-starting an input step, build out the message
            if isinstance(next_step_or_exit, InputStep):
                # build the initial gather message
                if current_step != next_step_or_exit or isinstance(result, StepReplay):
                    self._build_message_for_step(next_step_or_exit)
                return self.current_response
            else:
                # Otherwise, we run the next step since we only need to go back to the user if its an input or exit
                return self.process_sms_leg(request, sms_leg)

    def process_exit_path(self, request: Request, exit_path: ExitPath, sms_leg: ContactLeg = None):
        ivr_logger.warning(f"LiveVoxRequestAdapter.process_exit_path, SMS: {sms_leg.contact_id}")
        ivr_logger.debug(f"request: {request}, exit_path: {exit_path}, sms_leg: {sms_leg}")

        # need to end the sms_leg for other exit paths
        self.sms_service.end_sms_leg(sms_leg, exit_path.get_type_string(), exit_path.kwargs)
        if isinstance(exit_path, SMSExitPath):
            ivr_logger.info("SMSExitPath")
            self.current_response["finished"] = True
            if "exit_msg" in exit_path.kwargs and exit_path.kwargs["exit_msg"]:
                if exit_path.kwargs["overwrite_response"]:
                    self.current_response["text_array"] = [exit_path.kwargs["exit_msg"]]
                else:
                    self.update_text_array(self.current_response["text_array"], exit_path.kwargs["exit_msg"])
            return self.current_response
        elif isinstance(exit_path, WorkflowExitPath):
            ivr_logger.info("WorkflowExitPath")
            workflow_name = exit_path.workflow
            ivr_logger.debug(f"exit path workflow: {workflow_name}")
            new_sms_leg = self.sms_service.transfer_sms_leg_to_workflow(sms_leg, workflow_name)
            ivr_logger.debug(f"new sms_leg id: {new_sms_leg.id}")
            return self.process_sms_leg(request, new_sms_leg)

    def _run_workflow_step_for_sms_leg(self, sms_leg: ContactLeg, user_input: str = None) \
            -> Tuple[WorkflowEngine, Step, StepResult, NextStepOrExit]:
        ivr_logger.info("LiveVoxRequestAdapter._run_workflow_step_for_sms_leg")
        ivr_logger.debug(f"Call Leg: {sms_leg}, User Input: {user_input}")
        engine = WorkflowEngine(self.session, sms_leg.workflow_run)
        engine.initialize()
        current_step = engine.get_current_step()
        ivr_logger.debug(f"current_step: {current_step}")
        if engine.workflow_run.state == WorkflowState.requesting_user_input:
            current_step = engine.get_current_step()
            if isinstance(current_step, InputActionStep):
                step_input = MenuActionInput(
                    "number", user_input, menu_actions=current_step.actions
                )
            elif isinstance(current_step, NumberedInputActionStep):
                step_input = NumberedMenuActionInput(
                    "number", user_input, menu_actions=current_step.actions
                )
            elif isinstance(current_step, InputStep):
                step_input = current_step.map_user_input_to_input_type(user_input)
            else:
                step_input = None
            result, next_step_or_exit = engine.run_current_workflow_step(step_input=step_input)
            ivr_logger.debug(f"WorkflowState.requesting_user_input result: {result}")

            return engine, current_step, result, next_step_or_exit
        else:
            result, next_step_or_exit = engine.run_current_workflow_step(step_input=None)
            ivr_logger.debug(f"WorkflowState.requesting_user_input result: {result}")
            return engine, current_step, result, next_step_or_exit

    def _build_message_for_step(self, step: Step, previous_error: StepError = None) -> None:
        if isinstance(step, PlayMessageStep):
            self.current_response["text_array"] = \
                self.update_text_array(self.current_response["text_array"], step.message, end_break=step.end_break,
                                       start_new_message=step.start_new_message)
        if isinstance(step, InputStep):
            start_new_message = step.start_new_message
            if previous_error and isinstance(previous_error, UserStepError):
                if previous_error.user_msg != "":
                    new_text = format_as_sentence(previous_error.user_msg)
                    self.current_response["text_array"] = \
                        self.update_text_array(self.current_response["text_array"], new_text)
                    start_new_message = True
            if step.input_prompt != "":
                new_text = step.input_prompt
                self.current_response["text_array"] = \
                    self.update_text_array(self.current_response["text_array"], new_text,
                                           start_new_message=start_new_message)

    @staticmethod
    def update_text_array(text_array: list, new_text: str, start_new_message: bool = False, end_break: bool = False):
        if start_new_message and text_array[-1] != "":
            text_array.append("")

        max_msg_length = 160
        text = text_array[-1]
        if len(text) % max_msg_length != 0:
            text += " "
        text += new_text
        while len(text) > max_msg_length:
            text_array[-1] = text[:max_msg_length]
            text_array.append("")
            text = text[max_msg_length:]
        text_array[-1] = text

        if end_break:
            text_array.append("")

        return text_array

    def verify_sms_auth(self, request: Request):
        return True
