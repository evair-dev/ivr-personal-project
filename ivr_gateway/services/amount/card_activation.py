import requests
from ddtrace import tracer
from sqlalchemy import orm
from json import JSONDecodeError

from ivr_gateway.models.workflows import WorkflowRun
from ivr_gateway.models.contacts import Contact
from ivr_gateway.services.amount import AmountService
from ivr_gateway.api.exceptions import AmountCardActivationException
from ivr_gateway.utils import get_partner_namespaced_environment_variable


class CardActivationService(AmountService):
    def __init__(self, db_session: orm.Session, contact: Contact):
        super().__init__(db_session=db_session, contact=contact)
        self.auth_endpoint = f"{self.base_url}/api/account_management/auth/token"
        self.activation_endpoint = f"{self.base_url}/api/account_management/webhook/activate_card"
        self.secret = get_partner_namespaced_environment_variable(partner=self.partner,
                                                                  field="AMOUNT_CARD_ACTIVATION_SECRET")

    def __call__(self, workflow_run: WorkflowRun):
        try:
            access_token = self._get_authentication_token()
        except AmountCardActivationException:
            return False, "Card activation failed"

        session = workflow_run.session
        post_body = {"data": {
            "credit_card_account_id": session.get("credit_card_account_id"),
            "ssn_last_4": session.get("ssn_last_4"),
            "card_last_4": session.get("card_last_4")
        }}

        with tracer.trace('amount_service.api.account_management.webhook.activation_card'):
            def request():
                return requests.post(self.activation_endpoint, headers={"Authorization": f"Bearer {access_token}"},
                                     json=post_body, timeout=self.timeout)
            exception_occurred, response = self._attempt_request(
                request=request,
                amount_endpoint=self.activation_endpoint,
                tag_name="amount_service.activation_card.status_code",
                exception_result=(False, "Card activation failed"))
            if exception_occurred:
                return response
        try:
            data = response.json()
            self.log_response(request_name="card_activation_service.activate_card", response=response)
        except JSONDecodeError:
            self.log_response(request_name="activate_card", response=response,
                              error_message=f"Error encountered activating card. Expected JSON "
                                            f"format back. Got {response.headers.get('content-type')} instead.")
            return False, "Card activation failed"

        if data.get("message") == "ok":
            return True, "ok"
        else:
            return False, "Card activation failed"
