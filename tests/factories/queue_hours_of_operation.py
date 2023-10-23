from datetime import time

import factory

from ivr_gateway.models.queues import QueueHoursOfOperation


def queue_hours_of_operation_factory(session):
    class _QueueHoursOfOperationFactory(factory.alchemy.SQLAlchemyModelFactory):
        class Meta:
            model = QueueHoursOfOperation
            sqlalchemy_session = session

        start_time = time(8, 0, 0)
        end_time = time(16, 0, 0)


    return _QueueHoursOfOperationFactory
