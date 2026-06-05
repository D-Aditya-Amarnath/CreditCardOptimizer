from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from backend.deps import get_current_user
from models import UserProfile
from database import DatabaseManager
from gmail_collector import GmailCollector
import asyncio

router = APIRouter()
db = DatabaseManager()
collector = GmailCollector()


@router.get("/emails", response_class=HTMLResponse)
async def emails_page(
    request: Request,
    page: int = Query(1, ge=1),
    user: UserProfile = Depends(get_current_user)
):
    page_size = 20
    offset = (page - 1) * page_size
    emails = db.get_emails_paginated(limit=page_size, offset=offset)
    total = db.count_emails()
    total_pages = (total + page_size - 1) // page_size

    return {
        "request": request,
        "user": user,
        "emails": emails,
        "page": page,
        "total_pages": total_pages,
        "total": total,
    }


@router.get("/api/emails")
async def list_emails(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: UserProfile = Depends(get_current_user)
):
    offset = (page - 1) * limit
    emails = db.get_emails_paginated(limit=limit, offset=offset)
    total = db.count_emails()

    return {
        "emails": [
            {
                "email_id": e.email_id,
                "sender": e.sender,
                "subject": e.subject,
                "date_received": e.date_received.isoformat() if e.date_received else None,
                "account_email": e.account_email,
                "processed_status": e.processed_status,
            }
            for e in emails
        ],
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit,
    }


@router.get("/api/emails/{email_id}")
async def get_email(email_id: str, user: UserProfile = Depends(get_current_user)):
    email = db.get_email_by_id(email_id)
    if not email:
        return {"error": "Email not found"}

    banners = db.get_banners_by_email(email_id)

    return {
        "email_id": email.email_id,
        "sender": email.sender,
        "subject": email.subject,
        "date_received": email.date_received.isoformat() if email.date_received else None,
        "body_text": email.body_text,
        "body_html": email.body_html,
        "account_email": email.account_email,
        "processed_status": email.processed_status,
        "banners": [
            {
                "banner_url": b.banner_url,
                "content_type": b.content_type,
                "extracted_text": b.extracted_text,
                "extraction_method": b.extraction_method,
                "extraction_status": b.extraction_status,
            }
            for b in banners
        ],
    }


@router.get("/sync", response_class=HTMLResponse)
async def sync_page(request: Request, user: UserProfile = Depends(get_current_user)):
    accounts = collector.get_configured_accounts()
    sync_history = db.get_sync_history(limit=10)
    return {
        "request": request,
        "user": user,
        "accounts": accounts,
        "sync_history": sync_history,
    }


@router.post("/api/sync")
async def trigger_sync(user: UserProfile = Depends(get_current_user)):
    from orchestrator import OfferAgentOrchestrator

    async def run_sync():
        orchestrator = OfferAgentOrchestrator()
        new_count, account_count = orchestrator.sync_all_accounts()
        return new_count, account_count

    new_count, account_count = await asyncio.to_thread(run_sync)

    if new_count == -1:
        return {"status": "already_synced", "message": "Already synced today"}

    return {
        "status": "completed",
        "new_emails": new_count,
        "accounts_synced": account_count,
    }


@router.get("/api/sync/status")
async def sync_status(user: UserProfile = Depends(get_current_user)):
    history = db.get_sync_history(limit=5)
    accounts = collector.get_configured_accounts()
    recent = db.get_recent_sync_date()

    return {
        "accounts": accounts,
        "recent_sync": recent.isoformat() if recent else None,
        "history": [
            {
                "id": h.id,
                "account_email": h.account_email,
                "status": h.status,
                "new_emails": h.new_emails,
                "new_offers": h.new_offers,
                "started_at": h.started_at.isoformat() if h.started_at else None,
                "completed_at": h.completed_at.isoformat() if h.completed_at else None,
            }
            for h in history
        ],
    }
