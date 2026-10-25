"""Connected simulation prototype records and spatial storage."""
from alembic import op

revision = "0002"
down_revision = "0001"


def upgrade():
    op.execute('''CREATE TABLE missions (
	id VARCHAR(36) NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	area_id VARCHAR(80) NOT NULL, 
	operator_id VARCHAR(36) NOT NULL, 
	field_ids JSON NOT NULL, 
	boundary JSON NOT NULL, 
	waypoints JSON NOT NULL, 
	altitude_m FLOAT NOT NULL, 
	speed_m_s FLOAT NOT NULL, 
	state VARCHAR(32) NOT NULL, 
	runtime VARCHAR(32) NOT NULL, 
	synthetic_sensors BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	started_at TIMESTAMP WITH TIME ZONE, 
	finished_at TIMESTAMP WITH TIME ZONE, 
	error TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(operator_id) REFERENCES users (id)
)''')
    op.execute('''CREATE INDEX ix_missions_area_id ON missions (area_id)''')
    op.execute('''CREATE TABLE mission_events (
	id VARCHAR(36) NOT NULL, 
	mission_id VARCHAR(36) NOT NULL, 
	kind VARCHAR(40) NOT NULL, 
	detail TEXT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(mission_id) REFERENCES missions (id)
)''')
    op.execute('''CREATE INDEX ix_mission_events_mission_id ON mission_events (mission_id)''')
    op.execute('''CREATE TABLE observations (
	id VARCHAR(36) NOT NULL, 
	mission_id VARCHAR(36) NOT NULL, 
	sequence INTEGER NOT NULL, 
	longitude FLOAT NOT NULL, 
	latitude FLOAT NOT NULL, 
	altitude_m FLOAT NOT NULL, 
	speed_m_s FLOAT NOT NULL, 
	battery_percent FLOAT, 
	source VARCHAR(40) NOT NULL, 
	sensor JSON, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(mission_id) REFERENCES missions (id)
)''')
    op.execute('''CREATE INDEX ix_observations_mission_id ON observations (mission_id)''')
    op.execute('''CREATE TABLE detections (
	id VARCHAR(36) NOT NULL, 
	mission_id VARCHAR(36) NOT NULL, 
	observation_id VARCHAR(36) NOT NULL, 
	longitude FLOAT NOT NULL, 
	latitude FLOAT NOT NULL, 
	confidence FLOAT NOT NULL, 
	classification VARCHAR(40) NOT NULL, 
	processing_version VARCHAR(80) NOT NULL, 
	simulated BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(mission_id) REFERENCES missions (id), 
	FOREIGN KEY(observation_id) REFERENCES observations (id)
)''')
    op.execute('''CREATE INDEX ix_detections_mission_id ON detections (mission_id)''')
    op.execute('''CREATE TABLE analyst_reviews (
	id VARCHAR(36) NOT NULL, 
	detection_id VARCHAR(36) NOT NULL, 
	analyst_id VARCHAR(36) NOT NULL, 
	assessment VARCHAR(40) NOT NULL, 
	notes TEXT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(detection_id) REFERENCES detections (id), 
	FOREIGN KEY(analyst_id) REFERENCES users (id)
)''')
    op.execute('''CREATE INDEX ix_analyst_reviews_detection_id ON analyst_reviews (detection_id)''')
    op.execute('''CREATE TABLE survey_attempts (
	id VARCHAR(36) NOT NULL, 
	mission_id VARCHAR(36) NOT NULL, 
	area_id VARCHAR(80) NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	coverage_percent FLOAT NOT NULL, 
	geometry JSON NOT NULL, 
	algorithm_version VARCHAR(80) NOT NULL, 
	simulated BOOLEAN NOT NULL, 
	started_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	finished_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (mission_id), 
	FOREIGN KEY(mission_id) REFERENCES missions (id)
)''')
    op.execute('''CREATE INDEX ix_survey_attempts_area_id ON survey_attempts (area_id)''')
    op.execute('''CREATE TABLE vehicle_leases (
	id VARCHAR(40) NOT NULL, 
	mission_id VARCHAR(36), 
	PRIMARY KEY (id)
)''')
    op.execute("INSERT INTO vehicle_leases(id) VALUES ('sitl-01')")
    op.execute("ALTER TABLE missions ADD COLUMN planned_geometry geometry(Polygon,4326)")
    op.execute("CREATE INDEX missions_geometry_idx ON missions USING gist(planned_geometry)")
    op.execute("ALTER TABLE observations ADD COLUMN position geometry(Point,4326)")
    op.execute("ALTER TABLE observations ADD COLUMN footprint geometry(Geometry,4326)")
    op.execute("CREATE INDEX observations_footprint_idx ON observations USING gist(footprint)")
    op.execute("CREATE UNIQUE INDEX observation_sequence_idx ON observations(mission_id,sequence)")
    op.execute("CREATE TRIGGER survey_append_only BEFORE UPDATE OR DELETE ON survey_attempts FOR EACH ROW EXECUTE FUNCTION reject_audit_mutation()")
    op.execute("CREATE TRIGGER reviews_append_only BEFORE UPDATE OR DELETE ON analyst_reviews FOR EACH ROW EXECUTE FUNCTION reject_audit_mutation()")


def downgrade():
    op.drop_table("vehicle_leases")
    op.drop_table("survey_attempts")
    op.drop_table("analyst_reviews")
    op.drop_table("detections")
    op.drop_table("observations")
    op.drop_table("mission_events")
    op.drop_table("missions")
