from marshmallow import fields

from ivr_gateway.serde import BaseSchema
from ivr_gateway.steps.config import StepTree, Step, StepBranch


class StepSchema(BaseSchema):
    __model__ = Step

    name = fields.String()
    step_type = fields.String()
    step_kwargs = fields.Dict()
    exit_path = fields.Dict(allow_none=True, missing=None)


class StepBranchSchema(BaseSchema):
    __model__ = StepBranch

    name = fields.String()
    steps = fields.List(fields.Nested(StepSchema))
    reset_on_switch = fields.Boolean()


class StepTreeSchema(BaseSchema):
    __model__ = StepTree

    branches = fields.List(fields.Nested(StepBranchSchema))
