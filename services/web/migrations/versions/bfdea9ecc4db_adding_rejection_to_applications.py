"""Adding rejection to applications

Revision ID: bfdea9ecc4db
Revises: 8f26d40bbe76
Create Date: 2022-04-12 18:54:58.809376

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bfdea9ecc4db'
down_revision = '8f26d40bbe76'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('applications', sa.Column('is_rejected', sa.Boolean(), nullable=False))
    op.alter_column('characters', 'faction_id',
               existing_type=sa.INTEGER(),
               nullable=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('characters', 'faction_id',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.drop_column('applications', 'is_rejected')
    # ### end Alembic commands ###