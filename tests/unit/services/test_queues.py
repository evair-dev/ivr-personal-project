import pytest
import time_machine
from datetime import time, date, timedelta
from sqlalchemy import orm

from ivr_gateway.models.contacts import TransferRouting
from ivr_gateway.models.enums import OperatingMode, TransferType, Partner
from ivr_gateway.models.queues import Queue
from ivr_gateway.services.calls import CallService
from ivr_gateway.services.queues import QueueService, QueueStatusService
from tests.factories import queues as qf


class TestQueuesService:

    @pytest.fixture
    def queue(self, db_session) -> Queue:
        queue = qf.queue_factory(db_session).create(
            name="some.test.queue", hours_of_operation=[])
        return queue

    @pytest.fixture
    def transfer_first_routing(self, db_session, queue: Queue) -> TransferRouting:
        transfer_routing = TransferRouting(
            transfer_type=TransferType.PSTN,
            destination="773-695-2581",
            destination_system="DR Cisco",
            operating_mode="normal",
            queue=queue,
            weight=10,
            priority=0
        )
        db_session.add(transfer_routing)
        db_session.commit()
        return transfer_routing

    @pytest.fixture
    def transfer_second_routing(self, db_session, queue: Queue) -> TransferRouting:
        transfer_routing = TransferRouting(
            transfer_type=TransferType.PSTN,
            destination="773-695-2582",
            destination_system="DR Cisco",
            operating_mode="normal",
            queue=queue,
            weight=10,
            priority=0
        )
        db_session.add(transfer_routing)
        db_session.commit()
        return transfer_routing

    @pytest.fixture
    def queue_service(self, db_session: orm.Session) -> QueueService:
        return QueueService(db_session)

    @pytest.fixture
    def queue_status_service(self, db_session: orm.Session, queue_service: QueueService) -> QueueStatusService:
        return QueueStatusService(CallService(db_session), queue_service)

    @property
    def tomorrow(self):
        return date.today() + timedelta(days=1)

    @property
    def yesterday(self):
        return date.today() - timedelta(days=1)

    def test_add_queue(self, db_session: orm.Session, queue_service):
        new_queue = queue_service.create_queue("test.queue", Partner.IVR, 'closed')
        new_queue2 = queue_service.create_queue("test.queue2", Partner.IVR, 'closed', active=False)
        assert new_queue.name == "test.queue"
        assert new_queue2.name == "test.queue2"
        assert not new_queue2.active
        assert new_queue.partner == Partner.IVR

    def test_add_queue_hours_of_operations(self, db_session: orm.Session, queue: Queue, queue_service):
        queue_service.add_hours_of_operations_for_day(queue, 0, "0800", "1600")
        db_session.refresh(queue)
        assert len(queue.hours_of_operation) == 1
        queue_service.add_hours_of_operations_for_day(queue, 1, "0800", "1600")

    def test_add_emergency_mode_override(self, db_session: orm.Session, queue: Queue,
                                         queue_status_service: QueueStatusService):
        mode, maybe_holiday = queue_status_service.get_current_operation_mode_and_maybe_holiday_for_queue(queue)
        assert mode == OperatingMode.CLOSED
        assert maybe_holiday is None
        queue.emergency_mode = True
        db_session.add(queue)
        db_session.commit()
        mode, maybe_holiday = queue_status_service.get_current_operation_mode_and_maybe_holiday_for_queue(queue)
        assert mode == OperatingMode.EMERGENCY
        assert maybe_holiday is None

    @time_machine.travel("2020-12-29 13:00")
    def test_add_holiday_for_queue_holiday_already_passed(self, db_session: orm.Session, queue: Queue,
                                                          queue_service: QueueService):
        with pytest.raises(Exception) as exception:
            queue_service.add_holiday_for_queue(queue, "Test Holiday", self.yesterday)
        assert exception.value.args[0] == "Holidays must be planned in the future"

    @time_machine.travel("2020-12-29 13:00")
    def test_add_add_holiday_for_queue_standard_error_handling(self, db_session: orm.Session, queue: Queue,
                                                               queue_service: QueueService):
        # start_time or end_time null but not both
        start_time = time(0, 0)
        with pytest.raises(Exception) as exception:
            queue_service.add_holiday_for_queue(queue, "Test Holiday", self.tomorrow, start_time=start_time)
        assert exception.value.args[
                   0] == "Both start_time and end_time must be None or have a value. You can't set one OR the other."

        # holiday must be planned in the future
        with pytest.raises(Exception) as exception:
            queue_service.add_holiday_for_queue(queue, "Test Holiday", self.yesterday)
        assert exception.value.args[0] == "Holidays must be planned in the future"

        # start_time is ahead of end_time
        start_time = time(1, 0)
        end_time = time(0, 0)
        with pytest.raises(Exception) as exception:
            queue_service.add_holiday_for_queue(queue, "Test Holiday", self.tomorrow, start_time=start_time,
                                                end_time=end_time)
        assert exception.value.args[0] == "Holiday start_time can not be >= end_time."

    @time_machine.travel("2020-12-29 13:00")
    def test_hours_of_operation_for_today(self, db_session: orm.Session, queue: Queue, queue_service):
        # "Today" is a tuesday
        queue_service.add_hours_of_operations_for_day(queue, 2, "0000", "0800")
        hours_of_op = queue_service.get_hours_of_operation_for_today(queue)
        assert len(hours_of_op) == 1
        start_time, end_time = hours_of_op[0]
        assert start_time == time(0, 0)
        assert end_time == time(8, 0)
        queue_service.add_hours_of_operations_for_day(queue, 2, "1600", "2359")
        hours_of_op = queue_service.get_hours_of_operation_for_today(queue)
        assert len(hours_of_op) == 2
        start_time, end_time = hours_of_op[1]
        assert start_time == time(16, 0)
        assert end_time == time(23, 59)

    def test_add_queue_hours_of_operations_error_handling(self, db_session: orm.Session, queue: Queue,
                                                          queue_service: QueueService):
        queue_service.add_hours_of_operations_for_day(queue, 0, "0800", "1600")
        # Add an overlapping start time
        with pytest.raises(Exception):
            queue_service.add_hours_of_operations_for_day(queue, 0, "0000", "0801")
        # Overlapping end
        with pytest.raises(Exception):
            queue_service.add_hours_of_operations_for_day(queue, 0, "1559", "2000")
        # improper start after end
        with pytest.raises(Exception):
            queue_service.add_hours_of_operations_for_day(queue, 0, "2300", "2000")
        # improper start length
        with pytest.raises(Exception):
            queue_service.add_hours_of_operations_for_day(queue, 0, "59", "2000")
        # improper end length
        with pytest.raises(Exception):
            queue_service.add_hours_of_operations_for_day(queue, 0, "2000", "201")
        # improper end time
        with pytest.raises(Exception):
            queue_service.add_hours_of_operations_for_day(queue, 0, "0000", "2400")
        # improper start time
        with pytest.raises(Exception):
            queue_service.add_hours_of_operations_for_day(queue, 0, "-300", "0800")
        queue_service.add_hours_of_operations_for_day(queue, 0, "0700", "0800")
        queue_service.add_hours_of_operations_for_day(queue, 0, "1600", "2000")

    @time_machine.travel("2020-12-29 13:00")
    def test_equal_transfer_weighting(self, db_session: orm.Session, queue: Queue,
                                      transfer_first_routing: TransferRouting,
                                      transfer_second_routing: TransferRouting, queue_service: QueueService,
                                      queue_status_service: QueueStatusService, predictable_random):
        for i in range(7):
            queue_service.add_hours_of_operations_for_day(queue, i, "0400", "2200")

        first_sum = 0
        second_sum = 0
        for i in range(100):
            transfer_routing = queue_status_service.get_current_transfer_routing_mode_and_maybe_holiday_for_queue(queue,
                                                                                                                  "twilio")
            if transfer_routing[0] == transfer_first_routing:
                first_sum += 1
            elif transfer_routing[0] == transfer_second_routing:
                second_sum += 1
        assert first_sum == 41
        assert second_sum == 59

    @time_machine.travel("2020-12-29 13:00")
    def test_unequal_transfer_weighting(self, db_session: orm.Session, queue: Queue,
                                        transfer_first_routing: TransferRouting,
                                        transfer_second_routing: TransferRouting, queue_service: QueueService,
                                        queue_status_service: QueueStatusService, predictable_random):
        for i in range(7):
            queue_service.add_hours_of_operations_for_day(queue, i, "0400", "2200")
        transfer_first_routing.weight = 2
        first_sum = 0
        second_sum = 0
        for i in range(100):
            transfer_routing = queue_status_service.get_current_transfer_routing_mode_and_maybe_holiday_for_queue(queue,
                                                                                                                  "twilio")
            if transfer_routing[0] == transfer_first_routing:
                first_sum += 1
            elif transfer_routing[0] == transfer_second_routing:
                second_sum += 1
        assert first_sum < 20
        assert second_sum > 80

    @time_machine.travel("2020-12-29 13:00")
    def test_all_second_transfer_weighting(self, db_session: orm.Session, queue: Queue,
                                           transfer_first_routing: TransferRouting,
                                           transfer_second_routing: TransferRouting, queue_service: QueueService,
                                           queue_status_service: QueueStatusService, predictable_random):
        for i in range(7):
            queue_service.add_hours_of_operations_for_day(queue, i, "0400", "2200")
        transfer_first_routing.weight = 0
        first_sum = 0
        second_sum = 0
        for i in range(100):
            transfer_routing = queue_status_service.get_current_transfer_routing_mode_and_maybe_holiday_for_queue(queue,
                                                                                                                  "twilio")
            if transfer_routing[0] == transfer_first_routing:
                first_sum += 1
            elif transfer_routing[0] == transfer_second_routing:
                second_sum += 1
        assert first_sum == 0
        assert second_sum == 100

    @time_machine.travel("2020-12-29 13:00")
    def test_negative_transfer_weighting(self, db_session: orm.Session, queue: Queue,
                                         transfer_first_routing: TransferRouting,
                                         transfer_second_routing: TransferRouting, queue_service: QueueService,
                                         queue_status_service: QueueStatusService, predictable_random):
        for i in range(7):
            queue_service.add_hours_of_operations_for_day(queue, i, "0400", "2200")
        transfer_second_routing.priority = -1
        first_sum = 0
        second_sum = 0
        for i in range(100):
            transfer_routing = queue_status_service.get_current_transfer_routing_mode_and_maybe_holiday_for_queue(queue,
                                                                                                                  "twilio")
            if transfer_routing[0] == transfer_first_routing:
                first_sum += 1
            elif transfer_routing[0] == transfer_second_routing:
                second_sum += 1
        assert first_sum == 100
        assert second_sum == 0
