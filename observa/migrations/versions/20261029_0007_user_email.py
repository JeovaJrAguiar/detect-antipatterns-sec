"""Add email addresses to user accounts.

Revision ID: 20261029_0007
Revises: 20261014_0006
Create Date: 2026-10-29
"""

from alembic import op
import sqlalchemy as sa


revision = "20261029_0007"
down_revision = "20261014_0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("email", sa.String(length=254), nullable=True))
    op.execute(
        """
        UPDATE users
        SET email = CASE lower(username)
            WHEN 'admin' THEN 'admin@observa.com'
            WHEN 'operador' THEN 'operador@observa.com'
            WHEN 'executor' THEN 'executor@observa.com'
            ELSE 'user-' || id || '@legacy.invalid'
        END
        WHERE email IS NULL
        """
    )
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("email", existing_type=sa.String(length=254), nullable=False)
        batch_op.create_unique_constraint("uq_users_email", ["email"])


def downgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("uq_users_email", type_="unique")
    op.drop_column("users", "email")
