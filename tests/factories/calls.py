import factory
from factory.alchemy import SESSION_PERSISTENCE_COMMIT
from collections.abc import Iterable
from uuid import uuid4

from ivr_gateway.models.contacts import Contact, ContactLeg


def call_factory(session):
    class _CallFactory(factory.alchemy.SQLAlchemyModelFactory):
        class Meta:
            model = Contact
            sqlalchemy_session = session
            sqlalchemy_session_persistence = SESSION_PERSISTENCE_COMMIT  # Commits the session after creating the object

        id = uuid4()

        @factory.post_generation
        def contact_legs(obj, create, extracted, **kwargs):
            if not create:
                # Simple build, do nothing.
                return
            ContactLeg = contact_leg_factory(session)
            print(f"Extracted: {extracted}")
            if extracted and isinstance(extracted, Iterable):
                for extracted_e in extracted:
                    ContactLeg.create(
                        contact=obj,
                        **extracted_e
                    )
            else:
                ContactLeg.create(
                    contact=obj,
                    contact_system="test",
                    contact_system_id="123"
                )

    return _CallFactory


def contact_leg_factory(session):
    class _CallLegFactory(factory.alchemy.SQLAlchemyModelFactory):
        class Meta:
            model = ContactLeg
            sqlalchemy_session = session

    return _CallLegFactory
