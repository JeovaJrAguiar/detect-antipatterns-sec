"""Add append-only security audit log.

Revision ID: 20260928_0005
Revises: 20260928_0004
Create Date: 2026-09-28
"""

from alembic import op
import sqlalchemy as sa


revision = "20260928_0005"
down_revision = "20260928_0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "security_audit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=True),
        sa.Column("resource_id", sa.String(length=255), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("client_ip", sa.String(length=45), nullable=True),
        sa.Column("request_id", sa.String(length=36), nullable=True),
        sa.CheckConstraint(
            "outcome IN ('success', 'failure')",
            name="ck_security_audit_log_outcome",
        ),
    )
    op.create_index(
        "ix_security_audit_log_occurred_at",
        "security_audit_log",
        ["occurred_at"],
    )
    op.create_index(
        "ix_security_audit_log_actor_user_id",
        "security_audit_log",
        ["actor_user_id"],
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION reject_security_audit_mutation() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'security audit log is append-only';
            END;
            $$
            """
        )
        op.execute(
            """
            CREATE TRIGGER security_audit_log_reject_update_delete
            BEFORE UPDATE OR DELETE ON security_audit_log
            FOR EACH ROW EXECUTE FUNCTION reject_security_audit_mutation()
            """
        )
        op.execute(
            """
            CREATE TRIGGER security_audit_log_reject_truncate
            BEFORE TRUNCATE ON security_audit_log
            FOR EACH STATEMENT EXECUTE FUNCTION reject_security_audit_mutation()
            """
        )
        op.execute(
            "REVOKE UPDATE, DELETE, TRUNCATE ON TABLE security_audit_log FROM PUBLIC"
        )
    elif op.get_bind().dialect.name == "sqlite":
        op.execute(
            """
            CREATE TRIGGER security_audit_log_reject_update
            BEFORE UPDATE ON security_audit_log
            BEGIN
                SELECT RAISE(ABORT, 'security audit log is append-only');
            END
            """
        )
        op.execute(
            """
            CREATE TRIGGER security_audit_log_reject_delete
            BEFORE DELETE ON security_audit_log
            BEGIN
                SELECT RAISE(ABORT, 'security audit log is append-only');
            END
            """
        )


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS security_audit_log_reject_truncate ON security_audit_log"
        )
        op.execute(
            "DROP TRIGGER IF EXISTS security_audit_log_reject_update_delete ON security_audit_log"
        )
        op.execute("DROP FUNCTION IF EXISTS reject_security_audit_mutation()")
    elif op.get_bind().dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS security_audit_log_reject_update")
        op.execute("DROP TRIGGER IF EXISTS security_audit_log_reject_delete")

    op.drop_index("ix_security_audit_log_actor_user_id", table_name="security_audit_log")
    op.drop_index("ix_security_audit_log_occurred_at", table_name="security_audit_log")
    op.drop_table("security_audit_log")