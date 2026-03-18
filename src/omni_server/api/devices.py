"""API endpoints for device heartbeat management."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from omni_server.database import get_db
from omni_server.models import DeviceHeartbeatDB, Heartbeat

router = APIRouter(prefix="/api/v1/devices", tags=["devices"])


@router.post("/{device_id}/heartbeat")
async def receive_heartbeat(
    device_id: str,
    heartbeat: Heartbeat,
    db: Session = Depends(get_db),
) -> dict:
    """Receive and store device heartbeat."""
    if heartbeat.device_id != device_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="device_id in path does not match heartbeat data",
        )

    existing = db.query(DeviceHeartbeatDB).filter(DeviceHeartbeatDB.device_id == device_id).first()

    if existing:
        existing.status = heartbeat.status.value
        existing.current_task_id = heartbeat.current_task_id
        existing.current_task_progress = heartbeat.current_task_progress
        existing.system_resources = heartbeat.system_resources
        existing.capabilities = heartbeat.capabilities
        existing.runner_version = heartbeat.runner_version
        existing.last_seen = datetime.utcnow()
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

    db.commit()
    return {"status": "ok"}


@router.get("/{device_id}")
async def get_device(
    device_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """Get device information and heartbeat status."""
    device = db.query(DeviceHeartbeatDB).filter(DeviceHeartbeatDB.device_id == device_id).first()

    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    return {
        "device_id": device.device_id,
        "status": device.status,
        "runner_version": device.runner_version,
        "current_task_id": device.current_task_id,
        "current_task_progress": device.current_task_progress,
        "system_resources": device.system_resources,
        "capabilities": device.capabilities,
        "last_seen": device.last_seen.isoformat(),
    }


@router.get("", response_model=list[dict])
async def list_devices(
    status: str | None = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    """List all registered devices."""
    query = db.query(DeviceHeartbeatDB)

    if status:
        query = query.filter(DeviceHeartbeatDB.status == status)

    devices = query.all()
    return [
        {
            "device_id": d.device_id,
            "status": d.status,
            "runner_version": d.runner_version,
            "current_task_id": d.current_task_id,
            "last_seen": d.last_seen.isoformat(),
        }
        for d in devices
    ]
