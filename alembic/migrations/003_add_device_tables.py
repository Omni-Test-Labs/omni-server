"""Add device master table and capability management

Revision ID: 003_add_device_tables
Revises: 002_add_task_dependencies_and_locks
Create Date: 2026-03-24 19:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "003_add_device_tables"
down_revision = "002_add_task_dependencies_and_locks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("device_type", sa.String(), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("environment_id", sa.Integer(), nullable=True),
        sa.Column("runner_version", sa.String(), nullable=False),
        sa.Column("registered_at", sa.DateTime(), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(), server_default="offline", nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["environment_id"], ["app_environments.id"], name="fk_devices_environment_id"
        ),
        sa.ForeignKeyConstraint(["group_id"], ["device_groups.id"], name="fk_devices_group_id"),
        sa.PrimaryKeyConstraint("id", name="pk_devices"),
        sa.UniqueConstraint("device_id", name="uq_devices_device_id"),
        sa.Comment("Device master table for metadata"),
    )
    op.create_index("ix_devices_device_id", "devices", ["device_id"], unique=True)
    op.create_index("ix_devices_device_type", "devices", ["device_type"])
    op.create_index("ix_devices_last_heartbeat_at", "devices", ["last_heartbeat_at"])
    op.create_index("ix_devices_status", "devices", ["status"])
    op.create_index("ix_devices_created_at", "devices", ["created_at"])

    # Create device_groups table
    op.create_table(
        "device_groups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_device_groups"),
        sa.UniqueConstraint("name", name="uq_device_groups_name"),
        sa.Comment("Device groups for logical organization"),
    )

    # Create device_capabilities table
    op.create_table(
        "device_capabilities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.String(), nullable=False),
        sa.Column("capability_name", sa.String(), nullable=False),
        sa.Column("capability_version", sa.String(), nullable=True),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.device_id"],
            name="fk_device_capabilities_device_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_device_capabilities"),
        sa.Comment("Device capability registry for precise matching"),
    )
    op.create_index("ix_device_capabilities_device_id", "device_capabilities", ["device_id"])
    op.create_index(
        "ix_device_capabilities_capability_name", "device_capabilities", ["capability_name"]
    )

    # Create device_tags table
    op.create_table(
        "device_tags",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.String(), nullable=False),
        sa.Column("tag_name", sa.String(), nullable=False),
        sa.Column("tag_value", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.device_id"],
            name="fk_device_tags_device_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_device_tags"),
        sa.Comment("Device tags for flexible categorization"),
    )
    op.create_index("ix_device_tags_device_id", "device_tags", ["device_id"])
    op.create_index("ix_device_tags_created_at", "device_tags", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_device_tags_created_at", table_name="device_tags")
    op.drop_index("ix_device_tags_device_id", table_name="device_tags")
    op.drop_table("device_tags")

    op.drop_index("ix_device_capabilities_capability_name", table_name="device_capabilities")
    op.drop_index("ix_device_capabilities_device_id", table_name="device_capabilities")
    op.drop_table("device_capabilities")

    op.drop_table("device_groups")

    op.drop_index("ix_devices_status", table_name="devices")
    op.drop_index("ix_devices_last_heartbeat_at", table_name="devices")
    op.drop_index("ix_devices_device_type", table_name="devices")
    op.drop_index("ix_devices_created_at", table_name="devices")
    op.drop_index("ix_devices_device_id", table_name="devices")
    op.drop_table("devices")
