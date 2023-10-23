import json
import os
from typing import Optional, Tuple

import sqlalchemy.orm
from flask import Request
from twilio.request_validator import RequestValidator
from twilio.twiml import TwiML
from twilio.twiml.voice_response import VoiceResponse, Gather, Enqueue

from ivr_gateway.adapters import BaseCallAdapter
from ivr_gateway.adapters.exceptions import InvalidAuthenticationException
from ivr_gateway.adapters.ssml import SSML
from ivr_gateway.engines.workflows import WorkflowEngine, WorkflowEngineUnrecoverableException
from ivr_gateway.exit_paths import ExitPath, HangUpExitPath, QueueExitPath, WorkflowExitPath, CurrentQueueExitPath, \
    PSTNExitPath, ErrorTransferToCurrentQueueExitPath, AdapterStatusCallBackExitPath
from ivr_gateway.logger import ivr_logger
from ivr_gateway.models.admin import AdminUser, AdminCall, ScheduledCall
from ivr_gateway.models.contacts import ContactLeg, InboundRouting, TransferRouting
from ivr_gateway.models.enums import TransferType, WorkflowState, AdminRole, OperatingMode
from ivr_gateway.models.exceptions import MissingTransferRoutingException
from ivr_gateway.models.queues import Queue
from ivr_gateway.models.workflows import WorkflowRun
from ivr_gateway.services.admin import AdminService
from ivr_gateway.services.screenpop import ScreenPopService
from ivr_gateway.steps.api.v1 import InputStep, PlayMessageStep, InputActionStep, NumberedInputActionStep
from ivr_gateway.steps.base import Step, NextStepOrExit
from ivr_gateway.steps.inputs import MenuActionInput, NumberedMenuActionInput
from ivr_gateway.steps.result import StepError, StepResult, StepReplay, UserStepError


class TwilioClientGateway:
    pass


class TwilioClient:
    pass


def nest_say_in_response(twiml_object: TwiML, message: str):
    ssml = SSML(message)
    twiml_object.nest(ssml)


class TwilioRequestAdapter(BaseCallAdapter):
    ADMIN_NEW_CALL_PATH = "/admin/new"
    GATHER_ADMIN_VERIFY_PATH = "/admin/verify"
    GATHER_ADMIN_LOGIN_PATH = "/admin/login"
    GATHER_ADMIN_ANI_PATH = "/admin/ani"
    GATHER_ADMIN_DNIS_PATH = "/admin/dnis"
    GATHER_ADMIN_ROUTING_PATH = "/admin/routing"
    CONTINUE_PATH = "/continue"
    COMPLETED_STATUS = "completed"
    STATUS_CALLBACK_EXIT_PATH = "ivr_gateway.exit_paths.StatusCallBack"

    _current_voice_response: VoiceResponse = None

    def __init__(self, name: str, vendor_url: str, base_url: str, session: sqlalchemy.orm.Session):
        super().__init__(name, vendor_url, base_url, session)
        self._current_voice_response = VoiceResponse()

    @property
    def current_voice_response(self) -> VoiceResponse:
        return self._current_voice_response

    def transfer_call_in(self, request: Request) -> TwiML:
        pass

    def process_new_call(self, call_leg: ContactLeg, routing: InboundRouting, request: Request) -> TwiML:
        ivr_logger.warning(f"TwilioRequestAdapter.process_new_call, call: {call_leg.contact_id}")
        ivr_logger.debug(f"call_leg: {call_leg}, routing: {routing}, request: {request}")
        nest_say_in_response(self.current_voice_response, routing.greeting.message)
        return self.process_call_leg(request, call_leg)

    def process_call_leg(self, request: Request, call_leg: ContactLeg) -> TwiML:
        # Logging as an info here as we may run this method multiple times for the same request
        # so we go to INFO to see inter and intra request spanning info
        ivr_logger.info(f"TwilioRequestAdapter.process_call_leg, call: {call_leg.contact_id}")
        ivr_logger.debug(f"request: {request}, call_leg: {call_leg}")

        # If we are currently in the requesting_user_input state then we are applying input
        applying_input = call_leg.workflow_run.state == WorkflowState.requesting_user_input
        # Run the step, build the response, and capture any errors
        try:
            engine, current_step, result, next_step_or_exit = \
                self._run_workflow_step_for_call_leg(call_leg, user_input=request.form.get('Digits', None))
            ivr_logger.debug(f"current_step: {current_step}, result: {result}, next_step_or_exit: {next_step_or_exit}")
        except WorkflowEngineUnrecoverableException as wee:
            ivr_logger.error(f"caught workflow engine exception: {wee}")
            exit_path = ErrorTransferToCurrentQueueExitPath(error=repr(wee))
            return self.process_exit_path(
                request, exit_path, call_leg
            )
        if isinstance(result, StepError):
            # engine.reset_step_error()
            if isinstance(next_step_or_exit, InputStep):
                self._build_message_for_step(next_step_or_exit, previous_error=result)
                return self.current_voice_response
            else:
                # TODO: Handle various step types differently
                return self.process_call_leg(request, call_leg)

        elif isinstance(next_step_or_exit, ExitPath):
            ivr_logger.debug("branching to exit path")
            # Build a message for the step we just ran
            if not applying_input:
                self._build_message_for_step(current_step)
            # Handle the exit path since this might transfer to another workflow we can just start
            return self.process_exit_path(request, next_step_or_exit, call_leg=call_leg)
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
                return self.current_voice_response
            else:
                # Otherwise, we run the next step since we only need to go back to the user if its an input or exit
                return self.process_call_leg(request, call_leg)

    def process_exit_path(self, request: Request, exit_path: ExitPath, call_leg: ContactLeg = None) -> TwiML:
        ivr_logger.warning(f"TwilioRequestAdapter.process_exit_path, call: {call_leg.contact_id}")
        ivr_logger.debug(f"request: {request}, exit_path: {exit_path}, call_leg: {call_leg}")

        # transfer to queue methods handle end the call_leg
        if isinstance(exit_path, (CurrentQueueExitPath, ErrorTransferToCurrentQueueExitPath)):
            ivr_logger.info("Exiting to current queue")
            return self.transfer_to_current_queue(call_leg, exit_path)
        elif isinstance(exit_path, QueueExitPath):
            ivr_logger.info("Exiting to exit path queue")
            ivr_logger.debug(f"exit path queue: {exit_path.queue_name}")
            queue = self.queue_service.get_queue_by_name(exit_path.queue_name)
            return self.transfer_to_queue(call_leg, queue, exit_path)

        # need to end the call_leg for other exit paths
        self.call_service.end_call_leg(call_leg, exit_path.get_type_string(), exit_path.kwargs)
        if isinstance(exit_path, HangUpExitPath):
            ivr_logger.info("HangUpExitPath")
            self.current_voice_response.hangup()
            return self.current_voice_response
        elif isinstance(exit_path, WorkflowExitPath):
            ivr_logger.info("WorkflowExitPath")
            workflow_name = exit_path.workflow
            ivr_logger.debug(f"exit path workflow: {workflow_name}")
            new_call_leg = self.call_service.transfer_call_leg_to_workflow(call_leg, workflow_name)
            ivr_logger.debug(f"new call_leg id: {new_call_leg.id}")
            return self.process_call_leg(request, new_call_leg)
        elif isinstance(exit_path, PSTNExitPath):
            ivr_logger.info("PSTNExitPath")
            ivr_logger.debug(f"PSTN Phone Number: {exit_path.phone_number}")
            self.dial_out(exit_path.phone_number)
            return self.current_voice_response

    def _run_workflow_step_for_call_leg(self, call_leg: ContactLeg, user_input: str = None) \
            -> Tuple[WorkflowEngine, Step, StepResult, NextStepOrExit]:
        ivr_logger.info("TwilioRequestAdapter._run_workflow_step_for_call_leg")
        ivr_logger.debug(f"Call Leg: {call_leg}, User Input: {user_input}")
        engine = WorkflowEngine(self.session, call_leg.workflow_run)
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
            ivr_logger.debug(f"StepResult: {result}")
            return engine, current_step, result, next_step_or_exit

    def _build_message_for_step(self, step: Step, previous_error: StepError = None) -> None:
        if isinstance(step, PlayMessageStep):
            nest_say_in_response(self.current_voice_response, step.message)
        if isinstance(step, InputStep):
            timeout = step.timeout
            expected_length = step.expected_input_length
            expected_length = expected_length if expected_length > -1 else \
                step.kwargs.get("expected_length", None)
            if expected_length is not None:
                gather = Gather(action=f'{self.base_url}{self.CONTINUE_PATH}', actionOnEmptyResult=True,
                                numDigits=expected_length, timeout=timeout)
            else:
                gather = Gather(action=f'{self.base_url}{self.CONTINUE_PATH}', actionOnEmptyResult=True,
                                timeout=timeout)
            if previous_error and isinstance(previous_error, UserStepError):
                nest_say_in_response(
                    gather, previous_error.user_msg
                )
            nest_say_in_response(gather, step.input_prompt)
            self.current_voice_response.append(gather)

    def transfer_to_current_queue(self, call_leg: ContactLeg, exit_path: ExitPath) -> TwiML:
        queue = call_leg.workflow_run.current_queue
        if queue is None:
            self.call_service.end_call_leg(call_leg, exit_path.get_type_string(), exit_path.kwargs)
            self.current_voice_response.hangup()
            return self.current_voice_response
        return self.transfer_to_queue(call_leg, queue, exit_path)

    def transfer_to_queue(self, call_leg: ContactLeg, queue: Queue, exit_path: ExitPath) -> TwiML:
        try:
            transfer_routing, routing_operating_mode, maybe_holiday = \
                self.queue_status_service.get_current_transfer_routing_mode_and_maybe_holiday_for_queue(queue, "twilio")
        except MissingTransferRoutingException as e:
            ivr_logger.critical(f"Missing Transfer routing for queue: {queue.name}, Exception: {e}")
            # TODO: handle queue fallback logic (emergency sip, pstn, message)
            nest_say_in_response(
                self.current_voice_response,
                "I'm sorry but there's been an unrecoverable exception, Goodbye"
            )
            exit_path_kwargs = exit_path.kwargs
            exit_path_kwargs.update({
                "error": "missing transfer routing"
            })
            self.call_service.end_call_leg(call_leg, exit_path.get_type_string(), exit_path.kwargs)
            self.current_voice_response.hangup()
            return self.current_voice_response

        exit_path_kwargs = exit_path.kwargs

        if transfer_routing.queue != queue:
            exit_path_kwargs.update({
                "final_queue": transfer_routing.queue.name,
                "operating_mode": OperatingMode.CLOSED  # Will only change queue if main queue is closed
            })
        else:
            exit_path_kwargs.update({
                "operating_mode": routing_operating_mode
            })
        call_leg.transfer_routing = transfer_routing
        self.call_service.end_call_leg(call_leg, exit_path.get_type_string(), exit_path_kwargs)

        if routing_operating_mode != OperatingMode.NORMAL:
            # We have some queue in the routings that returned but is not in the normal mode so handle that
            if routing_operating_mode == OperatingMode.EMERGENCY:
                emergency_message = queue.emergency_message or self.call_service.get_system_wide_emergency_message()
                nest_say_in_response(self.current_voice_response, emergency_message)
                self.current_voice_response.hangup()
            elif routing_operating_mode == OperatingMode.CLOSED:
                nest_say_in_response(self.current_voice_response, queue.closed_message)
                self.current_voice_response.hangup()
            elif routing_operating_mode == OperatingMode.HOLIDAY:
                assert maybe_holiday is not None  # nosec
                nest_say_in_response(self.current_voice_response, maybe_holiday.message or queue.closed_message)
                self.current_voice_response.hangup()
            return self.current_voice_response

        if transfer_routing.transfer_type == TransferType.SIP:
            ivr_logger.debug(f"SIPing out: {transfer_routing.destination}")
            # response.refer()
            pass
        elif transfer_routing.transfer_type == TransferType.PSTN:
            self.dial_out(transfer_routing.destination)
        elif transfer_routing.transfer_type == TransferType.INTERNAL:
            self.transfer_to_flex(call_leg, transfer_routing)
        return self.current_voice_response

    def dial_out(self, phone_number: str):
        ivr_logger.debug(f"Dialing out: {phone_number}")
        self.current_voice_response.dial(phone_number)

    def transfer_to_flex(self, call_leg: ContactLeg, transfer_routing: TransferRouting):

        e = Enqueue(None, workflowSid=transfer_routing.destination)
        call = call_leg.contact
        phone_number = '+' + call.device_identifier
        partner = transfer_routing.queue.partner
        screenpop_service = ScreenPopService()
        screenpop_url = screenpop_service.get_url(call, partner)
        call_details = {
            "customers": {
                'customer_label_1': call.customer_id,
            },
            'secure_key': call.secured_key,
            'queue_name': transfer_routing.queue.name,
            'screenpop': screenpop_url,
            "type": "inbound",
            "name": phone_number
        }
        e.task(json.dumps(call_details))

        self.current_voice_response.append(e)

    def get_call_id(self, request: Request) -> str:
        return request.form.get("CallSid")

    def get_called_party(self, request: Request) -> str:
        called = request.form.get("To")
        if called.startswith("+"):
            return called[1:]
        return called

    def get_calling_party(self, request: Request) -> Optional[str]:
        calling = request.form.get("From")
        if calling is None:
            return None
        if calling.startswith("+"):
            return calling[1:]
        return calling

    def update_call_status(self, request: Request):
        call_id = self.get_call_id(request)
        ivr_logger.warning(f"TwilioRequestAdapter.update_call_status, call: {call_id}")
        call_leg = self.call_service.get_active_call_leg_for_call_system_and_id(self.name, call_id)
        if call_leg is None:
            ivr_logger.info(f"call: {call_id} is already complete")
            return
        call_status = request.form.get("CallStatus", "unknown")
        maybe_workflow_run: Optional[WorkflowRun] = call_leg.workflow_run
        if maybe_workflow_run is not None and call_status == self.COMPLETED_STATUS and call_leg.end_time is None:
            if maybe_workflow_run.state != WorkflowState.finished:
                self.call_service.end_call_leg(call_leg, AdapterStatusCallBackExitPath.get_type_string(),
                                               {"call_status": "disconnect"})

        if call_status == self.COMPLETED_STATUS and call_leg.end_time is None:
            self.call_service.end_call_leg(call_leg, AdapterStatusCallBackExitPath.get_type_string(),
                                           {"call_status": call_status})

    def verify_call_auth(self, request: Request):
        should_authenticate = os.getenv("TELEPHONY_AUTHENTICATION_REQUIRED", "true")
        ivr_logger.debug(f"call should authenticate: {should_authenticate}")
        if should_authenticate != "true":
            return True
        try:
            form = request.form
            account_sid = form.get("AccountSid")
            twilio_auth_token = os.getenv(f"TWILIO_{account_sid}_AUTH_TOKEN", None)
            if twilio_auth_token is None:
                twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
            request_validator = RequestValidator(twilio_auth_token)
            url = request.url
            signature = request.headers.get("X-Twilio-Signature", "")
            valid = request_validator.validate(url, form, signature)

            if not valid:
                ivr_logger.warning("TwilioRequestAdapter.verify_call_auth, invalid authentication for the request")
                raise InvalidAuthenticationException("Invalid signature")
            ivr_logger.debug("verify_call_auth call is authorized")
        except Exception:
            ivr_logger.warning("TwilioRequestAdapter.verify_call_auth, invalid authentication for the request")
            raise InvalidAuthenticationException("Invalid signature")

    def gather_admin_ani(self, admin_user: AdminUser, invalid=False) -> TwiML:
        gather = Gather(action=f"{self.base_url}{self.GATHER_ADMIN_ANI_PATH}", actionOnEmptyResult=True, timeout=10)
        prefix = "Invalid number, " if invalid else ""
        if admin_user.role == AdminRole.admin:
            gather.say(f"{prefix}Please enter the customer phone number or ID")
        else:
            gather.say(f"{prefix}Please enter the ID for the customer number")
        self.current_voice_response.append(gather)
        return self.current_voice_response

    def gather_admin_dnis(self, admin_user: AdminUser, invalid: bool = False) -> TwiML:

        gather = Gather(action=f"{self.base_url}{self.GATHER_ADMIN_DNIS_PATH}", actionOnEmptyResult=True, timeout=10)
        prefix = "Invalid number, " if invalid else ""
        if admin_user.role == "admin":
            gather.say(f"{prefix}Please enter the target phone number or ID")
        else:
            gather.say(f"{prefix}Please enter the ID for the target number")
        self.current_voice_response.append(gather)
        return self.current_voice_response

    def gather_admin_routing(self, invalid=False) -> TwiML:
        prefix = "Invalid routing priority, " if invalid else ""
        gather = Gather(action=f"{self.base_url}{self.GATHER_ADMIN_ROUTING_PATH}", actionOnEmptyResult=True, timeout=10)
        gather.say(f"{prefix}Please enter the routing priority")
        self.current_voice_response.append(gather)
        return self.current_voice_response

    def hangup(self, message: str = None) -> TwiML:
        response = VoiceResponse()
        if message is not None:
            response.say(message)
        response.hangup()
        return response

    @staticmethod
    def verified_admin_call(call: AdminCall) -> bool:
        if call is None:
            return False
        return call.verified

    def gather_admin_login(self, request: Request) -> TwiML:
        response = VoiceResponse()
        gather = Gather(action=f"{self.base_url}{self.GATHER_ADMIN_LOGIN_PATH}", actionOnEmptyResult=True, timeout=10)
        gather.say("Please enter your user ID shortcode")
        response.append(gather)
        return response

    def process_gather_admin_login(self, request: Request) -> TwiML:
        admin_service = AdminService(self.session)
        short_id = request.form.get('Digits', None)
        admin_user = admin_service.find_admin_user_by_short_id(short_id)
        if admin_user is None:
            return self.hangup("Invalid User ID")
        else:
            ani = self.get_calling_party(request)
            dnis = self.get_called_party(request)
            admin_service.create_admin_call(
                self.name, self.get_call_id(request), admin_user, ani, dnis
            )
            return self.gather_admin_verify(request)

    def gather_admin_verify(self, request: Request) -> TwiML:
        response = VoiceResponse()
        gather = Gather(action=f"{self.base_url}{self.GATHER_ADMIN_VERIFY_PATH}", actionOnEmptyResult=True, timeout=10)
        gather.say("Please enter your pin")
        response.append(gather)
        return response

    def process_gather_admin_verify(self, request: Request) -> TwiML:

        admin_service = AdminService(self.session)
        admin_call = admin_service.find_admin_call(self.name, self.get_call_id(request))
        if admin_call is None:
            return self.hangup()
        pin = request.form.get('Digits', None)

        if not admin_service.verify_admin_call(admin_call, pin):
            return self.hangup("Invalid Pin")

        scheduled_call = admin_service.find_scheduled_call(admin_call.user)
        if scheduled_call is not None:
            return self.process_scheduled_call(request, admin_call, scheduled_call)

        return self.gather_admin_ani(admin_call.user)

    def process_gather_admin_ani(self, request: Request) -> TwiML:
        admin_call = self.admin_service.find_admin_call(self.name, self.get_call_id(request))

        if not self.verified_admin_call(admin_call):
            return self.hangup()
        admin_user = admin_call.user

        ani = request.form.get('Digits', None)
        ivr_logger.debug(f"ani input: {ani}")
        if len(ani) < 10:
            admin_shortcut = self.admin_service.find_shortcut_ani(ani)
            if admin_shortcut is None:
                return self.gather_admin_ani(admin_user, invalid=True)
            ani = admin_shortcut.full_number
        elif admin_user.role == AdminRole.admin:
            if len(ani) == 10:
                ani = f"1{ani}"
        else:
            return self.gather_admin_ani(admin_user, invalid=True)
        ivr_logger.debug(f"ani: {ani}")
        self.admin_service.add_ani(admin_call, ani)

        return self.gather_admin_dnis(admin_user)

    def process_gather_admin_dnis(self, request: Request) -> TwiML:
        admin_call = self.admin_service.find_admin_call(self.name, self.get_call_id(request))

        if not self.verified_admin_call(admin_call):
            return self.hangup()

        admin_user = admin_call.user

        dnis = request.form.get('Digits', None)
        ivr_logger.debug(f"dnis input: {dnis}")
        if len(dnis) < 10:
            admin_shortcut = self.admin_service.find_shortcut_dnis(dnis)
            if admin_shortcut is None:
                return self.gather_admin_dnis(admin_user, invalid=True)
            dnis = admin_shortcut.full_number
        elif admin_user.role == AdminRole.admin:
            if len(dnis) == 10:
                dnis = f"1{dnis}"
        else:
            return self.gather_admin_dnis(admin_user, invalid=True)

        ivr_logger.debug(f"dnis: {dnis}")
        call_routings = self.call_service.get_routings_for_number(dnis)
        if len(call_routings) == 0:
            return self.gather_admin_dnis(admin_user, invalid=True)

        self.admin_service.add_dnis(admin_call, dnis)

        if len(call_routings) == 1:
            return self.process_admin_call(request, admin_call, call_routings[0])

        return self.gather_admin_routing()

    def process_gather_admin_routing(self, request: Request) -> TwiML:
        admin_call = self.admin_service.find_admin_call(self.name, self.get_call_id(request))

        if not self.verified_admin_call(admin_call):
            return self.hangup()

        digits = request.form.get('Digits', None)

        priority = int(digits)
        ivr_logger.debug(f"priority: {priority}")
        call_routings = self.call_service.get_routings_for_number(admin_call.dnis)
        routing = None
        for call_routing in call_routings:
            if call_routing.priority == priority:
                routing = call_routing
        if routing is None:
            ivr_logger.debug(f"invalid routing priority: {digits}")
            return self.gather_admin_routing(invalid=True)
        return self.process_admin_call(request, admin_call, routing)

    def process_scheduled_call(self, request: Request, admin_call: AdminCall, scheduled_call: ScheduledCall) -> TwiML:
        self.admin_service.copy_admin_from_scheduled(admin_call, scheduled_call)
        if scheduled_call.inbound_routing:
            return self.process_admin_call(request, admin_call, scheduled_call.inbound_routing)

        call = self.call_service.create_call_from_scheduled_call(scheduled_call)

        return self.process_call_leg(request, call.contact_legs[0])
