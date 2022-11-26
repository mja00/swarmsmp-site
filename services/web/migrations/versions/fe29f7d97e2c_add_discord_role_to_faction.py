"""Add discord role to faction

Revision ID: fe29f7d97e2c
Revises: 39852168ed51
Create Date: 2022-11-26 02:44:07.645115

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fe29f7d97e2c'
down_revision = '39852168ed51'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('factions', sa.Column('discord_role', sa.String(length=255), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('factions', 'discord_role')
    # ### end Alembic commands ###
