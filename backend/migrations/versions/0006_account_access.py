"""Per-account restrictions within role permissions."""
from alembic import op
import sqlalchemy as sa
revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('denied_permissions', sa.JSON(), nullable=False, server_default='[]'))


def downgrade():
    op.drop_column('users', 'denied_permissions')
