"""index token_blacklist.expires_at

Revision ID: c3f81a5d7e29
Revises: a41c7d9e5b02
Create Date: 2026-10-29 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c3f81a5d7e29'
down_revision: Union[str, Sequence[str], None] = 'a41c7d9e5b02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema. A limpeza de revogações vencidas filtra por `expires_at`."""
    op.create_index(op.f('ix_token_blacklist_expires_at'), 'token_blacklist', ['expires_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_token_blacklist_expires_at'), table_name='token_blacklist')
