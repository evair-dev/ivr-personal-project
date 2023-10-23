from unittest.mock import Mock
from sqlalchemy import orm

from ivr_gateway.engines.steps import StepEngine
from ivr_gateway.models.steps import StepRun
from ivr_gateway.steps.api.v1 import CopySessionVariable
from ivr_gateway.steps.config import Step
from ivr_gateway.steps.result import StepSuccess

from tests.unit.steps import BaseStepTestMixin


class TestCopySessionVariableStep(BaseStepTestMixin):

    def test_running_copy_session_variable_step(self, db_session: orm.Session):
        step_template = Step(
            name="step-1",
            step_type=CopySessionVariable.get_type_string(),
            step_kwargs={
                "existing_field": "session.some_field",
                "new_field_name": "copy_of_some_field"
            }
        )

        call, \
        call_leg, \
        call_routing, \
        greeting, \
        workflow, \
        workflow_run, \
        step = self.create_test_objects_for_step_template(db_session, step_template)

        mock_is_valid_step_branch = Mock()
        mock_is_valid_step_branch.return_value = True
        workflow_run.is_valid_step_branch = mock_is_valid_step_branch
        workflow_run.store_session_variable("some_field", "1234")

        engine = StepEngine(db_session, workflow_run)
        engine.initialize(step)
        result = engine.run_step()
        assert isinstance(result, StepSuccess)
        step_run: StepRun = db_session.query(StepRun).first()
        assert not step_run.state.error
        assert step_run.workflow_run.session["copy_of_some_field"] == "1234"
