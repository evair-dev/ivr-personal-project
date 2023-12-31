"""add_workflow_config_tag

Revision ID: e17699eb7074
Revises: 6fb6ed5bba27
Create Date: 2021-01-26 01:33:13.404788

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e17699eb7074'
down_revision = 'c2753d4b4335'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('workflow', sa.Column('active_config_tag', sa.String(), nullable=True))
    op.add_column('workflow_config', sa.Column('tag', sa.String(), nullable=True))
    op.create_index(op.f('ix_workflow_config_tag'), 'workflow_config', ['tag'], unique=False)
    op.create_unique_constraint('unique_workflow_config_tag_for_workflow', 'workflow_config', ['workflow_id', 'tag'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('unique_workflow_config_tag_for_workflow', 'workflow_config', type_='unique')
    op.drop_index(op.f('ix_workflow_config_tag'), table_name='workflow_config')
    op.drop_column('workflow_config', 'tag')
    op.drop_column('workflow', "active_config_tag")
    # ### end Alembic commands ###
