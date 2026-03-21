"""Add task dependencies and device locks tables

Revision ID: 002_add_task_dependencies_and_locks
Revises: 001_add_auth_models
Create Date: 2026-03-21 02:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "002_add_task_dependencies_and_locks"
down_revision = "001_add_auth_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create task_dependencies and device_locks tables."""

    # Create task_dependencies table
    op.create_table(
        "task_dependencies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id_one", sa.Integer(), nullable=False),
        sa.Column("task_id_two", sa.Integer(), nullable=False),
        sa.Column("dependency_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["task_id_one"], ["task_queue.id"], name="fk_task_dependencies_task_id_one"
        ),
        sa.ForeignKeyConstraint(
            ["task_id_two"], ["task_queue.id"], name="fk_task_dependencies_task_id_two"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_task_dependencies"),
    )
    op.create_index("ix_task_dependencies_task_id_one", "task_dependencies", ["task_id_one"])
    op.create_index("ix_task_dependencies_task_id_two", "task_dependencies", ["task_id_two"])
    op.create_index("ix_task_dependencies_created_at", "task_dependencies", ["created_at"])

    # Create device_locks table
    op.create_table(
        "device_locks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.String(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), server_default="locked", nullable=False),
        sa.Column("lock_timeout_seconds", sa.Integer(), server_default="300", nullable=False),
        sa.Column("acquired_at", sa.DateTime(), nullable=True),
        sa.Column("released_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["task_queue.id"], name="fk_device_locks_task_id"),
        sa.PrimaryKeyConstraint("id", name="pk_device_locks"),
    )
    op.create_index("ix_device_locks_device_id", "device_locks", ["device_id"])
    op.create_index("ix_device_locks_task_id", "device_locks", ["task_id"])
    op.create_index("ix_device_locks_created_at", "device_locks", ["created_at"])


def downgrade() -> None:
    """Drop task_dependencies and device_locks tables."""
    op.drop_index("ix_device_locks_created_at", table_name="device_locks")
    op.drop_index("ix_device_locks_task_id", table_name="device_locks")
    op.drop_index("ix_device_locks_device_id", table_name="device_locks")
    op.drop_table("device_locks")

    op.drop_index("ix_task_dependencies_created_at", table_name="task_dependencies")
    op.drop_index("ix_task_dependencies_task_id_two", table_name="task_dependencies")
    op.drop_index("ix_task_dependencies_task_id_one", table_name="task_dependencies")
    op.drop_table("task_dependencies")
