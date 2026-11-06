"""Field Personnel message provenance on mission events."""

from alembic import op
import sqlalchemy as sa

revision = '0007'
down_revision = '0006'


def upgrade():
    op.add_column('mission_events', sa.Column('actor_id', sa.String(36), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('mission_events', sa.Column('actor_username', sa.String(80), nullable=True))
    op.add_column('mission_events', sa.Column('priority', sa.String(16), nullable=True))


def downgrade():
    for name in ('priority', 'actor_username', 'actor_id'):
        op.drop_column('mission_events', name)
