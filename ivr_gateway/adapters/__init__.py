from abc import abstractmethod

import sqlalchemy.orm
from flask import Request
from twilio.twiml.voice_response import TwiML

from ivr_gateway.exit_paths import ExitPath
from ivr_gateway.logger import ivr_logger
from ivr_gateway.models.admin import AdminCall, AdminUser, AdminPhoneNumber
from ivr_gateway.models.contacts import ContactLeg, InboundRouting
from ivr_gateway.services.admin import AdminService
from ivr_gateway.services.calls import CallService
from ivr_gateway.models.enums import OperatingMode
from ivr_gateway.services.queues import QueueService, QueueStatusService
from ivr_gateway.services.sms import SmsService
from ivr_gateway.api.exceptions import MissingInboundRoutingException


class BaseCallAdapter:

    def __init__(self, name: str, vendor_url: str, base_url: str, session: sqlalchemy.orm.Session):
        self.vendor_url = vendor_url
        self.name = name
        self.session = session
        self.base_url = base_url
        self.call_service = CallService(self.session)
        self.queue_service = QueueService(self.session)
        self.queue_status_service = QueueStatusService(self.call_service, self.queue_service)
        self.admin_service = AdminService(self.session)

    def new_call(self, request: Request) -> TwiML:
        """
        Entry point for handling new calls. This is the entry point for all calls
        :param request:
        :return:
        """
        call_service = CallService(self.session)
        admin_service = AdminService(self.session)
        system_operating_mode = call_service.get_system_operating_mode()
        ani = self.get_calling_party(request)
        # Determine if we have an admin user / phone number calling in

        maybe_admin_phone_number = admin_service.find_admin_phone_number(ani)

        if system_operating_mode == OperatingMode.EMERGENCY:
            if maybe_admin_phone_number:
                return self.process_new_admin_call(request, maybe_admin_phone_number)
            else:
                # TODO: Handle emergency routing
                # Things be FOOBAR, play message, maybe we will have routing someday
                return self.hangup(self.call_service.get_system_wide_emergency_message())

        # Look up the called line and routing
        called_party_number = self.get_called_party(request)
        call_routing = call_service.get_routing_for_number(called_party_number)
        if call_routing is None:
            raise MissingInboundRoutingException("Resource not found.")
        # If we are handling an admin routing then swap to the admin flow
        if call_routing.admin:
            if maybe_admin_phone_number:
                return self.process_new_admin_call(request, maybe_admin_phone_number)
            else:
                # For numbers that are routed as "actual calls through 'new'", we should hangup
                # TODO: should we have a message here or just hangup?
                return self.hangup()

        call = call_service.create_call(self.name, self.get_call_id(request), call_routing, ani, called_party_number)
        call_legs = call.contact_legs
        # noinspection PyUnresolvedReferences
        call_leg = call_legs[0]
        return self.process_new_call(call_leg, call_routing, request)

    def process_new_call(self, call_leg: ContactLeg, routing: InboundRouting,
                         request: Request) -> TwiML:  # pragma: no cover
        """
        This is used as a lifecycle hook in the call processing on a new call event. Typically used to add
        a greeting to a new call event
        :param call_leg:
        :param routing:
        :param request:
        :return:
        """
        return self.process_call_leg(request, call_leg)

    @abstractmethod
    def process_call_leg(self, request: Request, call_leg: ContactLeg) -> TwiML:  # pragma: no cover
        """
        Method implemented by subclass to actually process the call leg
        :param call_leg:
        :param request:

        :return:
        """
        pass

    @abstractmethod
    def process_exit_path(self, request: Request, exit_path: ExitPath,
                          call_leg: ContactLeg = None) -> TwiML:  # pragma: no cover
        pass

    @abstractmethod
    def get_call_id(self, request: Request) -> str:  # pragma: no cover
        pass

    @abstractmethod
    def get_called_party(self, request: Request) -> str:  # pragma: no cover
        pass

    @abstractmethod
    def get_calling_party(self, request: Request) -> str:  # pragma: no cover
        pass

    @abstractmethod
    def transfer_call_in(self, request: Request) -> TwiML:  # pragma: no cover
        pass

    def continue_call(self, request: Request) -> TwiML:
        call_id = self.get_call_id(request)
        # Logging this guy here rather than in the specific call adapter b/c we don't really have a hook to log this
        # elsewhere
        ivr_logger.warning(f"BaseAdapter.continue_call, call: {call_id}")
        call_leg = self.call_service.get_active_call_leg_for_call_system_and_id(self.name, call_id)
        return self.process_call_leg(request, call_leg)

    @abstractmethod
    def update_call_status(self, request: Request):
        pass

    @abstractmethod
    def hangup(self, message: str = None) -> TwiML:  # pragma: no cover
        pass

    @abstractmethod
    def verify_call_auth(self, request: Request):  # pragma: no cover
        pass

    def process_new_admin_call(self, request: Request, admin_phone_number: AdminPhoneNumber):
        admin_service = AdminService(self.session)
        ani = self.get_calling_party(request)
        dnis = self.get_called_party(request)

        admin_user = admin_phone_number.user
        if admin_user is None:
            return self.gather_admin_login(request)

        admin_service.create_admin_call(
            self.name, self.get_call_id(request), admin_user, ani, dnis
        )
        return self.gather_admin_verify(request)

    @abstractmethod
    def gather_admin_login(self, request: Request) -> TwiML:  # pragma: no cover
        pass

    @abstractmethod
    def process_gather_admin_login(self, request: Request) -> TwiML:  # pragma: no cover
        pass

    @abstractmethod
    def gather_admin_verify(self, request: Request) -> TwiML:  # pragma: no cover
        pass

    @abstractmethod
    def process_gather_admin_verify(self, request: Request) -> TwiML:  # pragma: no cover
        pass

    @abstractmethod
    def gather_admin_ani(self, admin_user: AdminUser, invalid=False) -> TwiML:  # pragma: no cover
        pass

    @abstractmethod
    def process_gather_admin_ani(self, request: Request) -> TwiML:  # pragma: no cover
        pass

    @abstractmethod
    def gather_admin_dnis(self, admin_user: AdminUser, invalid=False) -> TwiML:  # pragma: no cover
        pass

    @abstractmethod
    def process_gather_admin_dnis(self, request: Request) -> TwiML:  # pragma: no cover
        pass

    @abstractmethod
    def gather_admin_routing(self, invalid=False) -> TwiML:  # pragma: no cover
        pass

    @abstractmethod
    def process_gather_admin_routing(self, request: Request) -> TwiML:  # pragma: no cover
        pass

    def process_admin_call(self, request: Request, admin_call: AdminCall, routing: InboundRouting) -> TwiML:
        """
        Used to initiate an admin call session
        :param request:
        :param admin_call:
        :param routing:
        :return:
        """
        admin_service = AdminService(self.session)
        admin_service.add_call_routing(admin_call, routing)

        call = self.call_service.create_call(admin_call.contact_system, admin_call.contact_system_id, routing,
                                             admin_call.ani, admin_call.dnis)
        call.admin_call = admin_call

        return self.process_new_call(call.contact_legs[0], routing, request)


class BaseSMSAdapter:

    def __init__(self, name: str, vendor_url: str, base_url: str, session: sqlalchemy.orm.Session):
        self.vendor_url = vendor_url
        self.name = name
        self.session = session
        self.base_url = base_url
        self.sms_service = SmsService(self.session)
        self.queue_service = QueueService(self.session)
        self.admin_service = AdminService(self.session)

    def continue_or_create_sms(self, request: Request):
        sms_id = self.get_contact_id(request)
        # Logging this guy here rather than in the specific sms adapter b/c we don't really have a hook to log this
        # elsewhere
        ivr_logger.warning(f"BaseSMSAdapter.continue_or_create_sms, sms: {sms_id}")
        contact_leg = self.sms_service.get_active_contact_leg_for_sms_system_and_id(self.name, sms_id)
        if contact_leg is None:
            return self.new_sms(request)
        return self.process_sms_leg(request, contact_leg)

    def new_sms(self, request: Request):
        """
        Entry point for handling new sms contacts.
        :param request:
        :return:
        """
        device = self.get_device_identifier(request)
        target = self.get_inbound_target(request)
        inbound_routing = self.sms_service.get_routing_for_number(target)
        initial_settings = self.get_initial_settings(request)

        sms = self.sms_service.create_sms_contact(self.name, self.get_contact_id(request), inbound_routing, device,
                                                  target, initial_settings)
        sms_legs = sms.contact_legs
        # noinspection PyUnresolvedReferences
        sms_leg = sms_legs[0]
        return self.process_new_sms(sms_leg, inbound_routing, request)

    def process_new_sms(self, contact_leg: ContactLeg, routing: InboundRouting, request: Request):  # pragma: no cover
        """
        This is used as a lifecycle hook in the contact processing on a new sms event. Typically used to add
        a greeting to a new contact event
        :param contact_leg:
        :param routing:
        :param request:
        :return:
        """
        return self.process_sms_leg(request, contact_leg)

    @abstractmethod
    def process_sms_leg(self, request: Request, sms_leg: ContactLeg):  # pragma: no cover
        """
        Method implemented by subclass to actually process the sms leg
        :param sms_leg:
        :param request:

        :return:
        """
        pass

    @abstractmethod
    def process_exit_path(self, request: Request, exit_path: ExitPath,
                          sms_leg: ContactLeg = None):  # pragma: no cover
        pass

    @abstractmethod
    def get_contact_id(self, request: Request) -> str:  # pragma: no cover
        pass

    @abstractmethod
    def get_inbound_target(self, request: Request) -> str:  # pragma: no cover
        pass

    @abstractmethod
    def get_device_identifier(self, request: Request) -> str:  # pragma: no cover
        pass

    @abstractmethod
    def get_initial_settings(self, request: Request) -> dict:  # pragma: no cover
        pass

    def continue_sms(self, request: Request):
        sms_id = self.get_contact_id(request)
        # Logging this guy here rather than in the specific sms adapter b/c we don't really have a hook to log this
        # elsewhere
        ivr_logger.warning(f"BaseSMSAdapter.continue_sms, sms: {sms_id}")
        contact_leg = self.sms_service.get_active_contact_leg_for_sms_system_and_id(self.name, sms_id)
        return self.process_sms_leg(request, contact_leg)

    @abstractmethod
    def verify_sms_auth(self, request: Request):  # pragma: no cover
        pass
