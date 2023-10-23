from unittest.mock import Mock

from sqlalchemy import orm

from ivr_gateway.engines.steps import StepEngine, StepEngineState
from ivr_gateway.models.steps import StepRun
from ivr_gateway.steps.api.v1 import BranchMapWorkflowStep
from ivr_gateway.steps.config import Step
from ivr_gateway.steps.result import StepSuccess

from tests.unit.steps import BaseStepTestMixin


class TestBranchStep(BaseStepTestMixin):

    def test_running_branch_step(self, db_session: orm.Session):
        step_template = Step(
            name="step-1",
            step_type=BranchMapWorkflowStep.get_type_string(),
            step_kwargs={
                "field": "session.session_variable",
                "on_error_reset_to_step": "step-0",
                "branches": {
                    "test_value": "branch-1",
                },
            },
        )
        call, \
            call_leg, \
            call_routing, \
            greeting, \
            workflow, \
            workflow_run, \
            step = self.create_test_objects_for_step_template(db_session, step_template, workflow_session={
                "session_variable": "test_value",
            }
                                                          )
        mock_is_valid_step_branch = Mock()
        mock_is_valid_step_branch.return_value = True
        workflow_run.is_valid_step_branch = mock_is_valid_step_branch
        engine = StepEngine(db_session, workflow_run)
        engine.initialize(step)
        result = engine.run_step()
        assert isinstance(result, StepSuccess)
        step_run: StepRun = db_session.query(StepRun).first()
        assert not step_run.state.error
        assert step_run.state.result["value"] == "branch-1"
        mock_is_valid_step_branch.assert_called_once_with("branch-1")
        assert engine.state == StepEngineState.step_complete
