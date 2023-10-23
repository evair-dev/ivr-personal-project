import os

from flask import request
from flask_restx import Namespace
import xml.etree.ElementTree as ET  # nosec


from ivr_gateway.api.v1.resources import APIV1AdminResource
from ivr_gateway.utils import returns_xml

ns = Namespace(name="telco", description="Telco API")


@ns.route('/transfer_lookup')
class TransferCallResource(APIV1AdminResource):
    @returns_xml
    def post(self):
        result = ET.Element('result')
        ani = request.form.get("ani", None)
        dnis = request.form.get("dnis", None)
        api_key = request.form.get("api_key", None)
        env_api_key = os.getenv("TRANSFER_API_KEY", None)
        if ani is None or dnis is None or api_key is None or api_key != env_api_key:
            return result
        full_ani = ani if len(ani) > 10 else f"1{ani}"
        full_dnis = dnis if len(dnis) > 10 else f"1{dnis}"
        maybe_call, no_call_reason = self.call_service.get_recent_transferred_call(full_ani, full_dnis)

        response_type = ET.SubElement(result, 'type')
        if maybe_call is None:
            response_type.text = 'no_matching_call'
            reason = ET.SubElement(result, 'reason')
            reason.text = no_call_reason
            return result
        call_id = ET.SubElement(result, 'call_id')
        call_id.text = maybe_call.global_id

        if maybe_call.customer_id is None:
            response_type.text = "unknown_customer"
            return result

        customer_id = ET.SubElement(result, 'customer_id')
        customer_id.text = maybe_call.customer_id

        if maybe_call.secured_key is None:
            response_type.text = 'known_customer'
            return result

        response_type.text = 'secured'
        secure_key = ET.SubElement(result, 'secure_key')
        secure_key.text = maybe_call.secured_key

        return result


