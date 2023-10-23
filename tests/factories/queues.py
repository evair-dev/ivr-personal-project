import factory
from collections.abc import Iterable

from ivr_gateway.models.enums import Partner
from ivr_gateway.models.queues import Queue
from tests.factories import transfer_routings as trf, queue_hours_of_operation as qhoof


def queue_factory(session):
    class _QueueFactory(factory.alchemy.SQLAlchemyModelFactory):
        class Meta:
            model = Queue
            sqlalchemy_session = session

        active = True
        partner = Partner.IVR
        closed_message = '<break time="500ms"/> We are currently closed. Please try us back during our normal ' \
                         'business hours of 7am-10pm central time. We apologize for this inconvenience and look ' \
                         'forward to speaking with you then.'
        timezone = "America/Chicago"

        @factory.post_generation
        def hours_of_operation(obj, create, extracted, **kwargs):
            if not create:
                # Simple build, do nothing.
                return

            hours_of_operation = qhoof.queue_hours_of_operation_factory(session)
            if extracted is not None and isinstance(extracted, Iterable):
                for extracted_e in extracted:
                    hours_of_operation.create(
                        queue=obj,
                        **extracted_e
                    )

            else:
                for i in range(7):
                    hours_of_operation.create(queue=obj, day_of_week=i)

        @factory.post_generation
        def transfer_routings(obj, create, extracted, **kwargs):
            if not create:
                # Simple build, do nothing.
                return
            transfer_routing = trf.transfer_routing_factory(session)
            print(f"Extracted: {extracted}")
            if extracted is not None and isinstance(extracted, Iterable):
                for extracted_e in extracted:
                    transfer_routing.create(
                        queue=obj,
                        **extracted_e
                    )
            else:
                transfer_routing.create(
                    queue=obj,
                    transfer_type="PSTN",
                    destination="12345678901",
                    destination_system="CISCO",
                )

    return _QueueFactory
