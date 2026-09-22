"""create identification jobs

Revision ID: 20260922_0001
Revises:
Create Date: 2026-09-22
"""

from alembic import op
import sqlalchemy as sa


revision = "20260922_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "identification_jobs",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("reason_code", sa.String(length=80), nullable=True),
        sa.Column("reference_version", sa.String(length=80), nullable=False),
        sa.Column("application_version", sa.String(length=40), nullable=True),
        sa.Column("algorithm_version", sa.String(length=80), nullable=True),
        sa.Column("rq_job_id", sa.String(length=100), nullable=True),
        sa.Column("job_dir", sa.Text(), nullable=False),
        sa.Column("upload_dir", sa.Text(), nullable=False),
        sa.Column("input_files", sa.JSON(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rq_job_id"),
    )
    op.create_index(
        op.f("ix_identification_jobs_status"),
        "identification_jobs",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_identification_jobs_status"),
        table_name="identification_jobs",
    )
    op.drop_table("identification_jobs")

