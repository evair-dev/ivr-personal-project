from sqlalchemy import orm

from ivr_gateway.engines.steps import StepEngine, StepEngineState
from ivr_gateway.models.steps import StepRun
from ivr_gateway.steps.api.v1 import NoopStep
from ivr_gateway.steps.config import Step
from ivr_gateway.steps.result import StepSuccess
from tests.unit.steps import BaseStepTestMixin


class TestNoopStep(BaseStepTestMixin):

    def test_running_noop_step(self, db_session: orm.Session):
        step_template = Step(
            name="step-1",
            step_type=NoopStep.get_type_string(),
            step_kwargs={}
        )
        call, \
            call_leg, \
            call_routing, \
            greeting, \
            workflow, \
            workflow_run, \
            step = self.create_test_objects_for_step_template(db_session, step_template)
        engine = StepEngine(db_session, workflow_run)
        engine.initialize(step)
        result = engine.run_step()
        assert isinstance(result, StepSuccess)
        step_run: StepRun = db_session.query(StepRun).first()
        assert not step_run.state.error
        assert step_run.state.result["value"] is None
        assert engine.state == StepEngineState.step_complete