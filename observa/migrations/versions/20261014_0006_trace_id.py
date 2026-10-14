from alembic import op
import sqlalchemy as sa


revision = "20261014_0006"
down_revision = "20260928_0005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "security_audit_log",
        sa.Column("trace_id", sa.String(length=36), nullable=True),
    )
    op.execute(
        "UPDATE security_audit_log SET trace_id = request_id WHERE trace_id IS NULL"
    )
    op.create_index(
        "ix_security_audit_log_trace_id",
        "security_audit_log",
        ["trace_id"],
    )


def downgrade():
    op.drop_index("ix_security_audit_log_trace_id", table_name="security_audit_log")
    op.drop_column("security_audit_log", "trace_id")
