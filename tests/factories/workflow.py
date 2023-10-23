import copy

import factory
from factory.alchemy import SESSION_PERSISTENCE_COMMIT

from ivr_gateway.models.workflows import Workflow, WorkflowConfig
from ivr_gateway.steps.api.v1 import PlayMessageStep
from ivr_gateway.steps.config import StepBranch, StepTree, Step

default_step_tree = StepTree(
    branches=[
        StepBranch(name="root", steps=[
            Step(
                name="step-1",
                step_type=PlayMessageStep.get_type_string(),
                step_kwargs={
                    "template": "Hello from IVR"
                },
                exit_path={
                    "exit_path_type": "ivr_gateway.models.exit_paths.HangUpExitPath",
                }
            )
        ])
    ]
)


def workflow_factory(session,
                     name: str,
                     step_tree: StepTree = None):
    if step_tree:
        step_tree = copy.deepcopy(step_tree)
    _workflow_configs = [WorkflowConfig(step_tree=step_tree or default_step_tree)]

    class _WorkflowFactory(factory.alchemy.SQLAlchemyModelFactory):
        class Meta:
            model = Workflow
            sqlalchemy_session = session  # the SQLAlchemy session object
            sqlalchemy_session_persistence = SESSION_PERSISTENCE_COMMIT  # Commits the session after creating the object

        # id = factory.Sequence(lambda n: n)
        workflow_name = name
        configs = _workflow_configs

    return _WorkflowFactory
