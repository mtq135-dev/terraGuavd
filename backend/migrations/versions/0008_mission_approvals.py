"""Configuration-bound Supervisor exceptions for outside-area simulated missions."""

from alembic import op
import sqlalchemy as sa

revision = '0008'
down_revision = '0007'


def upgrade():
    op.add_column('missions', sa.Column('plan_revision', sa.Integer(), nullable=False, server_default='1'))
    op.create_table('mission_approval_requests',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('mission_id', sa.String(36), sa.ForeignKey('missions.id'), nullable=False),
        sa.Column('assignment_id', sa.String(36), sa.ForeignKey('survey_area_assignments.id'), nullable=False),
        sa.Column('operator_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('supervisor_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('assignment_revision', sa.Integer(), nullable=False),
        sa.Column('configuration_hash', sa.String(64), nullable=False),
        sa.Column('snapshot', sa.JSON(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('requested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('decision_reason', sa.Text()),
        sa.Column('decided_by', sa.String(36), sa.ForeignKey('users.id')),
        sa.Column('decided_at', sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('Pending','Approved','Rejected','Invalidated')", name='valid_mission_approval_status'))
    for name in ('mission_id', 'operator_id', 'supervisor_id'):
        op.create_index(f'mission_approval_{name}_idx', 'mission_approval_requests', [name])


def downgrade():
    op.drop_table('mission_approval_requests')
    op.drop_column('missions', 'plan_revision')
