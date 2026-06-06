import os
import json
import csv
from datetime import datetime
from typing import List

from agent1_ingestion.imap_ingestion import ImapIngestionClient, load_imap_accounts_from_env
from agent1_ingestion.email_sanitizer import SanitizedEmail
from shared_core.database import DatabaseManager
from shared_core.models import EmailPayload

SYNC_STATE_FILE = ".last_sync.json"
CSV_LOG_FILE = "extracted_emails.csv"

class SyncManager:
    """Manages IMAP delta syncing, SQLite persistence, and CSV logging for Agent 1."""
    
    def __init__(self, db: DatabaseManager = None):
        self.db = db or DatabaseManager()
        self.db.initialize_schema()
        self.ingestion = ImapIngestionClient()
        self._sync_state = self._load_sync_state()

    def _load_sync_state(self) -> dict:
        if os.path.exists(SYNC_STATE_FILE):
            try:
                with open(SYNC_STATE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_sync_state(self) -> None:
        with open(SYNC_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(self._sync_state, f)

    def _append_to_csv(self, email: SanitizedEmail):
        file_exists = os.path.isfile(CSV_LOG_FILE)
        with open(CSV_LOG_FILE, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    "account_email", "message_id", "date_received", 
                    "bank_name", "sender", "subject", "clean_body_preview", "imap_uid"
                ])
            writer.writerow([
                email.account_email,
                email.message_id,
                email.date_received,
                email.bank_name,
                email.sender,
                email.subject,
                email.clean_body[:150].replace('\n', ' ').replace('\r', ''),
                email.imap_uid
            ])

    def sync(self, limit_per_account: int = 50) -> List[SanitizedEmail]:
        """Fetches delta emails, logs to CSV, saves to DB, and returns newly extracted emails."""
        accounts = load_imap_accounts_from_env()
        if not accounts:
            return []

        new_emails = []

        for account in accounts:
            account_key = account.account_email
            since_uid = self._sync_state.get(account_key, 0)
            max_seen_uid = since_uid

            # Fetch delta
            for email in self.ingestion.iter_sanitized_emails(
                [account], 
                limit_per_account=limit_per_account, 
                since_uid=since_uid
            ):
                if email.imap_uid > max_seen_uid:
                    max_seen_uid = email.imap_uid
                
                # Check DB to prevent duplicates just in case
                if self.db.raw_email_exists(email.message_id):
                    continue

                # Parse date string to datetime for DB
                try:
                    dt_received = datetime.fromisoformat(email.date_received)
                except Exception:
                    dt_received = datetime.utcnow()

                # 1. Save to SQLite Database
                payload = EmailPayload(
                    email_id=email.message_id,
                    sender=email.sender,
                    subject=email.subject,
                    date_received=dt_received,
                    body_text=email.clean_body,
                    body_html="",  # Sanitizer strips HTML, we store clean text
                    labels=[],
                    account_email=email.account_email,
                    image_urls=[],
                    email_type="promotional"
                )
                self.db.insert_raw_email(payload)
                
                # 2. Append to CSV for Quality Checks
                self._append_to_csv(email)
                
                new_emails.append(email)

            # Update highest UID for this account
            if max_seen_uid > since_uid:
                self._sync_state[account_key] = max_seen_uid
        
        # Persist new sync state
        self._save_sync_state()

        return new_emails
