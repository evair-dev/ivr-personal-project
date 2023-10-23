import factory

from ivr_gateway.models.contacts import TransferRouting


def transfer_routing_factory(session):
    class _TransferRoutingFactory(factory.alchemy.SQLAlchemyModelFactory):
        class Meta:
            model = TransferRouting
            sqlalchemy_session = session

        operating_mode = "normal"
        priority = 0

    return _TransferRoutingFactory
