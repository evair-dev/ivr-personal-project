import datetime
import random
from datetime import time, date
from typing import Optional, List, Tuple

import pytz
from sqlalchemy import orm

from ivr_gateway.models.contacts import TransferRouting
from ivr_gateway.models.enums import OperatingMode, TransferType, Partner
from ivr_gateway.models.exceptions import MissingTransferRoutingException
from ivr_gateway.models.queues import Queue, QueueHoursOfOperation, QueueHoliday
from ivr_gateway.services.calls import CallService


def overlap(qhoo1: QueueHoursOfOperation, start_time: time, end_time: time):
    if qhoo1.start_time <= start_time < qhoo1.end_time or \
            qhoo1.start_time < end_time <= qhoo1.end_time:
        return True
    return False


class QueueService:

    def __init__(self, session: orm.Session):
        self.session = session

    def get_all_queues(self) -> List[Queue]:
        return self.session.query(Queue).all()

    def get_queue_by_name(self, name) -> Optional[Queue]:
        return (self.session.query(Queue)
                .filter(Queue.name == name)
                .one_or_none())

    def get_list_of_queues_by_name(self, queue_names: List[str]):
        return (self.session.query(Queue)
                .filter(Queue.name.in_(queue_names))
                .all())

    def create_queue(self, name: str, partner: Partner, closed_message: str, active=True) -> Queue:
        queue = Queue(name=name, partner=partner, closed_message=closed_message, active=active)
        self.session.add(queue)
        self.session.commit()
        return queue

    def add_hours_of_operations_for_day(self, queue: Queue, day_of_week: int, start_time: str, end_time: str):
        """
        Adds a record for hours of operations for a queue, time is passed in as an integer (0800 == 8am, 1600 == 8pm),
        time is parsed into a timezone aware UTC time object, depending on the queue's initial timezone

        :param queue:
        :param day_of_week:
        :param start_time:
        :param end_time:
        :return:
        """
        if len(start_time) != 4 or len(end_time) != 4:
            raise Exception("Start and end time must be 4 characters long")
        start_time_int = int(start_time)
        end_time_int = int(end_time)
        if end_time_int >= 2400:
            raise Exception("End time must be < 2400")
        if start_time_int < 0:
            raise Exception("Start time must be at least 0")
        if end_time_int <= start_time_int:
            raise Exception("End time must be after start time.")
        if not (0 <= day_of_week < 7):
            raise Exception("Day of week must be 0-6 starting with 0 = 'Sunday'")

        start_time_hours = int(start_time[:2])
        start_time_minutes = int(start_time[2:])
        end_time_hours = int(end_time[:2])
        end_time_minutes = int(end_time[2:])

        if start_time_minutes < 0 or end_time_minutes < 0 or \
                start_time_minutes > 60 or end_time_minutes > 60:
            raise Exception("")

        _start_time = time(start_time_hours, start_time_minutes, 0)
        _end_time = time(end_time_hours, end_time_minutes, 0)

        if self._would_queue_hours_of_operations_overlap(queue, day_of_week, _start_time, _end_time):
            raise Exception("Hours of operations overlap, please resolve existing hours before adding new span")
        qhoo = QueueHoursOfOperation(queue=queue, day_of_week=day_of_week, start_time=_start_time, end_time=_end_time)
        self.session.add(qhoo)
        self.session.commit()

    def add_holiday_for_queue(self, queue: Queue, name: str, holiday: date, start_time=None, end_time=None, message=None):
        localized_queue_now = self.get_localized_now_for_queue(queue)
        today = localized_queue_now.date()

        if holiday < today:
            raise Exception("Holidays must be planned in the future")

        if (not start_time and end_time) or (start_time and not end_time):
            raise Exception("Both start_time and end_time must be None or have a value. You can't set one OR the other.")

        if (start_time and end_time) and start_time >= end_time:
            raise Exception("Holiday start_time can not be >= end_time.")
        existing_queue_holidays = (self.session.query(QueueHoliday)
                                   .join(Queue)
                                   .filter(Queue.id == queue.id)
                                   .filter(QueueHoliday.date == holiday))
        if existing_queue_holidays.count() > 0:
            existing_holiday_names = [qh.name for qh in existing_queue_holidays.all()]
            raise Exception(f"Holidays already planned: {existing_holiday_names}")
        qh = QueueHoliday(queue=queue, name=name, date=holiday, start_time=start_time, end_time=end_time, message=message)
        self.session.add(qh)
        self.session.commit()

    def get_current_day_of_week_for_queue(self, queue: Queue) -> int:
        localized_queue_now = self.get_localized_now_for_queue(queue)
        return localized_queue_now.isoweekday() % 7

    def get_hours_of_operation_for_today(self, queue: Queue) -> List[Tuple[time, time]]:
        current_day_of_week = self.get_current_day_of_week_for_queue(queue)
        hours_of_ops: List[QueueHoursOfOperation] = (self.session.query(QueueHoursOfOperation)
                                                     .join(QueueHoursOfOperation.queue)
                                                     .filter(Queue.name == queue.name)
                                                     .filter(QueueHoursOfOperation.day_of_week == current_day_of_week)
                                                     .order_by(QueueHoursOfOperation.start_time.asc())
                                                     .all())

        return [(hoo.start_time, hoo.end_time) for hoo in hours_of_ops]

    def get_queue_holiday_for_today_if_exist(self, queue: Queue) -> Optional[QueueHoliday]:
        localized_queue_now = self.get_localized_now_for_queue(queue)
        localized_queue_now_date = localized_queue_now.date()
        holiday_hoop = (self.session.query(QueueHoliday)
                        .join(Queue)
                        .filter(Queue.id == queue.id)
                        .filter(QueueHoliday.date == localized_queue_now_date)
                        .first())
        return holiday_hoop

    def get_current_time_of_day_for_queue(self, queue: Queue) -> time:
        localized_queue_now = self.get_localized_now_for_queue(queue)
        return localized_queue_now.time()

    def _would_queue_hours_of_operations_overlap(self, queue: Queue, day_of_week, start_time, end_time):
        existing_hours_of_operations = (self.session.query(QueueHoursOfOperation)
                                        .join(Queue)
                                        .filter(Queue.id == queue.id)
                                        .filter(QueueHoursOfOperation.day_of_week == day_of_week)
                                        .filter(QueueHoursOfOperation.queue_id == queue.id)
                                        .order_by(QueueHoursOfOperation.start_time.asc()))
        for hoo in existing_hours_of_operations:
            if overlap(hoo, start_time, end_time):
                return True
        return False

    def get_localized_now_for_queue(self, queue: Queue):
        utcnow = datetime.datetime.now(datetime.timezone.utc)
        queue_timezone = pytz.timezone(queue.timezone)
        return utcnow.astimezone(queue_timezone)


class QueueStatusService:

    def __init__(self, call_service: CallService, queue_service: QueueService):
        self.call_service = call_service
        self.queue_service = queue_service

    def get_current_transfer_routing_mode_and_maybe_holiday_for_queue(self, queue: Queue, current_system: str) \
            -> Tuple[TransferRouting, OperatingMode, Optional[QueueHoliday]]:
        transfer_routings = self.call_service.get_transfer_routings_for_queue(queue)
        # Filter out transfer routings that are internal to not the current system
        transfer_routings = [tr for tr in transfer_routings if not (tr.transfer_type == TransferType.INTERNAL
                                                                    and tr.destination_system.lower() != current_system.lower())]

        in_emergency = OperatingMode.EMERGENCY in (queue.emergency_mode,
                                                   self.call_service.get_system_operating_mode())
        if in_emergency and len(transfer_routings) > 0:
            # We have some queue in the routings that returned normal operating mode
            transfer_routing = transfer_routings[0]
            return transfer_routing, OperatingMode.EMERGENCY, None
        elif len(transfer_routings) > 0:
            queue_operating_mode, maybe_holiday = \
                self.get_current_operation_mode_and_maybe_holiday_for_queue(queue)
            if maybe_holiday is not None:
                # If it is a holiday just return the current transfer routing
                transfer_routing = self.get_weighted_transfer_routing(transfer_routings)
                return transfer_routing, queue_operating_mode, maybe_holiday
            if queue_operating_mode == OperatingMode.CLOSED:
                # If the queue is closed look for an open queue
                queue_transfers = [tr for tr in transfer_routings if tr.transfer_type == TransferType.QUEUE]
                if len(queue_transfers) == 0:
                    # If no queue transfers just return the current transfer routing
                    transfer_routing = transfer_routings[0]
                    return transfer_routing, queue_operating_mode, maybe_holiday
                for qt in queue_transfers:
                    # Find an open queue to transfer to
                    queue_name = qt.destination
                    waterfall_queue = self.queue_service.get_queue_by_name(queue_name)
                    waterfall_queue_mode, _ = self.get_current_operation_mode_and_maybe_holiday_for_queue(
                        waterfall_queue)
                    if waterfall_queue_mode == OperatingMode.NORMAL:
                        return self.get_current_transfer_routing_mode_and_maybe_holiday_for_queue(waterfall_queue,
                                                                                                  current_system)
            transfer_routing = self.get_weighted_transfer_routing(transfer_routings)
            return transfer_routing, queue_operating_mode, maybe_holiday
        else:
            raise MissingTransferRoutingException("Missing transfer routing for queue")

    def get_current_operation_mode_and_maybe_holiday_for_queue(self, queue: Queue) \
            -> Tuple[OperatingMode, Optional[QueueHoliday]]:
        if queue.emergency_mode:
            return OperatingMode.EMERGENCY, None

        hours_of_ops = self.queue_service.get_hours_of_operation_for_today(queue)
        queue_time_of_day = self.queue_service.get_current_time_of_day_for_queue(queue)

        # Check if we are on a holiday
        holiday = self.queue_service.get_queue_holiday_for_today_if_exist(queue)
        if holiday:
            if None in (holiday.start_time, holiday.end_time):
                return OperatingMode.HOLIDAY, holiday
            elif holiday.start_time <= queue_time_of_day < holiday.end_time:
                return OperatingMode.NORMAL, holiday
            else:
                return OperatingMode.HOLIDAY, holiday
        if len(hours_of_ops) == 0:
            # No hours of ops listed for queue => always outside of hours
            return OperatingMode.CLOSED, holiday
        # Check normal operating hours
        for start_time, end_time in hours_of_ops:
            if start_time <= queue_time_of_day < end_time:
                return OperatingMode.NORMAL, holiday
        return OperatingMode.CLOSED, holiday

    def get_weighted_transfer_routing(self, routings: List[TransferRouting]) -> TransferRouting:
        if len(routings) == 1:
            return routings[0]
        routings.sort(key=lambda routing: routing.priority)
        active_routings = [routing for routing in routings if routing.priority >= 0]
        lowest_priority = active_routings[0].priority
        lowest_priority_routings = [routing for routing in active_routings if routing.priority == lowest_priority]
        if len(lowest_priority_routings) == 1:
            return lowest_priority_routings[0]

        weights = [routing.weight for routing in lowest_priority_routings]
        return random.choices(lowest_priority_routings, weights=weights, k=1)[0]  # nosec
