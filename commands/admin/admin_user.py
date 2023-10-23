from uuid import UUID

import click

from commands.admin import AdminCommandBase
from ivr_gateway.models.enums import AdminRole


class Admin(AdminCommandBase):

    @click.command()
    @click.option('--username', prompt='Your username',
                  help='LDAP username')
    @click.option('--role', prompt='Your user role', default=AdminRole.admin.value, type=click.Choice(list(map(lambda x: x.value, AdminRole))))
    @click.option('--short_id', prompt='Your short id')
    @click.option('--pin', prompt='Your pin')
    @click.option('--phone-number', prompt='What is the phone number you would like use to make calls, '
                                           'i.e. 14432351191?')
    @click.option('--upsert', prompt='Update existing admin information with the same username', is_flag=True)
    def create_user(self, username, role, short_id, pin, phone_number, upsert) -> None:
        """
        flask admin create-user
        :param username: your LDAP username
        :param role:     role of user you want to create
        :param short_id: your shortid
        :param pin:      your pin
        :param phone_number:   phone number you would like to use to make calls , i.e. 14432351191
        :param upsert:         option to update existing user or create new if none exists
        :return:
        """

        if upsert:
            status = 'updated'
            user = self.admin_service.upsert_admin_user_by_name(
                name=username, role=role, short_id=short_id, pin=pin
            )
            user_phone_number = self.admin_service.upsert_admin_phone_number(
                name=f"{user.name} personal", user_id=user.id, phone_number=phone_number
            )
        else:
            status = 'created'
            user = self.admin_service.create_admin_user(name=username, role=role, short_id=short_id, pin=pin)
            user_phone_number = self.admin_service.create_admin_phone_number_with_user_id(name=f"{user.name} personal",
                                                                                          user_id=user.id,
                                                                                          phone_number=phone_number)

        click.echo('Hello %s!' % username)
        click.echo(f"Your user with username of {user.name} has been {status}.")
        click.echo(f"Your user id is: {user.id}")
        click.echo(f"Your phone number of {user_phone_number.phone_number} has been {status}")

    @click.command()
    @click.option('--user_id', prompt="Your user id")
    @click.option('--name', prompt="Name of phone number")
    @click.option('--phone_number', prompt="Enter phone number (i.e 14432351191)")
    @click.option('--upsert', prompt='Update an existing phone number', is_flag=True)
    def add_phone_number(self, user_id, name, phone_number, upsert) -> None:
        """
        flask admin add-phone-number
        :param user_id:
        :param name:
        :param phone_number:
        :param upsert:
        :return:
        """
        """Creates an admin phone number"""
        user_id = UUID(user_id)

        if upsert:
            status = 'updated'
            phone_number = self.admin_service.upsert_admin_phone_number(name=name, user_id=user_id, phone_number=phone_number)
        else:
            status = 'created'
            phone_number = self.admin_service.create_admin_phone_number_with_user_id(name=name, user_id=user_id, phone_number=phone_number)

        click.echo(f"Your phone number {phone_number.phone_number} has been {status}.")
        click.echo(f"Your phone number id is: {phone_number.id}")

    @click.command()
    @click.option('--user_id', prompt="Your user id")
    def create_credential(self, user_id) -> None:
        """
        flask admin create-credential
        :param user_id:
        :return:
        """
        """Creates an admin credential"""
        user_id = UUID(user_id)
        user = self.admin_service.get_user_by_id(user_id)
        if user is None:
            click.echo(f"could not find user with id {user_id}")
            return
        cred = self.admin_service.create_api_credential_for_admin_user(user_id)
        click.echo(f"api key: {cred.key}")
        click.echo(f"api secret: {cred.secret}")


