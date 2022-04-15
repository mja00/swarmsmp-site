"""Factions

Revision ID: 58afc5450eea
Revises: 3e7cafc41f05
Create Date: 2022-04-12 18:41:19.562151

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '58afc5450eea'
down_revision = '3e7cafc41f05'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('factions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('factions')
    # ### end Alembic commands ###