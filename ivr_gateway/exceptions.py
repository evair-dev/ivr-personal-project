class MissingAuthenticationException(Exception):
    pass


class InvalidResponseException(Exception):
    pass


class NonUpdateableModelError(AttributeError):
    def __init__(self, target, message=None):
        self.target = target

        if message is None:
            self.message = f'Cannot update model object {target.__class__.__name__}: model is non-updateable.'


class InvalidQueueConfigException(Exception):
    pass


class InvalidRoutingConfigException(Exception):
    pass
