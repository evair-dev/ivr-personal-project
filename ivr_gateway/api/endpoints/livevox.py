from flask import request
from flask_restx import Namespace

from ivr_gateway.api.v1.resources import APIV1LiveVoxSMSResource

ns = Namespace(name="livevox", description="LiveVox API")


@ns.route('/sms')
class LiveVoxCombinationSmsResource(APIV1LiveVoxSMSResource):
    def post(self):
        return self.livevox_sms_adapter.continue_or_create_sms(request)


@ns.route('/new')
class LiveVoxNewSmsResource(APIV1LiveVoxSMSResource):
    def post(self):
        return self.livevox_sms_adapter.new_sms(request)


@ns.route('/continue')
class LiveVoxContinueSMSResource(APIV1LiveVoxSMSResource):
    def post(self):
        return self.livevox_sms_adapter.continue_sms(request)
