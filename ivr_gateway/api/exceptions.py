from flask import jsonify, Response


class InvalidAPIRequestException(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        super().__init__()
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv


class MissingResourceException(InvalidAPIRequestException):
    status_code = 404


class MissingInboundRoutingException(MissingResourceException):
    pass


class MissingAdminUserException(MissingResourceException):
    pass


class MissingAdminPhoneException(MissingResourceException):
    pass


class MissingAdminCallException(MissingResourceException):
    pass


class MissingWorkflowException(MissingResourceException):
    pass


class MissingQueueException(MissingResourceException):
    pass


class InvalidAPIAuthenticationException(InvalidAPIRequestException):
    status_code = 401


class DuplicateDatabaseEntryException(InvalidAPIRequestException):
    status_code = 400


class AmountCardActivationException(Exception):
    status_code = 400


def serialize_exception_to_response(e: InvalidAPIRequestException) -> Response:
    resp = jsonify(e.to_dict())
    resp.status_code = e.status_code
    return resp
