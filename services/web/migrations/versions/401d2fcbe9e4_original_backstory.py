"""Original backstory

Revision ID: 401d2fcbe9e4
Revises: d9c32361e027
Create Date: 2022-08-19 03:07:57.056753

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '401d2fcbe9e4'
down_revision = 'd9c32361e027'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('characters', sa.Column('original_backstory', sa.Text(), nullable=False))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('characters', 'original_backstory')
    # ### end Alembic commands ###
