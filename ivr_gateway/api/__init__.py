from typing import Optional

import sqlalchemy
from flask_restx import Resource
from sqlalchemy import orm

from ivr_gateway.api.exceptions import DuplicateDatabaseEntryException
from ivr_gateway.db import session_scope


class APIResource(Resource):
    _db_session: Optional[orm.Session] = None

    def dispatch_request(self, *args, **kwargs):
        try:
            with session_scope() as session:
                self._db_session = session
                return super().dispatch_request(*args, **kwargs)
        except sqlalchemy.exc.IntegrityError as e:
            raise DuplicateDatabaseEntryException(*e.args)

    def get_db_session(self) -> orm.Session:
        if self._db_session is None:
            raise ValueError("Missing database session, must call from inside a dispatched request")
        return self._db_session
