import logging
import os

from ddtrace import patch_all
from flask.logging import default_handler
from flask_request_id_header.middleware import RequestID

from ivr_gateway.logger import setup_log_handler, ivr_logger

if os.environ.get("DATADOG_ENV", False):  # pragma: no cover
    patch_all()

from flask import Flask, logging as flask_logging, Response  # noqa: E402
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix  # noqa: E402

from ivr_gateway.core import blueprint as core_blueprint
import ivr_gateway.steps.dynamic_import  # noqa: F401

from ivr_gateway.api.exceptions import InvalidAPIRequestException, serialize_exception_to_response
from ivr_gateway.api.v1 import api_v1_blueprint
from commands import register_cli


app = Flask(__name__)
CORS(app, allow_headers="*", supports_credentials=True)
app.config['REQUEST_ID_UNIQUE_VALUE_PREFIX'] = ""
app.config['PROPAGATE_EXCEPTIONS'] = True
RequestID(app)
app.wsgi_app = ProxyFix(app.wsgi_app)
app_logger = flask_logging.create_logger(app)


if __name__ != "__main__":
    if os.environ.get("GUNICORN_WEBSERVER_ENABLED", "false") == "true":
        gunicorn_logger = logging.getLogger('gunicorn.error')
        app.logger.handlers.extend(gunicorn_logger.handlers)
        app.logger.setLevel(gunicorn_logger.level)
        ivr_logger.setLevel(gunicorn_logger.level)
        setup_log_handler(app.logger, handler=default_handler, defined_log_level=gunicorn_logger.level)
        setup_log_handler(ivr_logger, defined_log_level=gunicorn_logger.level)
    else:
        setup_log_handler(app.logger, handler=default_handler)
        setup_log_handler(ivr_logger)


@app.errorhandler(InvalidAPIRequestException)
def invalid_api_usage_error(err: InvalidAPIRequestException) -> Response:
    resp = serialize_exception_to_response(err)
    return resp


app.register_blueprint(core_blueprint)
app.register_blueprint(api_v1_blueprint)
register_cli(app)


# if __name__ == "__main__":  # pragma: no cover
#     # new_call()
#     app.run()
