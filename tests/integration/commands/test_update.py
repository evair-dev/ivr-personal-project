from commands import Update
from commands.scaffold import Scaffold
from ivr_gateway.models.contacts import InboundRouting, TransferRouting
from ivr_gateway.models.queues import Queue


class TestUpdateCommand:

    def test_update_transfer_routing(self, test_cli_runner, db_session):
        test_cli_runner.invoke(
            Scaffold.setup_dev_from_config_files
            )

        assert db_session.query(InboundRouting).count() == 5
        assert db_session.query(TransferRouting).count() == 13

        test_cli_runner.invoke(
            Update.transfer_routings_from_config_file,
            args=['--queue-config-file', './commands/configs/transfer_routing_config.json']
        )
        assert db_session.query(TransferRouting).count() == 28
        assert db_session.query(TransferRouting).filter(TransferRouting.priority == -1).count() == 11

    def test_update_transfer_routing_weight(self, test_cli_runner, db_session):
        test_cli_runner.invoke(
            Scaffold.setup_dev_from_config_files
            )

        cus_queue = db_session.query(Queue).filter(Queue.name == 'AFC.CC.CUS').first()
        transfer_routings = cus_queue.transfer_routings
        assert len(transfer_routings) == 1

        test_cli_runner.invoke(
            Update.transfer_routings_from_config_file,
            args=['--queue-config-file', './tests/integration/commands/card_cus_90_flex_10_livevox_transfer_config.json']
        )
        cus_queue = db_session.query(Queue).filter(Queue.name == 'AFC.CC.CUS').first()
        transfer_routings = cus_queue.transfer_routings
        assert len(transfer_routings) == 3
        livevox_transfers = [tr for tr in transfer_routings if tr.destination_system == 'LiveVox']
        assert len(livevox_transfers) == 1
        assert livevox_transfers[0].weight == 10
        twilio_transfers = [tr for tr in transfer_routings if tr.destination_system == 'twilio']
        assert len(twilio_transfers) == 1
        assert twilio_transfers[0].weight == 90