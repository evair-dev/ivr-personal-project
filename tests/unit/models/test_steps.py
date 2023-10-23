import pytest
from sqlalchemy import orm

from ivr_gateway.exceptions import NonUpdateableModelError
from ivr_gateway.models.steps import StepRun
from ivr_gateway.steps.api.v1 import PlayMessageStep


class TestStepState:

    @pytest.fixture
    def step_run(self, db_session: orm.Session) -> StepRun:
        step_run = StepRun(
            name="test_step",
            branch="test_branch",
            step_type=PlayMessageStep.get_type_string(),
            initialization={
                "args": ["test_step"],
                "kwargs": {
                    "template": "Test Message"
                },
                "session": {}
            }
        )
        db_session.add(step_run)
        db_session.commit()
        return step_run

    def test_step_run_state_is_updatable(self, db_session: orm.Session, step_run: StepRun):
        assert step_run.state is None
        rendered_message = "Test Message"
        created_state = step_run.create_state_update(step_input={}, step_result={
            "message": rendered_message
        })
        # Testing that state update is implicitly added to the open session, id should be None here
        assert created_state.id is None
        db_session.commit()
        # id should be
        assert created_state.id is not None
        assert len(step_run.step_states) == 1
        expected_updated_message = "Some other message"
        created_state2 = step_run.create_state_update(step_input={}, step_result={
            "message": expected_updated_message
        })
        assert created_state2.id is None
        db_session.commit()
        assert created_state2.id is not None
        assert len(step_run.step_states) == 2
        get_state_response = step_run.state
        get_state_response.result["message"] = expected_updated_message
        first_run_state = step_run.get_state(run_index=0)
        assert first_run_state == created_state

    def test_step_state_is_immutable(self, db_session: orm.Session, step_run: StepRun):
        created_state = step_run.create_state_update(step_input={}, step_result={
            "message": "Test Message"
        })
        # Testing that state update is implicitly added to the open session, id should be None here
        assert created_state.id is None
        db_session.commit()
        step_result_copy = created_state.result.copy()
        step_result_copy["message"] = "New Test Message"
        created_state.result = step_result_copy
        db_session.add(created_state)
        with pytest.raises(NonUpdateableModelError):
            db_session.commit()

    def test_step_run_get_state(self, db_session: orm.Session, step_run: StepRun):
        assert step_run.get_state() is None
        with pytest.raises(IndexError):
            step_run.get_state(run_index=-2)
        with pytest.raises(IndexError):
            step_run.get_state(run_index=1)
        with pytest.raises(IndexError):
            step_run.get_state(run_index=0)
        assert step_run.get_state(run_index=-1) is None
        created_state = step_run.create_state_update(step_input={}, step_result={
            "message": "Test Message"
        })

        db_session.commit()
        assert step_run.get_state(run_index=0) == created_state
        assert step_run.get_state(run_index=-1) == created_state
        with pytest.raises(IndexError):
            step_run.get_state(run_index=-2)
        with pytest.raises(IndexError):
            step_run.get_state(run_index=1)
