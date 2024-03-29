"""Ticket reply time

Revision ID: 42e082a86a0a
Revises: ab018b9414d3
Create Date: 2022-04-12 15:17:06.318993

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '42e082a86a0a'
down_revision = 'ab018b9414d3'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('tickets', sa.Column('last_reply', sa.DateTime(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('tickets', 'last_reply')
    # ### end Alembic commands ###
