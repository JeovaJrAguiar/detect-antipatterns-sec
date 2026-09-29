"""Create the initial Observa database schema.

Revision ID: 20260928_0001
Revises:
Create Date: 2026-09-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260928_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("json_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("api_url", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_sources_id", "sources", ["id"], unique=False)

    op.create_table(
        "detectors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name_ap", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("class_path", sa.String(), nullable=True),
        sa.Column("api_url", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_detectors_id", "detectors", ["id"], unique=False)

    op.create_table(
        "history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("detector_id", sa.Integer(), nullable=False),
        sa.Column("detected", sa.Integer(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("execution_time", sa.Double(), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["detector_id"], ["detectors.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_history_id", "history", ["id"], unique=False)


def downgrade():
    op.drop_index("ix_history_id", table_name="history")
    op.drop_table("history")
    op.drop_index("ix_detectors_id", table_name="detectors")
    op.drop_table("detectors")
    op.drop_index("ix_sources_id", table_name="sources")
    op.drop_table("sources")