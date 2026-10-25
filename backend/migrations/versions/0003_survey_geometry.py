"""Retain final coverage snapshots as indexed PostGIS geometry as well as GeoJSON."""
from alembic import op

revision='0003'
down_revision='0002'


def upgrade():
    op.execute('ALTER TABLE survey_attempts ADD COLUMN coverage_geometry geometry(Geometry,4326)')
    op.execute('CREATE INDEX survey_geometry_idx ON survey_attempts USING gist(coverage_geometry)')
    op.execute('''CREATE FUNCTION set_survey_geometry() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN NEW.coverage_geometry=ST_SetSRID(ST_GeomFromGeoJSON(NEW.geometry::text),4326); RETURN NEW; END; $$''')
    op.execute('CREATE TRIGGER survey_geometry BEFORE INSERT ON survey_attempts FOR EACH ROW EXECUTE FUNCTION set_survey_geometry()')


def downgrade():
    op.execute('DROP TRIGGER survey_geometry ON survey_attempts')
    op.execute('DROP FUNCTION set_survey_geometry()')
    op.execute('ALTER TABLE survey_attempts DROP COLUMN coverage_geometry')
