from typing import Optional

from ddtrace import tracer
from flask import request, has_request_context
from sqlalchemy import orm

from ivr_gateway.adapters.exceptions import InvalidAuthenticationException
from ivr_gateway.adapters.livevox import LiveVoxRequestAdapter
from ivr_gateway.api.exceptions import InvalidAPIAuthenticationException
from ivr_gateway.adapters.twilio import TwilioRequestAdapter
from ivr_gateway.api import APIResource
from ivr_gateway.db import session_scope
from ivr_gateway.services.admin import AdminService
from ivr_gateway.services.calls import CallService
from ivr_gateway.services.queues import QueueService
from ivr_gateway.services.workflows import WorkflowService


class APIV1AdminResource(APIResource):
    _db_session: Optional[orm.Session] = None

    @property
    def admin_service(self) -> AdminService:
        return AdminService(self.get_db_session())

    @property
    def workflow_service(self) -> WorkflowService:
        return WorkflowService(self.get_db_session())

    @property
    def call_service(self) -> CallService:
        return CallService(self.get_db_session())

    @property
    def queue_service(self) -> QueueService:
        return QueueService(self.get_db_session())


class APIV1TwilioResource(APIResource):
    _db_session: Optional[orm.Session] = None
    _twilio_adapter: Optional[TwilioRequestAdapter] = None

    def dispatch_request(self, *args, **kwargs):
        with session_scope() as session:
            self._db_session = session

            try:
                self.twilio_adapter.verify_call_auth(request)

                span = tracer.current_span()
                if span is not None:
                    call_sid = self._twilio_adapter.get_call_id(request)
                    span.set_tag('CallSid', call_sid)
                    if has_request_context():
                        request_id = request.environ.get("HTTP_X_REQUEST_ID")
                        if request_id is not None:
                            span.set_tag('request_id', request_id)
            except InvalidAuthenticationException as e:
                raise InvalidAPIAuthenticationException(*e.args)

            return super().dispatch_request(*args, **kwargs)

    @property
    def twilio_adapter(self) -> TwilioRequestAdapter:
        if self._twilio_adapter is None:
            self._twilio_adapter = TwilioRequestAdapter(
                "twilio", "www.twilio.com", "/api/v1/twilio", self.get_db_session()
            )
        return self._twilio_adapter


class APIV1LiveVoxSMSResource(APIResource):
    _db_session: Optional[orm.Session] = None
    _livevox_sms_adapter: Optional[LiveVoxRequestAdapter] = None

    def dispatch_request(self, *args, **kwargs):
        with session_scope() as session:
            self._db_session = session

            try:
                self.livevox_sms_adapter.verify_sms_auth(request)

                span = tracer.current_span()
                if span is not None:
                    call_sid = self._livevox_sms_adapter.get_contact_id(request)
                    span.set_tag('CallSid', call_sid)
                    if has_request_context():
                        request_id = request.environ.get("HTTP_X_REQUEST_ID")
                        if request_id is not None:
                            span.set_tag('request_id', request_id)
            except InvalidAuthenticationException as e:
                raise InvalidAPIAuthenticationException(*e.args)

            return super().dispatch_request(*args, **kwargs)

    @property
    def livevox_sms_adapter(self) -> LiveVoxRequestAdapter:
        if self._livevox_sms_adapter is None:
            self._livevox_sms_adapter = LiveVoxRequestAdapter(
                "livevox", "www.livevox.com", "/api/v1/livevox", self.get_db_session()
            )
        return self._livevox_sms_adapter
