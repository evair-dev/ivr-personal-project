from flask import request, Response
from flask_restx import Namespace

from ivr_gateway.api.v1.resources import APIV1TwilioResource
from ivr_gateway.utils import returns_twiml

ns = Namespace(name="twilio", description="Twilio API")


@ns.route('/new')
class TwilioNewCallResource(APIV1TwilioResource):
    @returns_twiml
    def post(self):
        return self.twilio_adapter.new_call(request)


@ns.route('/transfer')
class TwilioTransferCallResource(APIV1TwilioResource):
    @returns_twiml
    def post(self):
        return self.twilio_adapter.transfer_call_in(request)


@ns.route('/continue')
class TwilioContinueCallResource(APIV1TwilioResource):
    @returns_twiml
    def post(self):
        return self.twilio_adapter.continue_call(request)


@ns.route('/status')
class TwilioStatusCallResource(APIV1TwilioResource):
    def post(self):
        self.twilio_adapter.update_call_status(request)
        return Response("", status=204)


@ns.route('/admin/login')
class TwilioAdminLoginResource(APIV1TwilioResource):
    @returns_twiml
    def post(self):
        return self.twilio_adapter.process_gather_admin_login(request)


@ns.route('/admin/verify')
class TwilioAdminVerifyResource(APIV1TwilioResource):
    @returns_twiml
    def post(self):
        return self.twilio_adapter.process_gather_admin_verify(request)


@ns.route('/admin/ani')
class TwilioAdminAniResource(APIV1TwilioResource):
    @returns_twiml
    def post(self):
        return self.twilio_adapter.process_gather_admin_ani(request)


@ns.route('/admin/dnis')
class TwilioAdminDnisResource(APIV1TwilioResource):
    @returns_twiml
    def post(self):
        return self.twilio_adapter.process_gather_admin_dnis(request)


@ns.route('/admin/routing')
class TwilioAdminRoutingResource(APIV1TwilioResource):
    @returns_twiml
    def post(self):
        return self.twilio_adapter.process_gather_admin_routing(request)









