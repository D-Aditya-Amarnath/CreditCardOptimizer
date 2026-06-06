import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
from time import monotonic
from typing import Optional

from mcp.server.fastmcp import FastMCP
from mcp.shared.exceptions import McpError
from mcp.types import ErrorData, INTERNAL_ERROR

from agent1_ingestion.sync_manager import SyncManager
from shared_core.database import DatabaseManager
from agent1_ingestion.email_sanitizer import EmailSanitizer


class KycEmailContextServer:
    """Read-only MCP bridge for local sanitized email context."""

    def __init__(self, cache_ttl_seconds: int = 120):
        self.mcp = FastMCP("Know Your Card Local Email Bridge")
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cache_loaded_at = 0.0
        self._cache = []
        self._register_tools()

    def _register_tools(self) -> None:
        @self.mcp.tool()
        def list_recent_sanitized_emails(limit: int = 10, account_email: Optional[str] = None) -> str:
            """Return recent sanitized promotional email context. Read-only and local-only."""
            try:
                emails = self._load_recent(limit=max(limit, 1), account_email=account_email)
                return json.dumps([self._public_email(email) for email in emails[:limit]], ensure_ascii=False)
            except Exception as exc:
                raise McpError(ErrorData(code=INTERNAL_ERROR, message=str(exc)))

        @self.mcp.tool()
        def get_email_context(message_id: str) -> str:
            """Return one sanitized email by message id from the in-memory local cache."""
            try:
                self._load_recent(limit=50)
                for email in self._cache:
                    if email.get("message_id") == message_id:
                        return json.dumps(self._public_email(email), ensure_ascii=False)
                return json.dumps({"error": "message_id not found"})
            except Exception as exc:
                raise McpError(ErrorData(code=INTERNAL_ERROR, message=str(exc)))

        @self.mcp.tool()
        def search_recent_emails(query: str, limit: int = 10, account_email: Optional[str] = None) -> str:
            """Search sanitized recent email text in memory."""
            try:
                normalized = (query or "").lower().strip()
                emails = self._load_recent(limit=max(limit * 3, 25), account_email=account_email)
                matches = [
                    email for email in emails
                    if normalized in f"{email.get('subject', '')} {email.get('clean_body', '')}".lower()
                ]
                return json.dumps([self._public_email(email) for email in matches[:limit]], ensure_ascii=False)
            except Exception as exc:
                raise McpError(ErrorData(code=INTERNAL_ERROR, message=str(exc)))

    def _load_recent(self, *, limit: int, account_email: Optional[str] = None) -> list[dict]:
        now = monotonic()
        if self._cache and now - self._cache_loaded_at < self.cache_ttl_seconds:
            emails = self._cache
        else:
            # 1. Trigger delta sync to fetch any newly arrived emails since last UI refresh
            try:
                SyncManager().sync(limit_per_account=limit)
            except Exception as e:
                print(f"Background Sync Error: {e}")

            # 2. Load latest emails from SQLite (which now contains historical + new delta)
            db = DatabaseManager()
            db_emails = db.get_emails_paginated(limit=limit)
            
            sanitizer = EmailSanitizer()
            emails = []
            for db_email in db_emails:
                emails.append({
                    "bank_name": sanitizer.infer_bank_name(db_email.sender),
                    "subject": db_email.subject,
                    "clean_body": db_email.body_text,
                    "sender": db_email.sender,
                    "account_email": db_email.account_email,
                    "message_id": db_email.email_id,
                    "date_received": db_email.date_received.isoformat() if db_email.date_received else "",
                })

            self._cache = emails
            self._cache_loaded_at = now

        if account_email:
            emails = [email for email in emails if email.get("account_email") == account_email]
        return emails

    def _public_email(self, email: dict) -> dict:
        return {
            "bank_name": email.get("bank_name", ""),
            "subject": email.get("subject", ""),
            "clean_body": email.get("clean_body", ""),
            "sender": email.get("sender", ""),
            "account_email": email.get("account_email", ""),
            "message_id": email.get("message_id", ""),
            "date_received": email.get("date_received", ""),
        }

    def run(self) -> None:
        self.mcp.run()


if __name__ == "__main__":
    KycEmailContextServer().run()
