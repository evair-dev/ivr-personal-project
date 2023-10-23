import os
import secrets
from typing import Optional, Iterable
from uuid import UUID

from sqlalchemy.orm import joinedload
from sqlalchemy.orm.session import Session as SQLAlchemySession

from ivr_gateway.models.admin import AdminCall, AdminUser, AdminCallFrom, AdminCallTo, AdminPhoneNumber, ScheduledCall, \
    ApiCredential
from ivr_gateway.models.contacts import InboundRouting
from ivr_gateway.models.encryption import active_encryption_key_fingerprint
from ivr_gateway.models.enums import AdminRole
from ivr_gateway.models.workflows import Workflow
from ivr_gateway.utils import modify_object_with_dict


class AdminService:
    encryption_key_var = os.environ["ACTIVE_ENCRYPTION_KEY"]

    def __init__(self, db_session: SQLAlchemySession):
        self.session = db_session
        self.encryption_key = os.environ[self.encryption_key_var]

    def get_all_admin_users(self) -> Iterable:
        return (self.session.query(AdminUser)
                .all())

    def get_all_phone_numbers(self) -> Iterable:
        return (self.session.query(AdminPhoneNumber)
                .all())

    def get_all_phone_numbers_by_user_id(self, user_id: UUID):
        return (self.session.query(AdminPhoneNumber)
                .filter(AdminPhoneNumber.user_id == user_id)
                .all())

    def verify_password(self, username, password):
        return True

    def get_all_calls(self) -> Iterable:
        return (self.session.query(AdminCall)
                .all())

    def get_all_scheduled_calls(self) -> Iterable:
        return (self.session.query(ScheduledCall)
                .all())

    def find_admin_phone_number_by_id(self, admin_phone_number_id: UUID) -> Optional[AdminPhoneNumber]:
        return (self.session.query(AdminPhoneNumber)
                .filter(AdminPhoneNumber.id == admin_phone_number_id)
                .first())

    def find_admin_phone_number_by_user_id(self, admin_user_id: UUID) -> Optional[AdminPhoneNumber]:
        return (self.session.query(AdminPhoneNumber)
                .filter(AdminPhoneNumber.user_id == admin_user_id)
                .first())

    def find_admin_phone_number(self, phone_number: str) -> Optional[AdminPhoneNumber]:
        return (self.session.query(AdminPhoneNumber)
                .options(joinedload(AdminPhoneNumber.user))
                .filter(AdminPhoneNumber.phone_number == phone_number)
                .first())

    def find_admin_user_by_phone_number(self, phone_number: str) -> Optional[AdminUser]:
        return (self.session.query(AdminUser)
                .join(AdminUser.phone_numbers)
                .filter(AdminPhoneNumber.phone_number == phone_number)
                .first())

    def find_admin_user_by_short_id(self, short_id: str) -> Optional[AdminUser]:
        return (self.session.query(AdminUser)
                .filter(AdminUser.short_id == short_id)
                .first())

    def find_admin_user(self, user_id: UUID) -> Optional[AdminUser]:
        return (self.session.query(AdminUser)
                .filter(AdminUser.id == user_id)
                .first())

    def find_admin_user_by_name(self, name: str) -> Optional[AdminUser]:
        return (self.session.query(AdminUser)
                .filter(AdminUser.name == name)
                .first())

    def find_admin_call(self, telephony_system: str, telephony_system_id: str) -> AdminCall:
        return (self.session.query(AdminCall)
                .options(joinedload(AdminCall.user))
                .filter(AdminCall.contact_system_id == telephony_system_id)
                .filter(AdminCall.contact_system == telephony_system)
                .first())

    def find_admin_call_by_id(self, admin_call_id: UUID) -> Optional[AdminCall]:
        return (self.session.query(AdminCall)
                .options(joinedload(AdminCall.user))
                .filter(AdminCall.id == admin_call_id)
                .first())

    def find_scheduled_call_by_id(self, scheduled_call_id: UUID) -> Optional[ScheduledCall]:
        return (self.session.query(ScheduledCall)
                .options(joinedload(ScheduledCall.user))
                .filter(ScheduledCall.id == scheduled_call_id)
                .first())

    def find_scheduled_call(self, user: AdminUser) -> Optional[ScheduledCall]:
        return (self.session.query(ScheduledCall)
                .options(joinedload(ScheduledCall.inbound_routing))
                .filter(ScheduledCall.user == user)
                .filter(ScheduledCall.admin_call_id == None)  # NOQA: E711
                .first())

    def create_admin_user(self, name: str, short_id: str, pin: str, role: str) -> AdminUser:
        user = AdminUser()
        user.name = name
        user.short_id = short_id
        user.pin = pin
        user.role = AdminRole(role)
        self.session.add(user)
        self.session.commit()
        return user

    def update_admin_user(self, user_id: UUID, **kwargs) -> Optional[AdminUser]:
        user = self.find_admin_user(user_id)
        if user is None:
            return None

        modify_object_with_dict(user, kwargs)

        self.session.add(user)
        self.session.commit()
        return user

    def update_admin_user_by_name(self, name: str, **kwargs) -> Optional[AdminUser]:
        user = self.find_admin_user_by_name(name)
        if user is None:
            return None

        modify_object_with_dict(user, kwargs)

        self.session.add(user)
        self.session.commit()
        return user

    def upsert_admin_user_by_name(self, name: str, **kwargs) -> Optional[AdminUser]:
        user = self.find_admin_user_by_name(name)

        if user is None:
            user = self.create_admin_user(name=name, **kwargs)
            return user

        modify_object_with_dict(user, kwargs)

        self.session.add(user)
        self.session.commit()
        return user

    def delete_admin_user(self, user_id: UUID) -> Optional[AdminUser]:
        user = self.find_admin_user(user_id)

        if user is None:
            return None

        self.session.delete(user)
        self.session.commit()
        return user

    def create_admin_phone_number_with_user_id(self, user_id: UUID, name: str, phone_number: str):
        user = self.find_admin_user(user_id)
        admin_phone_number = AdminPhoneNumber()
        admin_phone_number.name = name
        admin_phone_number.phone_number = phone_number
        admin_phone_number.user = user

        self.session.add(admin_phone_number)
        self.session.add(user)
        self.session.commit()

        return admin_phone_number

    def create_admin_phone_number(self, user_short_id: str, name: str, phone_number: str) -> AdminPhoneNumber:
        user = self.find_admin_user_by_short_id(user_short_id)
        admin_phone_number = AdminPhoneNumber()
        admin_phone_number.name = name
        admin_phone_number.phone_number = phone_number
        user.phone_numbers.append(admin_phone_number)

        self.session.add(admin_phone_number)
        self.session.add(user)
        self.session.commit()

        return admin_phone_number

    def update_admin_phone_number(self, phone_number_id: UUID, **kwargs) -> Optional[AdminPhoneNumber]:
        admin_phone_number = self.find_admin_phone_number_by_id(phone_number_id)

        if admin_phone_number is None:
            return None

        modify_object_with_dict(admin_phone_number, kwargs)

        self.session.add(admin_phone_number)
        self.session.commit()

        return admin_phone_number

    def upsert_admin_phone_number(self, user_id: UUID, **kwargs) -> Optional[AdminPhoneNumber]:
        admin_phone_number = self.find_admin_phone_number_by_user_id(user_id)

        if admin_phone_number is None:

            admin_phone_number = self.create_admin_phone_number_with_user_id(user_id, **kwargs)
            return admin_phone_number

        modify_object_with_dict(admin_phone_number, kwargs)

        self.session.add(admin_phone_number)
        self.session.commit()

        return admin_phone_number

    def delete_admin_phone_number(self, admin_phone_number_id: UUID) -> Optional[AdminPhoneNumber]:
        admin_phone_number = self.find_admin_phone_number_by_id(admin_phone_number_id)

        if admin_phone_number is None:
            return None

        self.session.delete(admin_phone_number)

        self.session.commit()
        return admin_phone_number

    def create_admin_call(self, telephony_system: str, telephony_system_id: str, user: AdminUser,
                          ani: str = None, dnis: str = None) -> AdminCall:
        call = AdminCall()
        call.contact_system_id = telephony_system_id
        call.contact_system = telephony_system
        call.user = user
        call.original_ani = ani
        call.original_dnis = dnis
        self.session.add(call)
        self.session.commit()
        return call

    def create_scheduled_call(self, user_id: UUID, ani: str, dnis: str, call_routing_id: str) -> ScheduledCall:
        scheduled_call = ScheduledCall()
        scheduled_call.user_id = user_id
        scheduled_call.ani = ani
        scheduled_call.dnis = dnis
        scheduled_call.call_routing_id = call_routing_id

        self.session.add(scheduled_call)
        self.session.commit()

        return scheduled_call

    def update_scheduled_call(self, scheduled_call_id: UUID, **kwargs) -> Optional[ScheduledCall]:
        scheduled_call = self.find_scheduled_call_by_id(scheduled_call_id)
        # TODO: should we throw an error here
        if scheduled_call is None:
            return None

        modify_object_with_dict(scheduled_call, kwargs)

        self.session.add(scheduled_call)
        self.session.commit()

        return scheduled_call

    def verify_admin_call(self, call: AdminCall, pin: str) -> bool:
        if call is None:
            return False
        user = call.user
        if user.pin != pin:
            return False
        call.verified = True
        self.session.add(call)
        self.session.commit()
        return True

    def add_ani(self, call: AdminCall, ani: str) -> AdminCall:
        call.ani = ani
        self.session.add(call)
        self.session.commit()
        return call

    def add_dnis(self, call: AdminCall, dnis: str) -> AdminCall:
        call.dnis = dnis
        self.session.add(call)
        self.session.commit()
        return call

    def add_call_routing(self, call: AdminCall, call_routing: InboundRouting) -> AdminCall:
        call.inbound_routing = call_routing
        self.session.add(call)
        self.session.commit()
        return call

    def find_shortcut_ani(self, shortcut: str) -> Optional[AdminCallFrom]:
        return (self.session.query(AdminCallFrom)
                .filter(AdminCallFrom.short_number == shortcut)
                .first())

    def find_shortcut_dnis(self, shortcut: str) -> Optional[AdminCallTo]:
        return (self.session.query(AdminCallTo)
                .filter(AdminCallTo.short_number == shortcut)
                .first())

    def copy_admin_from_scheduled(self, admin_call: AdminCall, scheduled_call: ScheduledCall):
        admin_call.ani = scheduled_call.ani
        admin_call.dnis = scheduled_call.dnis
        admin_call.inbound_routing = scheduled_call.inbound_routing
        scheduled_call.admin_call = admin_call
        self.session.add(admin_call)
        self.session.add(scheduled_call)
        self.session.commit()

    def copy_scheduled_call_from_admin_by_id(self, call_id: UUID) -> Optional[ScheduledCall]:
        admin_call = self.find_admin_call_by_id(call_id)

        if admin_call is None:
            return None

        scheduled_call = ScheduledCall()
        scheduled_call.ani = admin_call.ani
        scheduled_call.dnis = admin_call.dnis
        scheduled_call.inbound_routing = admin_call.inbound_routing
        scheduled_call.user_id = admin_call.user_id
        scheduled_call.admin_call = admin_call
        admin_call.scheduled_call = scheduled_call

        self.session.add(scheduled_call)
        self.session.add(admin_call)
        self.session.commit()

        return scheduled_call

    def get_user_by_credential(self, api_key: str, api_secret: str) -> Optional[AdminUser]:
        return (self.session.query(AdminUser)
                    .join(AdminUser.api_credentials)
                    .filter(ApiCredential.key == api_key, ApiCredential.secret == api_secret)
                    .filter(ApiCredential.active)
                    .one_or_none())

    def get_user_by_id(self, id: UUID):
        return (self.session.query(AdminUser)
                .filter(AdminUser.id == id)
                .one_or_none())

    def create_api_credential_for_admin_user(self, user_id: UUID) -> ApiCredential:
        key = secrets.token_hex(16)
        secret = secrets.token_hex(16)
        cred = ApiCredential(
            user_id=user_id,
            key=key,
            secret=secret,
            encryption_key_fingerprint=active_encryption_key_fingerprint
        )
        self.session.add(cred)
        self.session.commit()
        return cred

    def create_scheduled_call_from_workflow(self, workflow: Workflow, **kwargs) -> ScheduledCall:
        scheduled_call = ScheduledCall()
        scheduled_call.user_id = kwargs.get("user_id")
        scheduled_call.ani = kwargs.get("ani")
        scheduled_call.dnis = kwargs.get("dnis")
        scheduled_call.routing_phone_number = kwargs.get("routing_phone_number")
        scheduled_call.workflow_id = workflow.id
        scheduled_call.workflow_version_tag = kwargs.get("workflow_version_tag")

        self.session.add(scheduled_call)
        self.session.commit()
        return scheduled_call



