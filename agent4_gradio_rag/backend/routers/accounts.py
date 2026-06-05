from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
import asyncio
import json

from agent4_gradio_rag.backend.deps import get_current_user
from shared_core.database import db
from agent4_gradio_rag import orchestrator

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


class GmailAccountAdd(BaseModel):
    email: str
    credentials_json: str


class AccountLinkRequest(BaseModel):
    email: str
    profile_id: int
    label: Optional[str] = None


@router.get("/")
async def list_accounts(current_user=Depends(get_current_user)):
    accounts = db.get_all_accounts()
    return {"accounts": accounts}


@router.post("/link")
async def link_account(data: AccountLinkRequest, current_user=Depends(get_current_user)):
    mapping = db.assign_account_to_profile(
        profile_id=data.profile_id,
        account_email=data.email,
        label=data.label,
        is_primary=False
    )
    return {
        "status": "ok",
        "account_email": mapping.account_email,
        "profile_id": mapping.profile_id
    }


@router.delete("/{account_email}")
async def unlink_account(account_email: str, current_user=Depends(get_current_user)):
    db.remove_account_mapping(account_email)
    return {"status": "ok"}


@router.post("/sync/{account_email}")
async def sync_account(account_email: str, background_tasks: BackgroundTasks, current_user=Depends(get_current_user)):
    from shared_core.database import db as _db
    
    sync_history = _db.create_sync_history(account_email)
    
    def run_sync():
        try:
            collector = orchestrator.GmailCollector()
            emails = collector.fetch_new_emails(account_email)
            
            new_emails = 0
            new_offers = 0
            new_transactions = 0
            
            for email_data in emails:
                payload = orchestrator.process_email_pipeline(email_data)
                if payload:
                    new_emails += 1
                    if payload.get("offers_processed"):
                        new_offers += payload["offers_processed"]
                    if payload.get("transactions_processed"):
                        new_transactions += payload["transactions_processed"]
            
            _db.update_sync_history(
                sync_id=sync_history.id,
                status="completed",
                new_emails=new_emails,
                new_offers=new_offers,
                new_transactions=new_transactions
            )
        except Exception as e:
            _db.update_sync_history(
                sync_id=sync_history.id,
                status="failed",
                errors=[str(e)]
            )
    
    background_tasks.add_task(run_sync)
    
    return {
        "status": "started",
        "sync_id": sync_history.id,
        "account_email": account_email
    }


@router.get("/sync-status/{sync_id}")
async def get_sync_status(sync_id: int, current_user=Depends(get_current_user)):
    with db.get_session() as session:
        from shared_core.models import SyncHistory
        sync = session.query(SyncHistory).filter(SyncHistory.id == sync_id).first()
        if not sync:
            raise HTTPException(404, "Sync not found")
        
        return {
            "id": sync.id,
            "account_email": sync.account_email,
            "status": sync.status,
            "new_emails": sync.new_emails,
            "new_offers": sync.new_offers,
            "new_banners": sync.new_banners,
            "new_transactions": sync.new_transactions,
            "errors": sync.errors,
            "started_at": sync.started_at.isoformat() if sync.started_at else None,
            "completed_at": sync.completed_at.isoformat() if sync.completed_at else None,
        }


sync_results = {}


@router.post("/sync-all")
async def sync_all_accounts(background_tasks: BackgroundTasks, current_user=Depends(get_current_user)):
    accounts = db.get_all_accounts()
    if not accounts:
        return {"status": "no_accounts"}
    
    sync_ids = []
    for acc in accounts:
        sync_history = db.create_sync_history(acc["account_email"])
        sync_ids.append({"account": acc["account_email"], "sync_id": sync_history.id})
    
    async def run_syncs():
        for acc_info in sync_ids:
            try:
                collector = orchestrator.GmailCollector()
                emails = collector.fetch_new_emails(acc_info["account"])
                
                new_emails = 0
                new_offers = 0
                new_transactions = 0
                
                for email_data in emails:
                    payload = orchestrator.process_email_pipeline(email_data)
                    if payload:
                        new_emails += 1
                        if payload.get("offers_processed"):
                            new_offers += payload["offers_processed"]
                        if payload.get("transactions_processed"):
                            new_transactions += payload["transactions_processed"]
                
                db.update_sync_history(
                    sync_id=acc_info["sync_id"],
                    status="completed",
                    new_emails=new_emails,
                    new_offers=new_offers,
                    new_transactions=new_transactions
                )
                sync_results[acc_info["sync_id"]] = "completed"
            except Exception as e:
                db.update_sync_history(
                    sync_id=acc_info["sync_id"],
                    status="failed",
                    errors=[str(e)]
                )
                sync_results[acc_info["sync_id"]] = "failed"
        
        sync_results["all_done"] = True
    
    background_tasks.add_task(run_syncs)
    
    return {
        "status": "started",
        "syncs": sync_ids
    }


@router.get("/sync-stream")
async def sync_stream(current_user=Depends(get_current_user)):
    accounts = db.get_all_accounts()
    
    if not accounts:
        async def no_accounts():
            yield "data: " + json.dumps({"type": "done", "message": "No accounts configured"}) + "\n\n"
        return StreamingResponse(no_accounts(), media_type="text/event-stream")
    
    async def event_generator():
        for acc in accounts:
            try:
                yield f"data: {json.dumps({'type': 'starting', 'account': acc['account_email']})}\n\n"
                
                sync_history = db.create_sync_history(acc["account_email"])
                
                collector = orchestrator.GmailCollector()
                emails = collector.fetch_new_emails(acc["account_email"])
                
                total = len(emails)
                new_emails = 0
                new_offers = 0
                new_transactions = 0
                
                for i, email_data in enumerate(emails):
                    yield f"data: {json.dumps({'type': 'progress', 'account': acc['account_email'], 'current': i+1, 'total': total})}\n\n"
                    
                    payload = orchestrator.process_email_pipeline(email_data)
                    if payload:
                        new_emails += 1
                        if payload.get("offers_processed"):
                            new_offers += payload["offers_processed"]
                        if payload.get("transactions_processed"):
                            new_transactions += payload["transactions_processed"]
                    
                    await asyncio.sleep(0.01)
                
                db.update_sync_history(
                    sync_id=sync_history.id,
                    status="completed",
                    new_emails=new_emails,
                    new_offers=new_offers,
                    new_transactions=new_transactions
                )
                
                yield f"data: {json.dumps({'type': 'completed', 'account': acc['account_email'], 'emails': new_emails, 'offers': new_offers, 'transactions': new_transactions})}\n\n"
                
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'account': acc['account_email'], 'error': str(e)})}\n\n"
        
        yield f"data: {json.dumps({'type': 'all_done'})}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")
