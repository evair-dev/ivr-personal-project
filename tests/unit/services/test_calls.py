import pytest
from datetime import datetime, timedelta

from ivr_gateway.models.contacts import TransferRouting
from ivr_gateway.models.queues import Queue
from ivr_gateway.services.calls import CallService
from tests.factories import queues as qf

from tests.factories import calls as cf

ANI1 = "6637469788"
ANI2 = "6637469900"
DNIS = "12345678901"


class TestCallsService:

    @pytest.fixture
    def queue(self, db_session) -> Queue:
        queue = qf.queue_factory(db_session).create(
            name="Iivr.LN.PAY.INT")
        return queue

    @pytest.fixture
    def transfer_routing(self, db_session, queue) -> TransferRouting:
        transfer_routing = TransferRouting(
            queue=queue,
            transfer_type="PSTN",
            destination="12345678901",
            destination_system="CISCO",
            operating_mode="normal"
        )
        db_session.add(transfer_routing)
        db_session.commit()
        return transfer_routing

    def test_get_most_recent_call(self, db_session):
        cf.call_factory(db_session).create(device_identifier=ANI1)  # call 1
        cf.call_factory(db_session).create(device_identifier=ANI2)  # call 2
        call3 = cf.call_factory(db_session).create(device_identifier=ANI2)

        call_service = CallService(db_session)
        most_recent_call = call_service.get_most_recent_call(call3.device_identifier)

        assert most_recent_call.device_identifier == call3.device_identifier
        assert most_recent_call.id == call3.id

    def test_get_most_recent_call_leg(self, db_session):
        now = datetime.now()
        test_call = cf.call_factory(db_session).create(
            device_identifier=ANI1,
            contact_legs=[
                {
                    "contact_system": "test",
                    "contact_system_id": "123",
                    "ani": ANI1,
                    "dnis": DNIS,
                    "created_at": now
                },
                {
                    "contact_system": "test",
                    "contact_system_id": "123",
                    "ani": ANI1,
                    "dnis": DNIS,
                    "created_at": now + timedelta(seconds=1)
                }
            ])
        call_leg_b = test_call.contact_legs[1]

        # swap positions to expand test coverage and ensure that the most recent call is returned regardless of index
        test_call.contact_legs = test_call.contact_legs[::-1]

        call_service = CallService(db_session)
        most_recent_call_leg = call_service.get_most_recent_call_leg(ANI1)
        assert most_recent_call_leg == call_leg_b

    def test_get_most_recent_call_leg_no_contact_legs(self, db_session):
        cf.call_factory(db_session).build(device_identifier=ANI1)
        call_service = CallService(db_session)
        most_recent_call_leg = call_service.get_most_recent_call_leg(ANI1)
        assert most_recent_call_leg is None

    def test_get_recent_transferred_call(self, db_session, transfer_routing):
        call1 = cf.call_factory(db_session).create(
            device_identifier=ANI1,
            contact_legs=[
                {
                    "contact_system": "test",
                    "contact_system_id": "123",
                    "ani": ANI1,
                    "dnis": DNIS

                },
                {
                    "contact_system": "test",
                    "contact_system_id": "123",
                    "ani": ANI1,
                    "dnis": DNIS,
                    "transfer_routing": transfer_routing,
                    "end_time": datetime.now()
                }
            ])

        # call 2
        cf.call_factory(db_session).create(
            device_identifier=ANI2,
            contact_legs=[
                {
                    "contact_system": "test",
                    "contact_system_id": "123",
                    "ani": ANI2,
                    "dnis": DNIS
                },
                {
                    "contact_system": "test",
                    "contact_system_id": "123",
                    "ani": ANI2,
                    "dnis": DNIS
                }
            ])

        call_service = CallService(db_session)
        transferred_call, reason = call_service.get_recent_transferred_call(ani=ANI1, dnis=DNIS)
        assert transferred_call == call1.contact_legs[0].contact
        assert reason is None

    def test_get_recent_transferred_call_dnis_mismatch(self, db_session, transfer_routing):
        cf.call_factory(db_session).create(
            device_identifier=ANI1,
            contact_legs=[
                {
                    "contact_system": "test",
                    "contact_system_id": "123",
                    "ani": ANI1,
                    "dnis": "15555555555",
                    "transfer_routing": transfer_routing,
                    "end_time": datetime.now()
                }
            ])

        call_service = CallService(db_session)
        transferred_call, reason = call_service.get_recent_transferred_call(ani=ANI1, dnis="15555555555")
        assert transferred_call is None
        assert reason == "dnis mismatch"

    def test_get_recent_transferred_call_too_old(self, db_session, transfer_routing):
        cf.call_factory(db_session).create(
            device_identifier=ANI1,
            contact_legs=[
                {
                    "contact_system": "test",
                    "contact_system_id": "123",
                    "ani": ANI1,
                    "dnis": DNIS,
                    "transfer_routing": transfer_routing,
                    "end_time": datetime.now() - timedelta(minutes=2)
                }
            ])

        call_service = CallService(db_session)
        transferred_call, reason = call_service.get_recent_transferred_call(ani=ANI1, dnis=DNIS)
        assert transferred_call is None
        assert reason == "call too old"

    def test_get_sip_headers(self, db_session):
        test_call = cf.call_factory(db_session).create(
            device_identifier=ANI1,
            inbound_target=DNIS,
            secured_key="abc",
            customer_id="456",
            contact_legs=[
                {
                    "contact_system": "test",
                    "contact_system_id": "123",
                    "ani": ANI1,
                    "dnis": DNIS
                }
            ]
        )

        headers = {
            "X-Ava-Secure-Key": "abc",
            "X-Ava-Customer-ID": "456",
            "X-Ava-Call-ID": test_call.global_id,
            "X-Ava-Tele-Info": f"${ANI1}:${DNIS}"
        }

        call_service = CallService(db_session)
        test_call_leg = test_call.contact_legs[0]
        assert call_service.get_sip_headers(test_call_leg) == headers
