from marshmallow import fields

from ivr_gateway.serde import BaseSchema
from ivr_gateway.steps.action import StepAction, NumberedStepAction


class StepActionSchema(BaseSchema):
    __model__ = StepAction

    name = fields.Str()
    display_name = fields.Str()
    is_finish = fields.Bool()
    is_replay = fields.Bool()
    emphasized = fields.Bool()
    secondary = fields.Bool()
    opts = fields.Dict()

class NumberedStepActionSchema(BaseSchema):
    __model__ = NumberedStepAction

    name = fields.Str()
    display_name = fields.Str()
    is_finish = fields.Bool()
    is_replay = fields.Bool()
    emphasized = fields.Bool()
    secondary = fields.Bool()
    opts = fields.Dict()
    number = fields.Str()