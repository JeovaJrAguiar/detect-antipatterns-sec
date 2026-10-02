"""Remove the forced first-login password change flag.

Revision ID: 20260928_0004
Revises: 20260928_0003
Create Date: 2026-09-28
"""

from alembic import op
import sqlalchemy as sa

revision = "20260928_0004"
down_revision = "20260928_0003"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("users", "must_change_password")


def downgrade():
    op.add_column(
        "users",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )