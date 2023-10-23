from flask import Flask
from commands.admin.admin_user import Admin
from commands.db import Db
from commands.scaffold import Scaffold
from commands.update import Update

cli_command_class_registry = [
    Admin,
    Scaffold,
    Db,
    Update
]


def register_cli(app: Flask):
    for command_class in cli_command_class_registry:
        app.cli.add_command(command_class.click_group)
