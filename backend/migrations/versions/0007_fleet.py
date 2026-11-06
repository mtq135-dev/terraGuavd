"""Fleet registry; preserve legacy identifiers and immutable survey snapshots."""
from alembic import op
import sqlalchemy as sa
revision='0007'
down_revision='0006'

def upgrade():
    op.create_table('uav_types',sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('name',sa.String(80),nullable=False,unique=True),sa.Column('category',sa.String(40),nullable=False),
        sa.Column('simulation_profile',sa.String(40),nullable=False),sa.Column('specifications',sa.JSON,nullable=False))
    op.create_table('uavs',sa.Column('id',sa.String(40),primary_key=True),sa.Column('name',sa.String(100),nullable=False),
        sa.Column('type_id',sa.String(36),sa.ForeignKey('uav_types.id'),nullable=False),sa.Column('active',sa.Boolean,nullable=False),
        sa.Column('runtime_slot',sa.String(16),unique=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.CheckConstraint("runtime_slot IS NULL OR runtime_slot IN ('sitl-01','sitl-02')",name='isolated_runtime_slot'))
    op.execute("INSERT INTO uav_types VALUES ('px4-x500','PX4 x500','quadrotor','px4-x500','{}'),('legacy','Legacy vehicle','unspecified','catalog-only','{}')")
    op.execute("INSERT INTO uavs VALUES ('sitl-01','Simulation UAV 1','px4-x500',true,'sitl-01',now()),('sitl-02','Simulation UAV 2','px4-x500',true,'sitl-02',now())")
    op.execute("""INSERT INTO uavs SELECT id,id,'legacy',false,NULL,now() FROM (
        SELECT uav_id id FROM missions UNION SELECT uav_id FROM survey_attempts UNION SELECT id FROM vehicle_leases
        ) legacy WHERE NOT EXISTS(SELECT 1 FROM uavs WHERE uavs.id=legacy.id)""")
    op.execute("INSERT INTO vehicle_leases(id) VALUES ('sitl-02') ON CONFLICT DO NOTHING")
    op.create_foreign_key('mission_uav_fk','missions','uavs',['uav_id'],['id'])
    op.create_foreign_key('attempt_uav_fk','survey_attempts','uavs',['uav_id'],['id'])
    op.create_foreign_key('lease_uav_fk','vehicle_leases','uavs',['id'],['id'])

def downgrade():
    for table,name in [('missions','mission_uav_fk'),('survey_attempts','attempt_uav_fk'),('vehicle_leases','lease_uav_fk')]:op.drop_constraint(name,table,type_='foreignkey')
    # Preserve lease identifiers/mission records on rollback; no history deletion.
    op.drop_table('uavs');op.drop_table('uav_types')
