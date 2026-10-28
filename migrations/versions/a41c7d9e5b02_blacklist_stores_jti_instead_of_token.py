"""token_blacklist stores the jti instead of the whole token

Revision ID: a41c7d9e5b02
Revises: 32d4ef2a69f2
Create Date: 2026-10-28 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a41c7d9e5b02'
down_revision: Union[str, Sequence[str], None] = '32d4ef2a69f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    As linhas existentes são descartadas: elas guardam o JWT inteiro, de onde o `jti`
    só sai decodificando cada token, e os tokens expiram em no máximo REFRESH_TOKEN_EXPIRE_DAYS.
    Efeito: tokens revogados (logout) antes desta migration voltam a valer até expirarem.
    """
    op.execute("DELETE FROM token_blacklist")
    op.drop_index(op.f('ix_token_blacklist_token'), table_name='token_blacklist')
    op.drop_column('token_blacklist', 'token')
    op.add_column('token_blacklist', sa.Column('jti', sa.String(length=32), nullable=False))
    op.create_index(op.f('ix_token_blacklist_jti'), 'token_blacklist', ['jti'], unique=True)
    op.alter_column(
        'token_blacklist',
        'created_at',
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema. As revogações guardadas se perdem: o jti não reconstrói o token."""
    op.execute("DELETE FROM token_blacklist")
    op.alter_column(
        'token_blacklist',
        'created_at',
        existing_type=sa.DateTime(timezone=True),
        server_default=None,
        nullable=True,
    )
    op.drop_index(op.f('ix_token_blacklist_jti'), table_name='token_blacklist')
    op.drop_column('token_blacklist', 'jti')
    op.add_column('token_blacklist', sa.Column('token', sa.String(), nullable=True))
    op.create_index(op.f('ix_token_blacklist_token'), 'token_blacklist', ['token'], unique=True)
