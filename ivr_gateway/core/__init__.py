from flask import Blueprint
from flask_restx import A000pi

import ivr_gateway.steps.dynamic_import  # noqa: F401
from ivr_gateway.db import session_scope

blueprint = Blueprint('core', __name__)

api = Api(blueprint, version='1.0', title='IVR Gateway', description='Core Endpoints For IVR Gateway')


@blueprint.route("/", methods=["GET"])
def index():
    return "Hello IVR World"


@blueprint.route("/heartbeat", methods=["GET"])
def heartbeat():
    with session_scope() as session:

        session.execute('SELECT 1')

        return "OK"



@blueprint.route("/ping", methods=["GET"])
def ping():
    return "pong"
