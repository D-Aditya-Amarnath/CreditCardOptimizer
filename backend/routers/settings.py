from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.deps import get_current_user
from database import db

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    auto_sync_on_open: bool = None
    sync_frequency_hours: int = None


@router.get("/")
async def get_settings(current_user=Depends(get_current_user)):
    settings = db.get_user_settings(current_user.id)
    return {
        "auto_sync_on_open": settings.auto_sync_on_open,
        "sync_frequency_hours": settings.sync_frequency_hours,
    }


@router.put("/")
async def update_settings(data: SettingsUpdate, current_user=Depends(get_current_user)):
    settings = db.update_user_settings(
        user_id=current_user.id,
        auto_sync_on_open=data.auto_sync_on_open,
        sync_frequency_hours=data.sync_frequency_hours
    )
    return {
        "auto_sync_on_open": settings.auto_sync_on_open,
        "sync_frequency_hours": settings.sync_frequency_hours,
    }


@router.get("/sync-frequency-options")
async def get_sync_frequency_options():
    return [
        {"value": 1, "label": "Every hour"},
        {"value": 6, "label": "Every 6 hours"},
        {"value": 12, "label": "Every 12 hours"},
        {"value": 24, "label": "Daily"},
        {"value": 168, "label": "Weekly"},
    ]
