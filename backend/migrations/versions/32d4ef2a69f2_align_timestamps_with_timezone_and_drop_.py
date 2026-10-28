"""align timestamps with timezone and drop unused status index

Revision ID: 32d4ef2a69f2
Revises: 2217ccac7fb7
Create Date: 2026-10-27 21:39:22.863006

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '32d4ef2a69f2'
down_revision: Union[str, Sequence[str], None] = '2217ccac7fb7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (tabela, coluna) que o modelo declara com timezone=True mas as migrations antigas criaram sem fuso.
NAIVE_COLUMNS = [
    ("users", "created_at"),
    ("users", "updated_at"),
    ("token_blacklist", "expires_at"),
]


def upgrade() -> None:
    """Upgrade schema.

    Os valores existentes foram gravados pela aplicação em UTC; `AT TIME ZONE 'UTC'`
    os interpreta assim. Se algum ambiente rodou com o fuso do servidor diferente de UTC,
    os valores antigos ficam deslocados pela diferença (afeta só datas já gravadas).
    """
    for table, column in NAIVE_COLUMNS:
        op.alter_column(
            table,
            column,
            existing_type=sa.TIMESTAMP(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
        )
    # Nenhuma consulta filtra por status; o índice só custava escrita.
    op.drop_index(op.f("ix_development_trails_status"), table_name="development_trails")


def downgrade() -> None:
    """Downgrade schema."""
    op.create_index(op.f("ix_development_trails_status"), "development_trails", ["status"], unique=False)
    for table, column in NAIVE_COLUMNS:
        op.alter_column(
            table,
            column,
            existing_type=sa.DateTime(timezone=True),
            type_=sa.TIMESTAMP(),
            existing_nullable=False,
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
        )
