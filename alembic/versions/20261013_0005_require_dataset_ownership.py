"""require dataset ownership

Revision ID: 20261013_0005
Revises: 20261008_0004
Create Date: 2026-10-13

"""

from typing import (
    Sequence,
    Union,
)

from alembic import op
import sqlalchemy as sa


revision: str = "20261013_0005"

down_revision: Union[
    str,
    None,
] = "20261008_0004"

branch_labels: Union[
    str,
    Sequence[str],
    None,
] = None

depends_on: Union[
    str,
    Sequence[str],
    None,
] = None


def upgrade() -> None:
    connection = op.get_bind()

    null_count = connection.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM datasets
            WHERE user_id IS NULL
            """
        )
    ).scalar_one()

    if null_count:
        raise RuntimeError(
            "Cannot require dataset ownership: "
            f"{null_count} dataset(s) still "
            "have NULL user_id."
        )

    with op.batch_alter_table(
        "datasets"
    ) as batch_op:
        batch_op.alter_column(
            "user_id",
            existing_type=sa.Uuid(),
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table(
        "datasets"
    ) as batch_op:
        batch_op.alter_column(
            "user_id",
            existing_type=sa.Uuid(),
            nullable=True,
        )
