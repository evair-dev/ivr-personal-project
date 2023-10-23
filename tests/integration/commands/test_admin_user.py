import pytest

from sqlalchemy.orm import Session as SQLAlchemySession

from commands.admin.admin_user import Admin
from ivr_gateway.models.admin import AdminUser


class TestAdminUserCommand:
    @pytest.fixture
    def admin_user(self, db_session: SQLAlchemySession) -> AdminUser:
        admin_user = AdminUser(
            name="Mister Admin",
            short_id="1234",
            pin="5678",
            role="user"
        )
        db_session.add(admin_user)
        db_session.commit()
        return admin_user

    def test_create_admin_user(self, test_cli_runner):
        result = test_cli_runner.invoke(Admin.create_user,
                                        args=['--username', 'TestName', '--role', 'admin', '--short_id', '1234',
                                              '--pin', '1234', '--phone-number', '17735558355'])
        assert "Your user with username of TestName has been created." in result.output
        assert "Your phone number of 17735558355 has been created" in result.output

    def test_create_admin_user_upsert(self, test_cli_runner):
        first_result = test_cli_runner.invoke(Admin.create_user,
                                              args=['--username', 'TestName', '--role', 'admin', '--short_id', '1234',
                                                    '--pin', '1234', '--phone-number', '17735558355', '--upsert'])
        assert "Your user with username of TestName has been updated." in first_result.output
        assert "Your phone number of 17735558355 has been updated" in first_result.output

        second_result = test_cli_runner.invoke(Admin.create_user,
                                               args=['--username', 'TestName', '--role', 'admin', '--short_id', '4321',
                                                     '--pin', '4321', '--phone-number', '17735558366', '--upsert'])
        assert "Your user with username of TestName has been updated." in second_result.output
        assert "Your phone number of 17735558366 has been updated" in second_result.output

    def test_create_admin_phone_number(self, db_session, test_cli_runner, admin_user):
        result = test_cli_runner.invoke(Admin.add_phone_number,
                                        args=['--user_id', str(admin_user.id), '--name', 'TestName', '--phone_number',
                                              "17738738833"])
        assert "Your phone number 17738738833 has been created." in result.output

    def test_create_admin_phone_number_upsert(self, db_session, test_cli_runner, admin_user):
        first_result = test_cli_runner.invoke(Admin.add_phone_number,
                                              args=['--user_id', str(admin_user.id), '--name', 'TestName',
                                                    '--phone_number',
                                                    "17738738833", '--upsert'])
        assert "Your phone number 17738738833 has been updated." in first_result.output

        second_result = test_cli_runner.invoke(Admin.add_phone_number,
                                               args=['--user_id', str(admin_user.id), '--name', 'TestName',
                                                     '--phone_number',
                                                     "17738738866", '--upsert'])
        assert "Your phone number 17738738866 has been updated." in second_result.output
