"""Site theme

Revision ID: 8e8ba38bf52e
Revises: f5775ba480ab
Create Date: 2022-04-16 14:24:40.252323

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8e8ba38bf52e'
down_revision = 'f5775ba480ab'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('system_settings', sa.Column('site_theme', sa.String(length=255), nullable=True))
    op.execute("UPDATE system_settings SET site_theme = 'darkly'")
    op.alter_column('system_settings', 'site_theme', nullable=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('system_settings', 'site_theme')
    # ### end Alembic commands ###
