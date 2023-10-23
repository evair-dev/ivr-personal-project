import os
import random

import pytest
from flask.testing import FlaskClient
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session as SQLAlchemySession, sessionmaker, scoped_session

from ivr_gateway import db
from ivr_gateway.app import app
from commands import base as commands_base
from ivr_gateway.models import Base


@pytest.fixture(scope="session", autouse=True)
def db_connection(request) -> Connection:
    """Creates a new database engine and session factory for a pytest session."""
    engine = db.create_sqlalchemy_engine(db.get_sqlalchemy_url())
    connection = engine.connect()
    Base.metadata.create_all(engine)

    def teardown():
        Base.metadata.drop_all(engine)
        connection.close()

    request.addfinalizer(teardown)
    return connection


@pytest.fixture(scope="function", autouse=True)
def db_session(request, db_connection) -> SQLAlchemySession:
    """Creates a new database session for a test."""
    transaction = db_connection.begin()
    session_factory = sessionmaker(
        bind=db_connection,
        expire_on_commit=False
    )
    Session = scoped_session(session_factory)
    db.Session = Session
    commands_base.Session = Session
    session = Session()

    def teardown():
        session.rollback()
        transaction.rollback()
        Session.remove()

    request.addfinalizer(teardown)
    return session


@pytest.fixture(scope='session')
def test_client() -> FlaskClient:
    # Flask provides a way to test your application by exposing the Werkzeug test Client
    # and handling the context locals for you.
    testing_client = app.test_client()
    app.config['TESTING'] = True
    app.config['SERVER_NAME'] = os.environ["SERVER_NAME"]
    # Establish an application context before running the tests.
    ctx = app.app_context()
    ctx.push()

    yield testing_client  # this is where the testing happens!

    ctx.pop()


@pytest.fixture(scope='session')
def test_cli_runner():
    return app.test_cli_runner()



@pytest.fixture(scope="function")
def predictable_random() -> random.Random:
    random.seed(1337)
    yield random
