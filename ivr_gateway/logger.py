import base64
import datetime

import binascii
import logging
import os

from gunicorn.glogging import Logger

from ivr_gateway.request_log_formatter import RequestFormatter

ivr_logger = logging.getLogger('ivr.logger')


def log_format(log_level):
    if log_level == logging.DEBUG:
        return '[%(asctime)s.%(msecs)03d] [%(levelname)s] request_id: [%(request_id)s] %(filename)s%(module)s:%(funcName)s %(message)s'
    return '[%(asctime)s.%(msecs)03d] [%(levelname)s] request_id: [%(request_id)s] %(message)s'


def setup_log_handler(logger, handler=None, defined_log_level=None):
    if handler is None:
        handler = logging.StreamHandler()
    log_level = (defined_log_level or os.getenv("LOG_LEVEL") or logging.WARNING)
    handler.setLevel(log_level)
    formatter = RequestFormatter(
        log_format(handler.level),
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class BearerLogger(Logger):

    def _get_user(self, environ):
        user = None
        http_auth = environ.get("HTTP_AUTHORIZATION")
        if http_auth and http_auth.lower().startswith('bearer'):
            auth = http_auth.split(" ", 1)
            if len(auth) == 2:
                try:
                    # b64decode doesn't accept unicode in Python < 3.3
                    # so we need to convert it to a byte string
                    auth = base64.b64decode(auth[1].strip().encode('utf-8'))
                    # b64decode returns a byte string
                    auth = auth.decode('utf-8')
                    auth = auth.split(":", 1)
                except (TypeError, binascii.Error, UnicodeDecodeError) as exc:
                    self.debug("Couldn't get username: %s", exc)
                    return user
                if len(auth) == 2:
                    user = auth[0]
        return user

    def now(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        return f"[{now.strftime('%d/%b/%Y:')}{now.time().isoformat(timespec='milliseconds')} {now.strftime('%z')}]"