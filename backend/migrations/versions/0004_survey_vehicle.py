"""Preserve vehicle identity and indexed target geometry."""
from alembic import op
import sqlalchemy as sa

revision='0004'
down_revision='0003'


def upgrade():
    for table in ['missions','survey_attempts']:
        op.add_column(table,sa.Column('uav_id',sa.String(40),nullable=False,server_default='sitl-01'))
    op.execute('ALTER TABLE detections ADD COLUMN position geometry(Point,4326) GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(longitude,latitude),4326)) STORED')
    op.execute('CREATE INDEX detections_position_idx ON detections USING gist(position)')


def downgrade():
    op.execute('ALTER TABLE detections DROP COLUMN position')
    for table in ['survey_attempts','missions']:
        op.drop_column(table,'uav_id')
