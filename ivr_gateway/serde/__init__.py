from abc import abstractmethod

from marshmallow import Schema, post_load


class BaseSchema(Schema):
    @property
    @abstractmethod
    def __model__(self):  # pragma: no cover
        pass

    @post_load
    def make_object(self, data: dict, **kwargs):
        return self.__model__(**data)
