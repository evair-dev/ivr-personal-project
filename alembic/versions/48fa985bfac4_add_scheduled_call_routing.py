"""add_scheduled_call_routing

Revision ID: 48fa985bfac4
Revises: c402912c0795
Create Date: 2021-03-04 16:02:59.687107

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '48fa985bfac4'
down_revision = 'c402912c0795'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('scheduled_call', sa.Column('routing_phone_number', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('scheduled_call', 'routing_phone_number')
    # ### end Alembic commands ###
