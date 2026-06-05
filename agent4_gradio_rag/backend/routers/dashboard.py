from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from agent4_gradio_rag.backend.deps import get_current_user
from shared_core.models import UserProfile
from shared_core.database import DatabaseManager
from shared_core.vector_store import HierarchicalVectorStore
from agent4_gradio_rag.retrieval_auditor import RetrievalAuditor

router = APIRouter()
db = DatabaseManager()
vector_store = HierarchicalVectorStore()
auditor = RetrievalAuditor()
templates = Jinja2Templates(directory="backend/templates")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user: UserProfile = Depends(get_current_user)):
    settings = db.get_user_settings(user.id)
    accounts = db.get_all_accounts()
    
    should_sync = settings.auto_sync_on_open and len(accounts) > 0
    
    if should_sync:
        return RedirectResponse(url="/loading", status_code=303)
    
    stats = db.get_dashboard_stats(user.id)
    user_cards = db.get_user_cards(user.id)
    expiring = db.get_expiring_offers([c.card_name for c in user_cards], days=7)
    notifications = db.get_unread_notifications(user.id, limit=5)
    recent_sync = db.get_sync_history(limit=1)
    audit_summary = auditor.get_audit_summary(db, user.id, limit=50)

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "stats": stats,
        "user_cards": user_cards,
        "expiring_offers": expiring[:5],
        "notifications": notifications,
        "recent_sync": recent_sync[0] if recent_sync else None,
        "audit": audit_summary,
    })


@router.get("/api/dashboard/summary")
async def dashboard_summary(user: UserProfile = Depends(get_current_user)):
    stats = db.get_dashboard_stats(user.id)
    user_cards = db.get_user_cards(user.id)
    expiring = db.get_expiring_offers([c.card_name for c in user_cards], days=7)
    unread_count = db.count_unread_notifications(user.id)

    return {
        **stats,
        "expiring_soon_offers": [
            {
                "id": o.id,
                "merchant": o.merchant,
                "card_name": o.card_name,
                "discount_percent": o.discount_percent,
                "valid_until": o.valid_until.isoformat() if o.valid_until else None,
                "max_cashback": o.max_cashback,
            }
            for o in expiring[:7]
        ],
        "unread_notifications": unread_count,
    }
