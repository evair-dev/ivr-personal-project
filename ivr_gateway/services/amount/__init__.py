import os

from typing import Tuple, Optional, Dict, Callable, Any

from ddtrace import tracer
from sqlalchemy import orm
import requests
from requests.exceptions import HTTPError, Timeout, ConnectionError
from json import JSONDecodeError

from ivr_gateway.logger import ivr_logger
from ivr_gateway.models.contacts import Contact
from ivr_gateway.models.enums import Partner
from ivr_gateway.utils import get_partner_namespaced_environment_variable
from ivr_gateway.models.vendors import VendorResponse
from ivr_gateway.api.exceptions import AmountCardActivationException


class AmountService:
    client_version = os.getenv('IVR_AMOUNT_CLIENT_VERSION')
    client_install = os.getenv('IVR_AMOUNT_CLIENT_INSTALL')
    timeout = 5

    headers = {"Client-Version": client_version,
               "Client-Install": client_install}

    def __init__(self, db_session: orm.Session, contact: Contact = None):
        self.db_session = db_session
        if contact:
            self.partner = self._get_partner_if_exists(contact)
            if self.partner:
                self.base_url = get_partner_namespaced_environment_variable(partner=self.partner,
                                                                            field="AMOUNT_BASE_URL")
            else:
                raise TypeError("No partner associated with this contact.")
        self.auth_endpoint = None
        self.secret = None

    @staticmethod
    def _get_partner_if_exists(contact: Contact) -> Optional[Partner]:
        if len(contact.contact_legs) == 0:
            return None
        if contact.contact_legs[0].initial_queue is None:
            return None
        return contact.contact_legs[0].initial_queue.partner

    def _attempt_request(
            self,
            request: Callable[[], Dict],
            amount_endpoint: str,
            tag_name: str,
            exception_result: Optional[Any] = None,
            contact: Optional[Contact] = None,
    ) -> Tuple[bool, Any]:
        try:
            response = request()
            span = tracer.current_span()
            span.set_tag(tag_name, response.status_code)
            ivr_logger.warning(f"Amount Service: {tag_name}, status_code: {response.status_code}")
            response.raise_for_status()
        except (HTTPError, Timeout, ConnectionError) as e:
            ivr_logger.error(f"{e.__class__.__name__} for {amount_endpoint}")
            if contact is not None:
                contact.session["customer_summary"] = {}
                self.db_session.add(contact)
                self.db_session.commit()
            if exception_result is None:
                raise AvantBasicError()
            return True, exception_result
        ivr_logger.info(f"successful response for {amount_endpoint}")
        return False, response

    def _get_authentication_token(self) -> str:

        with tracer.trace('amount_service.api.account_management.auth.token'):
            def request():
                return requests.post(self.auth_endpoint,
                                     headers={"Authorization": f"Basic {self.secret}"},
                                     timeout=self.timeout)
            exception_occurred, response = self._attempt_request(
                request=request,
                amount_endpoint=self.auth_endpoint,
                tag_name="amount_service.authentication.status_code",
                exception_result="")
            if exception_occurred:
                return response

        if response.status_code < 400:
            try:
                data = response.json()
                self.log_response("amount_service.get_authentication_token", response)
                return data.get("access_token")
            except JSONDecodeError:
                self.log_response("amount_service.get_authentication_token", response,
                                  error_message=f"Error encountered fetching authentication token. Expected JSON "
                                                f"format back. Got {response.headers.get('content-type')} instead.")
                raise AmountCardActivationException
        else:
            self.log_response("amount_service.get_authentication_token", response)
            raise AmountCardActivationException

    def log_response(self, request_name, response, error_message=None):
        if error_message:
            self.db_session.add(VendorResponse(vendor="amount",
                                               request_name=request_name,
                                               response_time=response.elapsed.total_seconds(),
                                               status_code=400,
                                               headers=dict(response.headers),
                                               error=error_message)
                                )
        else:
            self.db_session.add(VendorResponse(vendor="amount",
                                               request_name=request_name,
                                               response_time=response.elapsed.total_seconds(),
                                               status_code=response.status_code,
                                               headers=dict(response.headers),
                                               error="" if response.reason == "OK" else response.text)
                                )
        self.db_session.commit()


class AvantBasicError(Exception):
    pass
