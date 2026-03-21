"""Add authentication models

Revision ID: 001
Revises:
Create Date: 2026-03-20 01:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create roles table
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_roles_id"), "roles", ["id"], unique=False)
    op.create_index(op.f("ix_roles_name"), "roles", ["name"], unique=True)

    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("github_id", sa.String(), nullable=True),
        sa.Column("gitlab_id", sa.String(), nullable=True),
        sa.Column("avatar_url", sa.String(), nullable=True),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
    op.create_index(op.f("ix_users_is_active"), "users", ["is_active"], unique=False)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_created_at"), "users", ["created_at"], unique=False)
    op.create_index(op.f("ix_users_github_id"), "users", ["github_id"], unique=True)
    op.create_index(op.f("ix_users_gitlab_id"), "users", ["gitlab_id"], unique=True)

    # Create permissions table
    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("resource_type", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_permissions_id"), "permissions", ["id"], unique=False)
    op.create_index(op.f("ix_permissions_name"), "permissions", ["name"], unique=True)
    op.create_index(
        op.f("ix_permissions_resource_type"), "permissions", ["resource_type"], unique=False
    )

    # Create user_settings table
    op.create_table(
        "user_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("preferences", sa.JSON(), nullable=False),
        sa.Column("theme", sa.String(), nullable=True),
        sa.Column("language", sa.String(), nullable=True),
        sa.Column("notification_email", sa.Boolean(), nullable=True),
        sa.Column("notification_web", sa.Boolean(), nullable=True),
        sa.Column("timezone", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_settings_id"), "user_settings", ["id"], unique=False)
    op.create_index(op.f("ix_user_settings_user_id"), "user_settings", ["user_id"], unique=False)

    # Create notifications table
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("read", sa.Boolean(), nullable=True),
        sa.Column("link_url", sa.String(), nullable=True),
        sa.Column("meta_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_notifications_id"), "notifications", ["id"], unique=False)
    op.create_index(op.f("ix_notifications_user_id"), "notifications", ["user_id"], unique=False)
    op.create_index(op.f("ix_notifications_type"), "notifications", ["type"], unique=False)
    op.create_index(op.f("ix_notifications_read"), "notifications", ["read"], unique=False)
    op.create_index(
        op.f("ix_notifications_created_at"), "notifications", ["created_at"], unique=False
    )

    # Create audit_logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_logs_id"), "audit_logs", ["id"], unique=False)
    op.create_index(op.f("ix_audit_logs_user_id"), "audit_logs", ["user_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_entity_type"), "audit_logs", ["entity_type"], unique=False)
    op.create_index(op.f("ix_audit_logs_entity_id"), "audit_logs", ["entity_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_created_at"), "audit_logs", ["created_at"], unique=False)

    # Create test_applications table
    op.create_table(
        "test_applications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_test_applications_id"), "test_applications", ["id"], unique=False)
    op.create_index(op.f("ix_test_applications_type"), "test_applications", ["type"], unique=False)
    op.create_index(
        op.f("ix_test_applications_created_by"), "test_applications", ["created_by"], unique=False
    )
    op.create_index(
        op.f("ix_test_applications_created_at"), "test_applications", ["created_at"], unique=False
    )

    # Create app_environments table
    op.create_table(
        "app_environments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("app_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["app_id"], ["test_applications.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_app_environments_id"), "app_environments", ["id"], unique=False)
    op.create_index(
        op.f("ix_app_environments_app_id"), "app_environments", ["app_id"], unique=False
    )
    op.create_index(op.f("ix_app_environments_type"), "app_environments", ["type"], unique=False)

    # Create system_settings table
    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_system_settings_id"), "system_settings", ["id"], unique=False)
    op.create_index(op.f("ix_system_settings_key"), "system_settings", ["key"], unique=True)
    op.create_index(
        op.f("ix_system_settings_category"), "system_settings", ["category"], unique=False
    )

    # Create service_health table
    op.create_table(
        "service_health",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("service_name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("last_check", sa.DateTime(), nullable=True),
        sa.Column("uptime_seconds", sa.Float(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_service_health_id"), "service_health", ["id"], unique=False)
    op.create_index(
        op.f("ix_service_health_service_name"), "service_health", ["service_name"], unique=True
    )
    op.create_index(op.f("ix_service_health_status"), "service_health", ["status"], unique=False)
    op.create_index(
        op.f("ix_service_health_last_check"), "service_health", ["last_check"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_service_health_last_check"), table_name="service_health")
    op.drop_index(op.f("ix_service_health_status"), table_name="service_health")
    op.drop_index(op.f("ix_service_health_service_name"), table_name="service_health")
    op.drop_index(op.f("ix_service_health_id"), table_name="service_health")
    op.drop_table("service_health")

    op.drop_index(op.f("ix_system_settings_category"), table_name="system_settings")
    op.drop_index(op.f("ix_system_settings_key"), table_name="system_settings")
    op.drop_index(op.f("ix_system_settings_id"), table_name="system_settings")
    op.drop_table("system_settings")

    op.drop_index(op.f("ix_app_environments_type"), table_name="app_environments")
    op.drop_index(op.f("ix_app_environments_app_id"), table_name="app_environments")
    op.drop_index(op.f("ix_app_environments_id"), table_name="app_environments")
    op.drop_table("app_environments")

    op.drop_index(op.f("ix_test_applications_created_at"), table_name="test_applications")
    op.drop_index(op.f("ix_test_applications_created_by"), table_name="test_applications")
    op.drop_index(op.f("ix_test_applications_type"), table_name="test_applications")
    op.drop_index(op.f("ix_test_applications_id"), table_name="test_applications")
    op.drop_table("test_applications")

    op.drop_index(op.f("ix_audit_logs_created_at"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_entity_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_entity_type"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_user_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_id"), table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index(op.f("ix_notifications_created_at"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_read"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_type"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_user_id"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_id"), table_name="notifications")
    op.drop_table("notifications")

    op.drop_index(op.f("ix_user_settings_user_id"), table_name="user_settings")
    op.drop_index(op.f("ix_user_settings_id"), table_name="user_settings")
    op.drop_table("user_settings")

    op.drop_index(op.f("ix_permissions_resource_type"), table_name="permissions")
    op.drop_index(op.f("ix_permissions_name"), table_name="permissions")
    op.drop_index(op.f("ix_permissions_id"), table_name="permissions")
    op.drop_table("permissions")

    op.drop_index(op.f("ix_users_gitlab_id"), table_name="users")
    op.drop_index(op.f("ix_users_github_id"), table_name="users")
    op.drop_index(op.f("ix_users_created_at"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_index(op.f("ix_users_is_active"), table_name="users")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_table("users")

    op.drop_index(op.f("ix_roles_name"), table_name="roles")
    op.drop_index(op.f("ix_roles_id"), table_name="roles")
    op.drop_table("roles")
