import os
from typing import Dict

import requests
from ddtrace import tracer
from sqlalchemy import orm
from json import JSONDecodeError

from ivr_gateway.models.workflows import WorkflowRun
from ivr_gateway.services.amount import AmountService, AvantBasicError
from ivr_gateway.services.workflows.exceptions import MissingDependentValueException


class WorkflowRunnerService(AmountService):
    SECURE_CALL_ENDPOINT = '/api/v1/workflows/ivr/secure_call_ivr'
    LOAN_ENDPOINT = "/api/v1/workflows/product/loan"
    BASE_ENDPOINT = os.getenv('IVR_AMOUNT_BASE_URL')

    field_dependency = {
        'make_payment': ['loan_id']
    }

    def __init__(self, db_session: orm.Session):
        super().__init__(db_session)

    def run_step(self, workflow_run: WorkflowRun) -> Dict:
        url = workflow_run.session.get("Iivr_basic_workflow_url")
        state = workflow_run.session.get("state")
        amount_state = {"state": state}

        with tracer.trace('amount_service.api.v1.workflows'):
            def request():
                return requests.post(url, json=amount_state, headers=self.get_headers(workflow_run),
                                     timeout=self.timeout)
            exception_occurred, response = self._attempt_request(
                request=request,
                amount_endpoint=url,
                tag_name="amount_service.workflows.status_code")
            if exception_occurred:
                return response
        try:
            json = response.json()
        except JSONDecodeError:
            raise AvantBasicError()
        return json

    def get_url(self, workflow_run: WorkflowRun, workflow_name: str):
        if workflow_name == 'secure_call':
            return f'{self.BASE_ENDPOINT}{self.SECURE_CALL_ENDPOINT}'
        if workflow_name == 'make_payment':
            loan_id = workflow_run.session.get("loan_id")
            if loan_id is None:
                raise MissingDependentValueException()
            return f'{self.BASE_ENDPOINT}{self.LOAN_ENDPOINT}/{loan_id}/make_payment'

    def get_headers(self, workflow_run: WorkflowRun) -> Dict[str, str]:
        workflow_name = workflow_run.session.get("Iivr_basic_workflow_name")
        headers = self.headers.copy()
        if workflow_name == "make_payment":
            headers.update({
                "customer_id": str(workflow_run.session.get("customer_id"))
            })
        return headers

    def get_initial_state(self, workflow_run: WorkflowRun) -> Dict[str, int]:
        workflow_name = workflow_run.session.get("Iivr_basic_workflow_name")
        if workflow_name == "secure_call":
            workflow_session_state = {
                "customer_id": int(workflow_run.session.get("customer_id", 0))
            }
        else:
            workflow_session_state = {
                "product_id": int(workflow_run.session.get("loan_id", 0))
            }
        return workflow_session_state
