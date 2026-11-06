"""Third isolated channel and camera-free downward-LiDAR x500 variant."""
from alembic import op
revision='0008'
down_revision='0007'
def upgrade():
    op.drop_constraint('isolated_runtime_slot','uavs',type_='check')
    op.execute("ALTER TABLE uavs ADD CONSTRAINT isolated_runtime_slot CHECK(runtime_slot IS NULL OR runtime_slot IN ('sitl-01','sitl-02','sitl-03'))")
    op.execute("INSERT INTO uav_types VALUES ('px4-x500-lidar-down','PX4 x500 downward LiDAR','quadrotor','px4-x500-lidar-down','{}') ON CONFLICT (id) DO NOTHING")
    op.execute("INSERT INTO uavs VALUES ('sitl-03','Simulation UAV 3 / downward LiDAR','px4-x500-lidar-down',true,'sitl-03',now()) ON CONFLICT (id) DO NOTHING")
    op.execute("INSERT INTO vehicle_leases(id) VALUES ('sitl-03') ON CONFLICT (id) DO NOTHING")
def downgrade():
    # Preserve registered vehicles and immutable attempts on rollback.
    op.drop_constraint('isolated_runtime_slot','uavs',type_='check')
    op.execute("ALTER TABLE uavs ADD CONSTRAINT isolated_runtime_slot CHECK(runtime_slot IS NULL OR runtime_slot IN ('sitl-01','sitl-02')) NOT VALID")
