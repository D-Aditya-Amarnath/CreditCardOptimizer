import os
from datetime import datetime
from database import DatabaseManager
from gmail_collector import GmailCollector
from vector_store import VectorStore

class OfferAgentOrchestrator:
    """Orchestrator: fetches promotional emails, stores raw in SQLite, embeds in ChromaDB.
    No LLM extraction during sync — LLM is only used at query time for summarization."""
    
    def __init__(self):
         self.db = DatabaseManager()
         self.db.initialize_schema()
         self.collector = GmailCollector()
         self.vector_store = VectorStore()
         
    def sync_all_accounts(self) -> tuple[int, int]:
        """Syncs promotional emails across all configured Gmail accounts. Max once per day."""
        sync_file = ".last_sync"
        today = datetime.now().strftime("%Y-%m-%d")
        
        if os.path.exists(sync_file):
            with open(sync_file, "r") as f:
                last_sync = f.read().strip()
                if last_sync == today:
                    return -1, -1  # Already synced today

        accounts = self.collector.get_configured_accounts()
        total_new = 0
        
        for account in accounts:
            count = self.sync_account(account)
            total_new += count
            
        with open(sync_file, "w") as f:
            f.write(today)
            
        return total_new, len(accounts)

    def sync_account(self, email_address: str) -> int:
        """Fetches and stores new promotional emails. Embeds each in ChromaDB."""
        service, auth_email = self.collector.authenticate(email_address=email_address)
        
        latest_date = self.db.get_latest_email_date(auth_email)
        
        emails = self.collector.fetch_promotional_emails(
            service, authenticated_email=auth_email, after_timestamp=latest_date
        )
        
        new_count = 0
        for payload in emails:
            if self.db.raw_email_exists(payload.email_id):
                continue
            
            # Store in SQLite (source of truth)
            self.db.insert_raw_email(payload)
            self.db.update_email_status(payload.email_id, "STORED")
            
            # Embed in ChromaDB (RAG retrieval layer)
            self.vector_store.add_email(
                email_id=payload.email_id,
                subject=payload.subject or "",
                sender=payload.sender or "",
                body_text=payload.body_text or "",
                date_received=str(payload.date_received) if payload.date_received else "",
                account_email=auth_email
            )
            
            new_count += 1
            
        return new_count
    
    def reindex_vectors(self) -> int:
        """Re-indexes all SQLite emails into ChromaDB. Used for one-time migration."""
        return self.vector_store.reindex_from_db(self.db)
