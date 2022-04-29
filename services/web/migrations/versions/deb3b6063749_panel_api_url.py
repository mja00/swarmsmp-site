"""Panel api url

Revision ID: deb3b6063749
Revises: 9291a45801f6
Create Date: 2022-04-29 15:34:17.843972

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'deb3b6063749'
down_revision = '9291a45801f6'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('system_settings', sa.Column('panel_api_url', sa.String(length=255), nullable=True))
    op.execute("UPDATE system_settings SET panel_api_url = 'https://panel.example.com/api/v1/'")
    op.alter_column('system_settings', 'panel_api_url', nullable=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('system_settings', 'panel_api_url')
    # ### end Alembic commands ###
