from datetime import date, datetime

import pytest
import time_machine

from ivr_gateway.exceptions import InvalidQueueConfigException
from tests.factories import queues as qf
from ivr_gateway.models.queues import Queue, QueueHoliday
from ivr_gateway.services.operating_times import OperatingTimesService, HolidayHoursService


class TestOperatingTimes:

    @pytest.fixture
    def operating_times_service(self) -> OperatingTimesService:
        return OperatingTimesService()

    def test_is_weekday(self, operating_times_service):
        assert operating_times_service.is_business_day(date(2021, 1, 4))  # Monday
        assert operating_times_service.is_business_day(date(2021, 1, 5))  # Tuesday
        assert operating_times_service.is_business_day(date(2021, 1, 6))  # Wednesday
        assert operating_times_service.is_business_day(date(2021, 1, 7))  # Thursday
        assert operating_times_service.is_business_day(date(2021, 1, 8))  # Friday
        assert not operating_times_service.is_business_day(date(2021, 1, 9))  # Saturday
        assert not operating_times_service.is_business_day(date(2021, 1, 10))  # Sunday

    def test_is_holiday(self, operating_times_service):
        assert operating_times_service.is_holiday(date(2021, 1, 1))
        assert not operating_times_service.is_holiday(date(2021, 1, 2))

    def test_is_business_day(self, operating_times_service):
        assert not operating_times_service.is_business_day(date(2021, 1, 1))  # New Years
        assert not operating_times_service.is_business_day(date(2021, 1, 1))  # Saturday
        assert not operating_times_service.is_business_day(date(2021, 1, 1))  # Sunday
        assert operating_times_service.is_business_day(date(2021, 1, 4))  # Monday
        assert operating_times_service.is_business_day(date(2021, 1, 5))  # Tuesday
        assert operating_times_service.is_business_day(date(2021, 1, 6))  # Wednesday
        assert operating_times_service.is_business_day(date(2021, 1, 7))  # Thursday

    def test_next_business_day(self, operating_times_service):
        assert operating_times_service.next_business_day(date(2020, 12, 31)) == \
               date(2021, 1, 4)  # New Years Eve -> Monday
        assert operating_times_service.next_business_day(date(2021, 1, 1)) == date(2021, 1, 4)  # New Years -> Monday
        assert operating_times_service.next_business_day(date(2021, 1, 2)) == date(2021, 1, 4)  # Saturday -> Monday
        assert operating_times_service.next_business_day(date(2021, 1, 3)) == date(2021, 1, 4)  # Sunday -> Monday
        assert operating_times_service.next_business_day(date(2021, 1, 4)) == date(2021, 1, 5)  # Monday -> Tuesday
        assert operating_times_service.next_business_day(date(2021, 1, 5)) == date(2021, 1, 6)  # Tuesday -> Wednesday
        assert operating_times_service.next_business_day(date(2021, 1, 6)) == date(2021, 1, 7)  # Wednesday -> Thursday
        assert operating_times_service.next_business_day(date(2021, 1, 7)) == date(2021, 1, 8)  # Thursday -> Friday
        assert operating_times_service.next_business_day(date(2021, 1, 8)) == date(2021, 1, 11)  # Friday -> Monday

class TestHolidayHours:
    @pytest.fixture
    def holiday_hours_service(self, db_session):
        return HolidayHoursService(db_session)

    @pytest.fixture
    def queue(self, db_session) -> Queue:
        queue = qf.queue_factory(db_session).create(
            name="some.test.queue", hours_of_operation=[])
        return queue

    def test_create_holiday_hours_from_config_without_name(self, holiday_hours_service):
        with pytest.raises(InvalidQueueConfigException) as exception:
            holiday_hours_service.create_holiday_hours_from_config({})
        assert exception.value.args[0] == "No name for holiday supplied."

    def test_create_holiday_hours_from_config_without_date(self, holiday_hours_service):
        config = {
            "name": "test_config"
        }

        with pytest.raises(InvalidQueueConfigException) as exception:
            holiday_hours_service.create_holiday_hours_from_config(config)
        assert exception.value.args[0] == f"Invalid or empty date for {config.get('name')}"

    def test_create_holiday_hours_from_config_with_invalid_date(self, holiday_hours_service):
        config = {
            "name": "test_config",
            "date": "not_a_date"
        }

        with pytest.raises(InvalidQueueConfigException) as exception:
            holiday_hours_service.create_holiday_hours_from_config(config)
        assert exception.value.args[0]  == f"Invalid or empty date for {config.get('name')}"

    def test_create_holiday_hours_from_config_without_queue_configs(self, holiday_hours_service):
        config = {
            "name": "test_config",
            "date": "2021-12-31"
        }

        with pytest.raises(InvalidQueueConfigException) as exception:
            holiday_hours_service.create_holiday_hours_from_config(config)
        assert exception.value.args[0] == f"No queue_configs supplied for holiday {config.get('name')}."

    def test_create_holiday_hours_from_config_without_queues(self, holiday_hours_service):
        config = {
            "name": "test_config",
            "date": "2021-12-31",
            "queue_configs": [
                {}
            ]
        }

        with pytest.raises(InvalidQueueConfigException) as exception:
            holiday_hours_service.create_holiday_hours_from_config(config)
        assert exception.value.args[0] == "queue_configs must have a list of queues to apply to"

    def test_create_holiday_hours_from_config_with_invalid_queue_name(self, holiday_hours_service):
        config = {
            "name": "test_config",
            "date": "2021-12-31",
            "queue_configs": [
                {
                    "queues": ["some.test.queue"],
                    "start_time": "09:00",
                    "end_time": "14:00"
                }
            ]
        }

        with pytest.raises(InvalidQueueConfigException) as exception:
            holiday_hours_service.create_holiday_hours_from_config(config)
        assert exception.value.args[0] == "One of the queue names provided does not exist"

    def test_create_holiday_hours_from_config_with_invalid_start_time(self, holiday_hours_service, queue):
        config = {
            "name": "test_config",
            "date": "2021-12-31",
            "queue_configs": [
                {
                    "queues": ["some.test.queue"],
                    "start_time": "not_a_time",
                    "end_time": "00:00"
                }
            ]
        }

        with pytest.raises(InvalidQueueConfigException) as exception:
            holiday_hours_service.create_holiday_hours_from_config(config)
        assert exception.value.args[0] == "Invalid or empty start_time, need to set a correct start_time"

    def test_create_holiday_hours_from_config_with_invalid_end_time(self, holiday_hours_service, queue):
        config = {
            "name": "test_config",
            "date": "2021-12-31",
            "queue_configs": [
                {
                    "queues": ["some.test.queue"],
                    "start_time": "00:00",
                    "end_time": "not_a_time"
                }
            ]
        }

        with pytest.raises(InvalidQueueConfigException) as exception:
            holiday_hours_service.create_holiday_hours_from_config(config)
        assert exception.value.args[0] == "Invalid or empty end_time, need to set a correct end_time"

    def test_create_holiday_hours_from_config_with_later_start_time(self, holiday_hours_service, queue):
        config = {
            "name": "test_config",
            "date": "2021-12-31",
            "queue_configs": [
                {
                    "queues": ["some.test.queue"],
                    "start_time": "01:00",
                    "end_time": "00:00"
                }
            ]
        }

        with pytest.raises(InvalidQueueConfigException) as exception:
            holiday_hours_service.create_holiday_hours_from_config(config)
        assert exception.value.args[0] == "end_time must come after start_time"

    @time_machine.travel("2020-12-29 19:00")
    def test_valid_holiday_payload(self, db_session, holiday_hours_service, queue):
        config = {
            "name": "test_holiday",
            "date": "2021-12-31",
            "queue_configs": [
                {
                    "queues": ["some.test.queue"],
                    "start_time": "09:00",
                    "end_time": "14:00"
                }
            ]
        }

        holiday_hours_service.create_holiday_hours_from_config(config)

        result = (db_session.query(QueueHoliday)
                  .join(Queue)
                  .filter(Queue.id == queue.id)
                  .first())
        assert result.name == "test_holiday"
        assert result.start_time == datetime.strptime("09:00", '%H:%M').time()
        assert result.end_time == datetime.strptime("14:00", '%H:%M').time()
        assert result.date == datetime.fromisoformat("2021-12-31").date()
