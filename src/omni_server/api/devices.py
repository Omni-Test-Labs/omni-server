"""API endpoints for device management and heartbeat."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from omni_server.config import Settings
from omni_server.database import get_db
from omni_server.events import get_event_bus, DeviceEvent
from omni_server.models import (
    DeviceDB,
    DeviceHeartbeatDB,
    DeviceCapabilityDB,
    DeviceTagDB,
    Heartbeat,
    DeviceCreate,
    DeviceUpdate,
    DeviceResponse,
)
from omni_server.cleanup.heartbeat import HeartbeatCleanupService

router = APIRouter(prefix="/devices", tags=["devices"])

event_bus = get_event_bus()


async def publish_device_event(event_type: str, device_id: str, **kwargs):
    event = DeviceEvent(event_type=event_type, device_id=device_id, **kwargs)
    await event_bus.publish(f"device:{device_id}", event.model_dump())


@router.post("/")
async def create_device(
    device: DeviceCreate,
    db: Session = Depends(get_db),
) -> dict:
    existing = db.query(DeviceDB).filter(DeviceDB.device_id == device.device_id).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Device with device_id '{device.device_id}' already exists",
        )

    device_db = DeviceDB(
        device_id=device.device_id,
        name=device.name,
        device_type=device.device_type,
        capabilities=device.capabilities,
        config=device.config,
        environment_id=device.environment_id,
        runner_version=device.runner_version,
        group_id=device.group_id,
        registered_at=datetime.utcnow(),
        last_heartbeat_at=datetime.utcnow(),
        status="offline",
    )

    db.add(device_db)
    db.flush()

    for tag in device.tags:
        tag_db = DeviceTagDB(
            device_id=device.device_id,
            tag_name=tag.tag_name,
            tag_value=tag.tag_value,
        )
        db.add(tag_db)

    db.commit()

    await publish_device_event(
        "device.registered",
        device.device_id,
        status="offline",
        runner_version=device.runner_version,
        capabilities=device.capabilities,
    )

    return {
        "device_id": device.device_id,
        "status": "created",
        "message": f"Device '{device.name}' registered successfully",
    }


@router.get("/{device_id}")
async def get_device(
    device_id: str,
    db: Session = Depends(get_db),
) -> dict:
    device = db.query(DeviceDB).filter(DeviceDB.device_id == device_id).first()

    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    capabilities_list = [
        {
            "id": cap.id,
            "capability_name": cap.capability_name,
            "capability_version": cap.capability_version,
            "config": cap.config,
            "enabled": cap.enabled,
        }
        for cap in device.capabilities_list
    ]

    tags = [{"tag_name": tag.tag_name, "tag_value": tag.tag_value} for tag in device.tags]

    return {
        "device_id": device.device_id,
        "name": device.name,
        "device_type": device.device_type,
        "capabilities": device.capabilities,
        "config": device.config,
        "environment_id": device.environment_id,
        "runner_version": device.runner_version,
        "registered_at": device.registered_at.isoformat(),
        "last_heartbeat_at": device.last_heartbeat_at.isoformat()
        if device.last_heartbeat_at
        else None,
        "status": device.status,
        "group_id": device.group_id,
        "capabilities_list": capabilities_list,
        "tags": tags,
    }


@router.get("")
async def list_devices(
    status: Optional[str] = None,
    device_type: Optional[str] = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    query = db.query(DeviceDB)

    if status:
        query = query.filter(DeviceDB.status == status)

    if device_type:
        query = query.filter(DeviceDB.device_type == device_type)

    devices = query.all()
    return [
        {
            "device_id": d.device_id,
            "name": d.name,
            "device_type": d.device_type,
            "status": d.status,
            "runner_version": d.runner_version,
            "last_heartbeat_at": d.last_heartbeat_at.isoformat() if d.last_heartbeat_at else None,
        }
        for d in devices
    ]


@router.patch("/{device_id}")
async def update_device(
    device_id: str,
    update: DeviceUpdate,
    db: Session = Depends(get_db),
) -> dict:
    device = db.query(DeviceDB).filter(DeviceDB.device_id == device_id).first()

    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    if update.name is not None:
        device.name = update.name

    if update.device_type is not None:
        device.device_type = update.device_type

    if update.config is not None:
        device.config = update.config

    if update.environment_id is not None:
        device.environment_id = update.environment_id

    if update.group_id is not None:
        device.group_id = update.group_id

    if update.tags is not None:
        db.query(DeviceTagDB).filter(DeviceTagDB.device_id == device_id).delete()

        for tag in update.tags:
            tag_db = DeviceTagDB(
                device_id=device_id,
                tag_name=tag.tag_name,
                tag_value=tag.tag_value,
            )
            db.add(tag_db)

    db.commit()

    return {"device_id": device_id, "status": "updated", "message": "Device updated successfully"}


@router.post("/{device_id}/heartbeat")
async def receive_heartbeat(
    device_id: str,
    heartbeat: Heartbeat,
    db: Session = Depends(get_db),
) -> dict:
    if heartbeat.device_id != device_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="device_id in path does not match heartbeat data",
        )

    device = db.query(DeviceDB).filter(DeviceDB.device_id == device_id).first()

    if device:
        device.status = heartbeat.status.value
        device.last_heartbeat_at = datetime.utcnow()
        if device.runner_version != heartbeat.runner_version:
            device.runner_version = heartbeat.runner_version
    else:
        device_db = DeviceDB(
            device_id=device_id,
            name=f"Device-{device_id}",
            device_type="unknown",
            capabilities=heartbeat.capabilities,
            config={},
            runner_version=heartbeat.runner_version,
            registered_at=datetime.utcnow(),
            last_heartbeat_at=datetime.utcnow(),
            status=heartbeat.status.value,
        )
        db.add(device_db)
        device = device_db

    existing_heartbeat = (
        db.query(DeviceHeartbeatDB).filter(DeviceHeartbeatDB.device_id == device_id).first()
    )

    if existing_heartbeat:
        existing_heartbeat.status = heartbeat.status.value
        existing_heartbeat.current_task_id = heartbeat.current_task_id
        existing_heartbeat.current_task_progress = heartbeat.current_task_progress
        existing_heartbeat.system_resources = heartbeat.system_resources
        existing_heartbeat.capabilities = heartbeat.capabilities
        existing_heartbeat.runner_version = heartbeat.runner_version
        existing_heartbeat.last_seen = datetime.utcnow()
    else:
        heartbeat_db = DeviceHeartbeatDB(
            device_id=device_id,
            status=heartbeat.status.value,
            current_task_id=heartbeat.current_task_id,
            current_task_progress=heartbeat.current_task_progress,
            system_resources=heartbeat.system_resources,
            capabilities=heartbeat.capabilities,
            runner_version=heartbeat.runner_version,
        )
        db.add(heartbeat_db)

    capabilities_list = []
    for cap_name in heartbeat.capabilities.get("supported_step_types", []):
        existing_cap = (
            db.query(DeviceCapabilityDB)
            .filter(
                DeviceCapabilityDB.device_id == device_id,
                DeviceCapabilityDB.capability_name == cap_name,
            )
            .first()
        )

        if not existing_cap:
            cap_db = DeviceCapabilityDB(
                device_id=device_id,
                capability_name=cap_name,
                capability_version=heartbeat.capabilities.get(f"{cap_name}_version"),
                config=heartbeat.capabilities.get(cap_name, {}),
                enabled=True,
            )
            db.add(cap_db)
            capabilities_list.append(cap_name)

    await publish_device_event(
        "device.heartbeat",
        device_id,
        status=heartbeat.status.value,
        runner_version=heartbeat.runner_version,
        capabilities=heartbeat.capabilities,
        details={
            "current_task_id": heartbeat.current_task_id,
            "current_task_progress": heartbeat.current_task_progress,
            "system_resources": heartbeat.system_resources,
        },
    )

    db.commit()

    return {
        "status": "ok",
        "device_registered": device is not None,
        "new_capabilities": capabilities_list,
    }


@router.get("/heartbeats/stats")
async def get_heartbeat_stats(
    db: Session = Depends(get_db),
) -> dict:
    """Get heartbeat statistics and database size information."""
    cleanup_service = HeartbeatCleanupService()
    return cleanup_service.get_heartbeat_stats(db)


@router.post("/heartbeats/cleanup")
async def cleanup_heartbeats(
    db: Session = Depends(get_db),
) -> dict:
    """Manually trigger heartbeat cleanup."""
    cleanup_service = HeartbeatCleanupService()
    result = cleanup_service.cleanup_old_heartbeats(db)
    return result
