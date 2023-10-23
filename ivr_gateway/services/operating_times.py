from datetime import date, timedelta

from sqlalchemy.orm.session import Session as SQLAlchemySession

from ivr_gateway.exceptions import InvalidQueueConfigException
from ivr_gateway.services.queues import QueueService
from ivr_gateway.utils import try_cast_to_date, try_cast_to_time


class OperatingTimesService:
    ACH_HOLIDAYS = {
        '2021-01-01',
        '2021-01-18',
        '2021-01-20',
        '2021-02-15',
        '2021-05-31',
        '2021-07-05',
        '2021-09-06',
        '2021-10-11',
        '2021-11-11',
        '2021-11-25',
        '2021-12-26',

    }

    def is_business_day(self, day: date) -> bool:
        return self.is_weekday(day) and not self.is_holiday(day)

    def next_business_day(self, day: date) -> date:
        next_day = day + timedelta(days=1)
        while not self.is_business_day(next_day):
            next_day = next_day + timedelta(days=1)
        return next_day

    def previous_business_day(self, day: date) -> date:
        previous_day = day - timedelta(days=1)
        while not self.is_business_day(previous_day):
            previous_day = previous_day - timedelta(days=1)
        return previous_day

    def last_business_day(self, day: date) -> date:
        if self.is_business_day(day):
            return day
        return self.previous_business_day(day)

    def max_card_payment_day(self, day: date) -> date:
        return day + timedelta(days=180)

    def min_card_payment_day(self, day: date) -> date:
        return day

    def is_weekday(self, day: date) -> bool:
        return day.isoweekday() < 6

    def is_holiday(self, day: date) -> bool:
        return day.isoformat() in self.ACH_HOLIDAYS


class HolidayHoursService:
    def __init__(self, db_session: SQLAlchemySession):
        self.session = db_session
        self.queue_service = QueueService(db_session)

    def create_holiday_hours_from_config(self, config):
        """

        :param config: {
            "name": "memorial day 2021",
            "date": "2021-05-31",
            "queue_configs": [
              {
                "queues: ["AFC.LN.PAY.INT"],
                (optional)"message": "it is memorial day, we are gone",
                "start_time":  "09:00" or None,
                "end_time": "14:00" or None,
              }
            ]
          }
        :return:
        """
        if not config.get("name"):
            raise InvalidQueueConfigException("No name for holiday supplied.")
        name = config.get("name")

        holiday_date = try_cast_to_date(config.get("date"))
        if not holiday_date:
            raise InvalidQueueConfigException(f"Invalid or empty date for {config.get('name')}")

        if not config.get("queue_configs"):
            raise InvalidQueueConfigException(f"No queue_configs supplied for holiday {config.get('name')}.")

        for queue_config in config.get("queue_configs"):
            if not queue_config.get("queues"):
                raise InvalidQueueConfigException("queue_configs must have a list of queues to apply to")
            queues = self.queue_service.get_list_of_queues_by_name(queue_config.get("queues"))

            if not len(queues) == len(queue_config.get("queues")):
                raise InvalidQueueConfigException("One of the queue names provided does not exist")

            start_time = try_cast_to_time(queue_config.get("start_time"))
            end_time = try_cast_to_time(queue_config.get("end_time"))

            if not start_time and end_time:
                raise InvalidQueueConfigException("Invalid or empty start_time, need to set a correct start_time")

            if start_time and not end_time:
                raise InvalidQueueConfigException("Invalid or empty end_time, need to set a correct end_time")

            if start_time and end_time:
                if not (end_time > start_time):
                    raise InvalidQueueConfigException("end_time must come after start_time")

            for queue in queues:
                self.queue_service.add_holiday_for_queue(queue, name, holiday_date, start_time, end_time, queue_config.get("message"))




