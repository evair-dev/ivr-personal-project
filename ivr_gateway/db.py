import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session


def get_sqlalchemy_url():
    return os.getenv("DATABASE_URL")


def create_sqlalchemy_engine(uri):
    return create_engine(uri, pool_pre_ping=True)


def create_sqlalchemy_session_factory():
    return sessionmaker(
        bind=create_sqlalchemy_engine(get_sqlalchemy_url()),
        expire_on_commit=False
    )


Session = scoped_session(create_sqlalchemy_session_factory())


@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    session = Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
