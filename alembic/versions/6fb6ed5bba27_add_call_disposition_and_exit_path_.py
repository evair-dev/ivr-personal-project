"""add_call_disposition_and_exit_path_fields

Revision ID: 6fb6ed5bba27
Revises: f4d22ae3bd91
Create Date: 2021-01-21 20:05:14.451520

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '6fb6ed5bba27'
down_revision = 'f4d22ae3bd91'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('call_leg', sa.Column('disposition_kwargs', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('call_leg', sa.Column('disposition_type', sa.String(), nullable=True))
    op.add_column('workflow_run', sa.Column('exit_path_kwargs', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('workflow_run', sa.Column('exit_path_type', sa.String(), nullable=True))
    op.drop_column('call_leg', 'active')
    op.drop_column('call_leg', 'backend')
    op.drop_column('workflow', 'external')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('workflow', sa.Column('external', sa.BOOLEAN(), server_default="False", nullable=False))
    op.add_column('call_leg', sa.Column('backend', sa.String(), server_default="gateway", nullable=False))
    op.add_column('call_leg', sa.Column('active', sa.BOOLEAN(), autoincrement=False, nullable=True))
    bind = op.get_bind()
    bind.execute("UPDATE call_leg set active = False WHERE end_time IS NULL")
    op.drop_column('workflow_run', 'exit_path_type')
    op.drop_column('workflow_run', 'exit_path_kwargs')
    op.drop_column('call_leg', 'disposition_type')
    op.drop_column('call_leg', 'disposition_kwargs')
    # ### end Alembic commands ###