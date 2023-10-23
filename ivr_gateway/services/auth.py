import logging
import os
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

import jwt
from sqlalchemy.orm.session import Session as SQLAlchemySession
from ivr_gateway.models.admin import AdminUser
from ivr_gateway.services.admin import AdminService

logger = logging.getLogger("auth-service")

TOKEN_KEY = os.getenv("TOKEN_KEY", "TOKEN_SECRET")


class AuthService:

    def __init__(self, db_session: SQLAlchemySession):
        self.session = db_session
        self.admin_service = AdminService(db_session)

    def get_user_from_token(self, token: str) -> Optional[AdminUser]:
        user_id = self.decode_token(token)
        if user_id is None:
            return None
        return self.admin_service.get_user_by_id(UUID(user_id))

    @staticmethod
    def decode_token(token: str):
        if token is None:
            return None
        try:
            decoded = jwt.decode(token, TOKEN_KEY, algorithms=['HS256'])
            logger.debug(f"jwt subject: {decoded.get('sub')}")
            return decoded.get("sub")
        except jwt.exceptions.InvalidTokenError:
            return None

    @staticmethod
    def get_token(user: AdminUser) -> str:
        jwt_payload = {"sub": str(user.id),
                       "role": str(user.role),
                       'exp': datetime.utcnow() + timedelta(hours=168)}
        logger.debug(f"jwt subject: {jwt_payload['sub']}")
        encoded = jwt.encode(jwt_payload, TOKEN_KEY, algorithm='HS256')
        return encoded
