"""Seed default roles and permissions for omni-server."""

from datetime import datetime

from sqlalchemy.orm import Session

from omni_server.models import PermissionDB, RoleDB

# Define default roles and their permissions
DEFAULT_ROLES = {
    "admin": {
        "description": "Administrator with full system access",
        "permissions": [
            {
                "name": "all",
                "description": "Full access to all resources",
                "resource_type": "all",
                "action": "all",
            }
        ],
    },
    "user": {
        "description": "Standard user with limited access",
        "permissions": [
            {
                "name": "read_devices",
                "description": "Read device information",
                "resource_type": "device",
                "action": "read",
            },
            {
                "name": "read_tasks",
                "description": "Read task information",
                "resource_type": "task",
                "action": "read",
            },
            {
                "name": "create_tasks",
                "description": "Create new tasks",
                "resource_type": "task",
                "action": "create",
            },
            {
                "name": "read_applications",
                "description": "Read test application information",
                "resource_type": "application",
                "action": "read",
            },
            {
                "name": "read_settings",
                "description": "Read user settings",
                "resource_type": "setting",
                "action": "read",
            },
            {
                "name": "update_settings",
                "description": "Update own settings",
                "resource_type": "setting",
                "action": "update",
            },
        ],
    },
}


def seed_roles(db: Session) -> None:
    """Seed default roles and permissions."""
    for role_name, role_data in DEFAULT_ROLES.items():
        # Check if role exists
        existing_role = db.query(RoleDB).filter(RoleDB.name == role_name).first()

        if not existing_role:
            # Create permissions
            permissions = []
            for perm_data in role_data["permissions"]:
                existing_perm = (
                    db.query(PermissionDB).filter(PermissionDB.name == perm_data["name"]).first()
                )

                if not existing_perm:
                    perm = PermissionDB(
                        name=perm_data["name"],
                        description=perm_data["description"],
                        resource_type=perm_data["resource_type"],
                        action=perm_data["action"],
                        created_at=datetime.utcnow(),
                    )
                    db.add(perm)
                    db.flush()
                    permissions.append(perm)
                else:
                    permissions.append(existing_perm)

            # Create role with permissions
            role = RoleDB(
                name=role_name,
                description=role_data["description"],
                permissions=[p.name for p in permissions],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(role)
            db.commit()
            print(f"Created role: {role_name}")
        else:
            print(f"Role already exists: {role_name}")


def seed_system_settings(db: Session) -> None:
    """Seed default system settings."""
    from omni_server.models import SystemSettingDB

    DEFAULT_SETTINGS = {
        "global.site_name": "Omni Test Labs",
        "global.site_url": "http://localhost:3000",
        "auth.allow_registration": "true",
        "auth.oauth.enabled": "true",
        "notification.email_enabled": "false",
        "notification.email_from": "noreply@omnitestlabs.com",
        "api.rate_limit_enabled": "true",
        "api.rate_limit_per_minute": "100",
    }

    for key, value in DEFAULT_SETTINGS.items():
        category = key.split(".")[0]
        existing = db.query(SystemSettingDB).filter(SystemSettingDB.key == key).first()

        if not existing:
            setting = SystemSettingDB(
                key=key,
                value=value,
                category=category,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(setting)
            db.commit()
            print(f"Created system setting: {key}")
        else:
            print(f"System setting already exists: {key}")


def main():
    """Run all seed operations."""
    from omni_server.database import engine, SessionLocal

    # Create all tables if they don't exist
    from omni_server.models import Base

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        print("Seeding roles and permissions...")
        seed_roles(db)

        print("\nSeeding system settings...")
        seed_system_settings(db)

        print("\nSeed operations complete!")
    finally:
        db.close()


if __name__ == "__main__":
    main()
