"""create_state_linkback_to_workflow_step_run

Revision ID: 832162cc2c97
Revises: e17699eb7074
Create Date: 2021-02-02 15:41:44.909337

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '832162cc2c97'
down_revision = 'e17699eb7074'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('workflow_step_run', sa.Column('step_state_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('workflow_step_run_step_state_id_fkey', 'workflow_step_run', 'step_state', ['step_state_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('workflow_step_run_step_state_id_fkey', 'workflow_step_run', type_='foreignkey')
    op.drop_column('workflow_step_run', 'step_state_id')
    # ### end Alembic commands ###
