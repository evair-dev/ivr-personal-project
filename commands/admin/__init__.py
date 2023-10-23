from commands.base import DbCommandBase
from ivr_gateway.services.admin import AdminService


class AdminCommandBase(DbCommandBase):

    @property
    def admin_service(self) -> AdminService:
        return AdminService(self.db_session)
