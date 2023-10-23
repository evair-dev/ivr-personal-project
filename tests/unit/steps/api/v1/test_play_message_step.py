import calendar
import datetime

from sqlalchemy import orm

from ivr_gateway.engines.steps import StepEngine, StepEngineState
from ivr_gateway.models.steps import StepRun
from ivr_gateway.steps.api.v1 import PlayMessageStep
from ivr_gateway.steps.config import Step
from ivr_gateway.steps.result import StepSuccess
from tests.unit.steps import BaseStepTestMixin


class TestPlayMessageStep(BaseStepTestMixin):

    def test_running_play_step(self, db_session: orm.Session):
        step_template = Step(
            name="step-1",
            step_type=PlayMessageStep.get_type_string(),
            step_kwargs={
                "fieldset": [
                    ("session.session_variable", "field1"),
                    ("session.session_dict.nested", "field2"),
                ],
                "template": "Var: {{ field1 }}, Nested Var: {{ field2 }}"
            }
        )
        expected_message = "Var: test_value, Nested Var: nested_value"
        call, \
        call_leg, \
        call_routing, \
        greeting, \
        workflow, \
        workflow_run, \
        step = self.create_test_objects_for_step_template(db_session, step_template, workflow_session={
            "session_variable": "test_value",
            "session_dict": {
                "nested": "nested_value"
            }
        })
        engine = StepEngine(db_session, workflow_run)
        engine.initialize(step)
        result = engine.run_step()
        assert isinstance(result, StepSuccess)
        step_run: StepRun = db_session.query(StepRun).first()
        assert not step_run.state.error
        assert step_run.state.result["value"] == expected_message
        assert engine.state == StepEngineState.step_complete

    def test_use_message_key(self, db_session: orm.Session, monkeypatch):
        monkeypatch.setenv("IVR_APP_ENV", "test")
        step_template = Step(
            name="step-1",
            step_type=PlayMessageStep.get_type_string(),
            step_kwargs={
                "fieldset": [
                    ("session.test_key", "field1"),
                ],
                "message_key": "test_templated_message"
            }
        )
        expected_message = "This is a message that uses the workflow session to say: Hello"
        call, \
            call_leg, \
            call_routing, \
            greeting, \
            workflow, \
            workflow_run, \
            step = self.create_test_objects_for_step_template(db_session, step_template, workflow_session={
                "test_key": "Hello",
            })
        engine = StepEngine(db_session, workflow_run)
        engine.initialize(step)
        result = engine.run_step()
        assert isinstance(result, StepSuccess)
        step_run: StepRun = db_session.query(StepRun).first()
        assert not step_run.state.error
        assert step_run.state.result["value"] == expected_message
        assert engine.state == StepEngineState.step_complete

    def test_currency_template_filter(self, db_session: orm.Session):
        step_template = Step(
            name="step-1",
            step_type=PlayMessageStep.get_type_string(),
            step_kwargs={
                "fieldset": [
                    ("session.currency", "cur_val"),
                ],
                "template": "Val: {{ cur_val|currency }}"
            }
        )
        currency_input = int("10000")  # 100 dollars (stored in cents)
        expected_message = f'Val: ${(currency_input / 100):.2f}'
        call, \
        call_leg, \
        call_routing, \
        greeting, \
        workflow, \
        workflow_run, \
        step = self.create_test_objects_for_step_template(db_session, step_template, workflow_session={
            "currency": currency_input
        })
        engine = StepEngine(db_session, workflow_run)
        engine.initialize(step)
        result = engine.run_step()
        assert isinstance(result, StepSuccess)
        step_run: StepRun = db_session.query(StepRun).first()
        assert not step_run.state.error
        assert step_run.state.result["value"] == expected_message
        assert engine.state == StepEngineState.step_complete

    def test_number_template_filter(self, db_session: orm.Session):
        step_template = Step(
            name="step-1",
            step_type=PlayMessageStep.get_type_string(),
            step_kwargs={
                "fieldset": [
                    ("session.number", "num_val"),
                ],
                "template": "Val: {{ num_val|grouped }}"
            }
        )
        expected_message = 'Val: 20000'
        call, \
        call_leg, \
        call_routing, \
        greeting, \
        workflow, \
        workflow_run, \
        step = self.create_test_objects_for_step_template(db_session, step_template, workflow_session={
            "number": "20000"
        })
        engine = StepEngine(db_session, workflow_run)
        engine.initialize(step)
        result = engine.run_step()
        assert isinstance(result, StepSuccess)
        step_run: StepRun = db_session.query(StepRun).first()
        assert not step_run.state.error
        assert step_run.state.result["value"] == expected_message
        assert engine.state == StepEngineState.step_complete

    def test_number_with_grouping_template_filter(self, db_session: orm.Session):
        step_template = Step(
            name="step-1",
            step_type=PlayMessageStep.get_type_string(),
            step_kwargs={
                "fieldset": [
                    ("session.number", "num_val"),
                ],
                "template": "Val: {{ num_val|grouped([2,3]) }}"
            }
        )
        expected_message = 'Val: 20 000'
        call, \
        call_leg, \
        call_routing, \
        greeting, \
        workflow, \
        workflow_run, \
        step = self.create_test_objects_for_step_template(db_session, step_template, workflow_session={
            "number": "20000"
        })
        engine = StepEngine(db_session, workflow_run)
        engine.initialize(step)
        result = engine.run_step()
        assert isinstance(result, StepSuccess)
        step_run: StepRun = db_session.query(StepRun).first()
        assert not step_run.state.error
        assert step_run.state.result["value"] == expected_message
        assert engine.state == StepEngineState.step_complete

    def test_number_with_grouping_and_spacing_character_template_filter(self, db_session: orm.Session):
        step_template = Step(
            name="step-1",
            step_type=PlayMessageStep.get_type_string(),
            step_kwargs={
                "fieldset": [
                    ("session.number", "num_val"),
                ],
                "template": "Val: {{ num_val|grouped([2,3], ',') }}"
            }
        )
        expected_message = 'Val: 20,000'
        call, \
        call_leg, \
        call_routing, \
        greeting, \
        workflow, \
        workflow_run, \
        step = self.create_test_objects_for_step_template(db_session, step_template, workflow_session={
            "number": "20000"
        })
        engine = StepEngine(db_session, workflow_run)
        engine.initialize(step)
        result = engine.run_step()
        assert isinstance(result, StepSuccess)
        step_run: StepRun = db_session.query(StepRun).first()
        assert not step_run.state.error
        assert step_run.state.result["value"] == expected_message
        assert engine.state == StepEngineState.step_complete

    def test_number_with_individual_template_filter(self, db_session: orm.Session):
        step_template = Step(
            name="step-1",
            step_type=PlayMessageStep.get_type_string(),
            step_kwargs={
                "fieldset": [
                    ("session.number", "num_val"),
                ],
                "template": "Val: {{ num_val|individual }}"
            }
        )
        expected_message = 'Val: 1 2 3 4 5'
        call, \
        call_leg, \
        call_routing, \
        greeting, \
        workflow, \
        workflow_run, \
        step = self.create_test_objects_for_step_template(db_session, step_template, workflow_session={
            "number": "12345"
        })
        engine = StepEngine(db_session, workflow_run)
        engine.initialize(step)
        result = engine.run_step()
        assert isinstance(result, StepSuccess)
        step_run: StepRun = db_session.query(StepRun).first()
        assert not step_run.state.error
        assert step_run.state.result["value"] == expected_message
        assert engine.state == StepEngineState.step_complete

    def test_date_template_filter(self, db_session: orm.Session):
        step_template = Step(
            name="step-1",
            step_type=PlayMessageStep.get_type_string(),
            step_kwargs={
                "fieldset": [
                    ("session.date", "date_val"),
                ],
                "template": "Val: {{ date_val|date }}"
            }
        )
        expected_dt = datetime.datetime.now()
        expected_dt_str = expected_dt.date().isoformat()
        expected_message = f'Val: {calendar.month_name[expected_dt.month]} {expected_dt.day}, {expected_dt.year}'
        call, \
        call_leg, \
        call_routing, \
        greeting, \
        workflow, \
        workflow_run, \
        step = self.create_test_objects_for_step_template(db_session, step_template, workflow_session={
            "date": expected_dt_str
        })
        engine = StepEngine(db_session, workflow_run)
        engine.initialize(step)
        result = engine.run_step()
        assert isinstance(result, StepSuccess)
        step_run: StepRun = db_session.query(StepRun).first()
        assert not step_run.state.error
        assert step_run.state.result["value"] == expected_message
        assert engine.state == StepEngineState.step_complete

    def test_date_with_day_template_filter(self, db_session: orm.Session):
        step_template = Step(
            name="step-1",
            step_type=PlayMessageStep.get_type_string(),
            step_kwargs={
                "fieldset": [
                    ("session.date", "date_val"),
                ],
                "template": "Val: {{ date_val|date_with_day }}"
            }
        )
        expected_dt = datetime.datetime.now()
        expected_dt_str = expected_dt.date().isoformat()
        expected_message = f'Val: {calendar.day_name[expected_dt.weekday()]}, {calendar.month_name[expected_dt.month]} {expected_dt.day}, {expected_dt.year}'
        call, \
        call_leg, \
        call_routing, \
        greeting, \
        workflow, \
        workflow_run, \
        step = self.create_test_objects_for_step_template(db_session, step_template, workflow_session={
            "date": expected_dt_str
        })
        engine = StepEngine(db_session, workflow_run)
        engine.initialize(step)
        result = engine.run_step()
        assert isinstance(result, StepSuccess)
        step_run: StepRun = db_session.query(StepRun).first()
        assert not step_run.state.error
        assert step_run.state.result["value"] == expected_message
        assert engine.state == StepEngineState.step_complete

    def test_payment_date_template_filter(self, db_session: orm.Session):
        step_template = Step(
            name="step-1",
            step_type=PlayMessageStep.get_type_string(),
            step_kwargs={
                "fieldset": [
                    ("session.date", "date_val"),
                ],
                "template": "Val: {{ date_val|payment_date }}"
            }
        )
        expected_dt = datetime.datetime.now()
        expected_dt_str = expected_dt.isoformat()
        expected_message = f'Val: {calendar.day_name[expected_dt.weekday()]}, {calendar.month_name[expected_dt.month]} {expected_dt.day}, {expected_dt.year} at {expected_dt.strftime("%I:%M %p")}'
        call, \
        call_leg, \
        call_routing, \
        greeting, \
        workflow, \
        workflow_run, \
        step = self.create_test_objects_for_step_template(db_session, step_template, workflow_session={
            "date": expected_dt_str
        })
        engine = StepEngine(db_session, workflow_run)
        engine.initialize(step)
        result = engine.run_step()
        assert isinstance(result, StepSuccess)
        step_run: StepRun = db_session.query(StepRun).first()
        assert not step_run.state.error
        assert step_run.state.result["value"] == expected_message
        assert engine.state == StepEngineState.step_complete

    def test_date_mmddyy_template_filter(self, db_session: orm.Session):
        step_template = Step(
            name="step-1",
            step_type=PlayMessageStep.get_type_string(),
            step_kwargs={
                "fieldset": [
                    ("session.date", "date_val"),
                ],
                "template": "Val: {{ date_val|date_mmddyy }}"
            }
        )
        expected_dt = datetime.datetime.now()
        expected_dt_str = expected_dt.isoformat()
        expected_message = f'Val: {expected_dt.strftime("%m/%d/%y")}'
        call, \
        call_leg, \
        call_routing, \
        greeting, \
        workflow, \
        workflow_run, \
        step = self.create_test_objects_for_step_template(db_session, step_template, workflow_session={
            "date": expected_dt_str
        })
        engine = StepEngine(db_session, workflow_run)
        engine.initialize(step)
        result = engine.run_step()
        assert isinstance(result, StepSuccess)
        step_run: StepRun = db_session.query(StepRun).first()
        assert not step_run.state.error
        assert step_run.state.result["value"] == expected_message
        assert engine.state == StepEngineState.step_complete

    def test_number_last_characters_filter(self, db_session: orm.Session):
        step_template = Step(
            name="step-1",
            step_type=PlayMessageStep.get_type_string(),
            step_kwargs={
                "fieldset": [
                    ("session.number", "num_val"),
                ],
                "template": "Val: {{ num_val|last_characters(4) }}"
            }
        )
        expected_message = 'Val: 3456'
        call, \
        call_leg, \
        call_routing, \
        greeting, \
        workflow, \
        workflow_run, \
        step = self.create_test_objects_for_step_template(db_session, step_template, workflow_session={
            "number": "123456"
        })
        engine = StepEngine(db_session, workflow_run)
        engine.initialize(step)
        result = engine.run_step()
        assert isinstance(result, StepSuccess)
        step_run: StepRun = db_session.query(StepRun).first()
        assert not step_run.state.error
        assert step_run.state.result["value"] == expected_message
        assert engine.state == StepEngineState.step_complete
