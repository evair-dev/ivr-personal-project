import pytest
from unittest.mock import Mock

from sqlalchemy import orm
from typing import List, Any

from ivr_gateway.engines.steps import StepEngine
from ivr_gateway.models.steps import StepRun
from ivr_gateway.steps.api.v1 import BooleanLogicStep
from ivr_gateway.steps.config import Step
from ivr_gateway.steps.result import StepSuccess, StepError

from tests.unit.steps import BaseStepTestMixin


class TestBranchStep(BaseStepTestMixin):
    def prepare_single_step_boolean_engine(self, db_session: orm.Session, fieldset: List,
                                           result_field: str, op: str, session_variable: Any = None):
        step_template = Step(
            name="step-1",
            step_type=BooleanLogicStep.get_type_string(),
            step_kwargs={
                "fieldset": fieldset,
                "result_field": result_field,
                "op": op
            }
        )
        call, \
            call_leg, \
            call_routing, \
            greeting, \
            workflow, \
            workflow_run, \
            step = self.create_test_objects_for_step_template(db_session, step_template, workflow_session={
                "session_variable": session_variable,
            }
                                                          )
        mock_is_valid_step_branch = Mock()
        mock_is_valid_step_branch.return_value = True
        workflow_run.is_valid_step_branch = mock_is_valid_step_branch
        engine = StepEngine(db_session, workflow_run)
        engine.initialize(step)
        return engine, workflow_run

    def test_running_branch_step(self, db_session: orm.Session):
        engine, workflow_run = self.prepare_single_step_boolean_engine(
            db_session,
            fieldset=["session.session_variable"],
            op="nonnull",
            result_field="is_null",
            session_variable="test_value"
        )
        result = engine.run_step()
        assert isinstance(result, StepSuccess)
        step_run: StepRun = db_session.query(StepRun).first()
        assert not step_run.state.error
        assert step_run.state.result["value"] is True
        assert workflow_run.session.get("is_null") is True

    def test_running_branch_step_with_static_true(self, db_session: orm.Session):
        engine, workflow_run = self.prepare_single_step_boolean_engine(
            db_session,
            fieldset=[1, "session.session_variable"],
            op=">",
            result_field="one_is_greater_than_variable",
            session_variable=2
        )
        result = engine.run_step()
        assert isinstance(result, StepSuccess)
        step_run: StepRun = db_session.query(StepRun).first()
        assert not step_run.state.error
        assert step_run.state.result["value"] is False
        assert workflow_run.session.get("one_is_greater_than_variable") is False

    def test_running_branch_step_with_static_false(self, db_session: orm.Session):
        engine, workflow_run = self.prepare_single_step_boolean_engine(
            db_session,
            fieldset=["session.session_variable", 1],
            op=">",
            result_field="variable_greater_than_one",
            session_variable=2
        )
        result = engine.run_step()
        assert isinstance(result, StepSuccess)
        step_run: StepRun = db_session.query(StepRun).first()
        assert not step_run.state.error
        assert step_run.state.result["value"] is True
        assert workflow_run.session.get("variable_greater_than_one") is True

    def test_running_branch_step_type_error(self, db_session: orm.Session):
        op = "<="
        f1 = 2
        f2 = "bad_static_value"
        engine, _ = self.prepare_single_step_boolean_engine(
            db_session,
            fieldset=["session.session_variable", f2],
            op=op,
            result_field="type_error",
            session_variable=f1
        )
        with pytest.raises(StepError) as err:
            engine.run_step()
        assert err.value.msg == f"Cannot perform {op} operation in boolean logic step on values" \
                                f" of types {str(type(f1))} and {str(type(f2))}"

    def test_running_branch_step_non_bool_error(self, db_session: orm.Session):
        op = "||"
        engine, _ = self.prepare_single_step_boolean_engine(
            db_session,
            fieldset=[2, 3],
            op=op,
            result_field="non_bool_error",
        )
        with pytest.raises(StepError) as err:
            engine.run_step()
        assert err.value.msg == f"Non-boolean result of {op} operation in boolean logic step"
