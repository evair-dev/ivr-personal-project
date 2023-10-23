import copy
import inspect
import re
import warnings
from typing import Optional, Type

import click
from flask.cli import AppGroup
from sqlalchemy import orm

from ivr_gateway.db import Session


# TODO: Note how we modified this comparative to the original solution
# modified to work with Flask from https://larkost.github.io/larkost/tech/Python_Click_with_Classes.html#the-code
class ClickInstantiator:
    klass = None
    command = None

    def __init__(self, command, klass):
        self.command = command
        self.klass = klass

    def __call__(self, *args, **kwargs):
        klass_instance = self.klass()
        self.before_call(klass_instance)
        _exception = None
        try:
            result = self.command(klass_instance, *args, **kwargs)
            return result
        except BaseException as e:
            _exception = e
        finally:
            self.after_call(klass_instance, e=_exception)

    def handle_exception(self, e):
        raise e

    @staticmethod
    def before_call(self: "ClickCommandBase"):
        pass

    @staticmethod
    def after_call(self: "ClickCommandBase", e: BaseException = None):
        pass


class ClickCommandMetaclass(type):
    def __new__(mcs, name, bases, dct):
        klass: Type["ClickCommandBase"] = super().__new__(mcs, name, bases, dct)
        # create and populate the click.Group for this Class
        klass.click_group = AppGroup(name=re.sub(r'(?<!^)(?=[A-Z])', '-', klass.__name__).lower())

        # warn about @click.command decorators missing the parens
        for name, command in inspect.getmembers(klass, inspect.isfunction):
            if repr(command).startswith('<function command.'):
                warnings.warn(
                    '%s.%s is wrapped with click.command without parens, please add them' % (klass.__name__, name))

        for name, command in inspect.getmembers(klass, lambda x: isinstance(x, click.Command)):
            if name == 'click_group':
                continue

            def find_final_command(target):
                """Find the last call command at the end of a stack of click.Command instances"""
                while isinstance(target.callback, click.Command):
                    target = target.callback
                return target

            command_target = find_final_command(command)

            if not isinstance(command_target.callback, ClickInstantiator):
                # the top class to implement this
                command_target.callback = ClickInstantiator(command_target.callback, klass)
                mcs.register_event_hook_callbacks_from_target_class(command_target.callback, klass)
            else:
                # this is a subclass function, copy it and replace the klass
                setattr(klass, name, copy.deepcopy(command))
                command = getattr(klass, name)
                find_final_command(getattr(klass, name)).callback.klass = klass

            # now add it to the group
            klass.click_group.add_command(command, name.replace("_", "-"))
        return klass

    @staticmethod
    def register_event_hook_callbacks_from_target_class(ci: ClickInstantiator, ccb: Type["ClickCommandBase"]):
        ci.before_call = ccb.before_call
        ci.after_call = ccb.after_call


class ClickCommandBase(metaclass=ClickCommandMetaclass):
    def before_call(self):
        pass

    def after_call(self, e: BaseException = None):
        pass


class Base(ClickCommandBase):
    def before_call(self):
        pass

    def after_call(self, e: BaseException = None):
        pass


class DbCommandBase(Base):
    _db_session: Optional[orm.Session] = None

    def before_call(self):
        super().before_call()
        self._db_session = Session()

    def after_call(self, e: BaseException = None):
        super().after_call(e=e)
        if e is not None:
            self._db_session.rollback()
            raise e
        else:
            self._db_session.commit()
        self._db_session.close()
        self._db_session = None

    @property
    def db_session(self):
        if self._db_session is None:
            raise Exception()
        return self._db_session
