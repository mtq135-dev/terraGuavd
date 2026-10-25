"""Supervisor-owned large areas and mission membership; preserve legacy missions."""
from alembic import op
import sqlalchemy as sa

revision = '0005'
down_revision = '0004'


def upgrade():
    op.create_table('survey_area_assignments',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('name',sa.String(100),nullable=False),
        sa.Column('description',sa.Text,nullable=False),
        sa.Column('operator_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('created_by',sa.String(36),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('boundary',sa.JSON,nullable=False),
        sa.Column('deadline',sa.DateTime(timezone=True)),
        sa.Column('revision',sa.Integer,nullable=False,server_default='1'),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False))
    op.execute('''ALTER TABLE survey_area_assignments ADD COLUMN boundary_geometry geometry(Polygon,4326)
      GENERATED ALWAYS AS (ST_SetSRID(ST_GeomFromGeoJSON(boundary::text),4326)) STORED''')
    op.execute('ALTER TABLE survey_area_assignments ADD CONSTRAINT valid_survey_area CHECK (ST_IsValid(boundary_geometry) AND NOT ST_IsEmpty(boundary_geometry))')
    op.create_index('survey_area_operator_idx','survey_area_assignments',['operator_id'])
    op.execute('CREATE INDEX survey_area_geometry_idx ON survey_area_assignments USING gist(boundary_geometry)')
    op.add_column('missions',sa.Column('assignment_id',sa.String(36),sa.ForeignKey('survey_area_assignments.id'),nullable=True))
    op.create_index('mission_assignment_idx','missions',['assignment_id'])
    op.create_table('survey_area_events',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('assignment_id',sa.String(36),sa.ForeignKey('survey_area_assignments.id'),nullable=False),
        sa.Column('actor_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('kind',sa.String(40),nullable=False),
        sa.Column('snapshot',sa.JSON,nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('survey_area_event_idx','survey_area_events',['assignment_id'])
    op.execute('''CREATE FUNCTION protect_survey_area_events() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Survey area history is append-only'; END; $$''')
    op.execute('CREATE TRIGGER survey_area_history_immutable BEFORE UPDATE OR DELETE ON survey_area_events FOR EACH ROW EXECUTE FUNCTION protect_survey_area_events()')


def downgrade():
    op.drop_table('survey_area_events')
    op.execute('DROP FUNCTION protect_survey_area_events()')
    op.drop_index('mission_assignment_idx',table_name='missions')
    op.drop_column('missions','assignment_id')
    op.drop_table('survey_area_assignments')
