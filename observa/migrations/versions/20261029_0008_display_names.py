"""Allow person names as user display names.

Revision ID: 20261029_0008
Revises: 20261029_0007
Create Date: 2026-10-29
"""

from alembic import op
import sqlalchemy as sa


revision = "20261029_0008"
down_revision = "20261029_0007"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(
            "users",
            recreate="always",
            naming_convention={"uq": "uq_%(table_name)s_%(column_0_name)s"},
        ) as batch_op:
            batch_op.drop_constraint("uq_users_username", type_="unique")
            batch_op.alter_column(
                "username",
                existing_type=sa.String(length=64),
                type_=sa.String(length=128),
            )
        return

    username_constraint = next(
        constraint
        for constraint in sa.inspect(bind).get_unique_constraints("users")
        if constraint["column_names"] == ["username"]
    )
    op.drop_constraint(username_constraint["name"], "users", type_="unique")
    op.alter_column(
        "users",
        "username",
        existing_type=sa.String(length=64),
        type_=sa.String(length=128),
    )


def downgrade():
    with op.batch_alter_table(
        "users",
        recreate="always" if op.get_bind().dialect.name == "sqlite" else "auto",
        naming_convention={"uq": "uq_%(table_name)s_%(column_0_name)s"},
    ) as batch_op:
        batch_op.alter_column(
            "username",
            existing_type=sa.String(length=128),
            type_=sa.String(length=64),
        )
        batch_op.create_unique_constraint("uq_users_username", ["username"])
