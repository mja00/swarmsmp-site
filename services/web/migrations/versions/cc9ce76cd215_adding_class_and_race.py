"""Adding class and race

Revision ID: cc9ce76cd215
Revises: 683a3cd79bf7
Create Date: 2022-05-09 13:36:44.869799

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cc9ce76cd215'
down_revision = '683a3cd79bf7'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('classes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('hidden', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('races',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('hidden', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )

    # Create a row for both new tables for a hidden default
    op.execute("INSERT INTO classes (name, hidden, created_at, updated_at) VALUES ('Unknown', true, now(), now())")
    op.execute("INSERT INTO races (name, hidden, created_at, updated_at) VALUES ('Unknown', true, now(), now())")


    # We need to change the columns to int instead of string. Also change any rows that have a string value to 0.
    op.alter_column('applications', 'character_class', nullable=True)
    op.execute("UPDATE applications SET character_class = NULL")
    op.execute("ALTER TABLE applications ALTER COLUMN character_class TYPE INTEGER USING character_class::integer")
    op.execute("UPDATE applications SET character_class = 1")
    op.alter_column('applications', 'character_class', nullable=False)
    op.create_foreign_key(None, 'applications', 'classes', ['character_class'], ['id'])

    op.alter_column('applications', 'character_race', nullable=True)
    op.execute("UPDATE applications SET character_race = NULL")
    op.execute("ALTER TABLE applications ALTER COLUMN character_race TYPE INTEGER USING character_race::integer")
    op.execute("UPDATE applications SET character_race = 1")
    op.alter_column('applications', 'character_race', nullable=False)
    op.create_foreign_key(None, 'applications', 'races', ['character_race'], ['id'])

    op.alter_column('characters', 'subrace', nullable=True)
    op.execute("UPDATE characters SET subrace = NULL")
    op.execute("ALTER TABLE characters ALTER COLUMN subrace TYPE INTEGER USING subrace::integer")
    op.execute("UPDATE characters SET subrace = 1")
    op.alter_column('characters', 'subrace', nullable=False)
    op.create_foreign_key(None, 'characters', 'races', ['subrace'], ['id'])

    op.alter_column('characters', 'clazz', nullable=True)
    op.execute("UPDATE characters SET clazz = NULL")
    op.execute("ALTER TABLE characters ALTER COLUMN clazz TYPE INTEGER USING clazz::integer")
    op.execute("UPDATE characters SET clazz = 1")
    op.alter_column('characters', 'clazz', nullable=False)
    op.create_foreign_key(None, 'characters', 'classes', ['clazz'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'characters', type_='foreignkey')
    op.drop_constraint(None, 'characters', type_='foreignkey')
    op.drop_constraint(None, 'applications', type_='foreignkey')
    op.drop_constraint(None, 'applications', type_='foreignkey')
    op.drop_table('races')
    op.drop_table('classes')
    # ### end Alembic commands ###