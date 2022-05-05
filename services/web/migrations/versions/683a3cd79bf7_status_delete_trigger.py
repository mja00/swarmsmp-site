"""Status delete trigger

Revision ID: 683a3cd79bf7
Revises: 406cdf7b4990
Create Date: 2022-05-05 13:49:17.808241

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '683a3cd79bf7'
down_revision = '406cdf7b4990'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE FUNCTION delete_old_statuses() RETURNS trigger language plpgsql AS $$ BEGIN DELETE FROM server_status WHERE created_at < now() - INTERVAL '1 day'; RETURN NULL; END; $$;")
    op.execute("CREATE TRIGGER trigger_delete_old_statuses AFTER INSERT ON server_status EXECUTE PROCEDURE delete_old_statuses();")


def downgrade():
    op.execute("DROP TRIGGER trigger_delete_old_statuses ON server_status;")
    op.execute("DROP TRIGGER delete_old_statuses;")
