from fastapi import APIRouter, Depends, Query
from backend.deps import get_current_user
from models import UserProfile
from database import DatabaseManager

router = APIRouter()
db = DatabaseManager()


@router.get("/api/notifications")
async def get_notifications(
    limit: int = Query(20, ge=1, le=100),
    user: UserProfile = Depends(get_current_user)
):
    notifications = db.get_all_notifications(user.id, limit=limit)
    unread_count = db.count_unread_notifications(user.id)
    return {
        "notifications": [
            {
                "id": n.id,
                "type": n.type,
                "title": n.title,
                "message": n.message,
                "read": n.read,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in notifications
        ],
        "unread_count": unread_count,
    }


@router.get("/api/notifications/unread-count")
async def unread_count(user: UserProfile = Depends(get_current_user)):
    return {"count": db.count_unread_notifications(user.id)}


@router.post("/api/notifications/{notif_id}/read")
async def mark_read(notif_id: int, user: UserProfile = Depends(get_current_user)):
    db.mark_notification_read(user.id, notif_id)
    return {"status": "ok"}


@router.post("/api/notifications/mark-all-read")
async def mark_all_read(user: UserProfile = Depends(get_current_user)):
    db.mark_all_notifications_read(user.id)
    return {"status": "ok"}
