from ddtrace import tracer
from sqlalchemy import orm

from ivr_gateway.services.amount.card_activation import CardActivationService
from ivr_gateway.steps.api.v1.base import APIV1Step
from ivr_gateway.steps.result import StepResult, StepSuccess, StepError


SERVICE_DIRECTORY = {
    "amount": {
        "activate_card": CardActivationService,
    },
}


class CallExternalServiceStep(APIV1Step):
    """
    Step used to hit external API from workflow
    """

    def __init__(self, name: str, partner: str, service: str, *args, **kwargs):
        self.partner = partner
        self.service = service
        kwargs.update({
            "partner": partner,
            "service": service
        })
        super().__init__(name, *args, **kwargs)

    @tracer.wrap()
    def run(self, db_session: orm.Session) -> StepResult:  # pragma: no cover
        workflow_run = self.step_run.workflow_run
        service = SERVICE_DIRECTORY.get(self.partner).get(self.service)(db_session, workflow_run.contact_leg.contact)
        success, msg = service(workflow_run)

        if success:
            return self.save_result(result=StepSuccess(result=msg))
        else:
            raise self.save_result(result=StepError(msg))
