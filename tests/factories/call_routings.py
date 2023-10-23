import factory

from ivr_gateway.models.contacts import InboundRouting


def inbound_routing_factory(session):
    class _CallRoutingFactory(factory.alchemy.SQLAlchemyModelFactory):
        class Meta:
            model = InboundRouting
            sqlalchemy_session = session

        active = True
        operating_mode = "normal"

    return _CallRoutingFactory
