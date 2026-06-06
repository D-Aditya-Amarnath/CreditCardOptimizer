import email
import imaplib
import json
import os
from dataclasses import dataclass
from email.message import Message
from email.utils import parsedate_to_datetime
from typing import Iterable, Iterator, Optional

from agent1_ingestion.email_sanitizer import EmailSanitizer, SanitizedEmail


@dataclass(frozen=True)
class ImapAccount:
    account_email: str
    host: str
    username: str
    password: str
    port: int = 993
    mailbox: str = "INBOX"


class ImapConfigError(ValueError):
    pass


def load_imap_accounts_from_env() -> list[ImapAccount]:
    """Load local IMAP account config without committing secrets."""
    raw = os.getenv("KYC_IMAP_ACCOUNTS")
    config_file = os.getenv("KYC_IMAP_ACCOUNTS_FILE")

    if config_file:
        with open(config_file, "r", encoding="utf-8") as handle:
            raw = handle.read()

    if not raw:
        return []

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ImapConfigError("KYC_IMAP_ACCOUNTS must be valid JSON") from exc

    if not isinstance(payload, list):
        raise ImapConfigError("KYC_IMAP_ACCOUNTS must be a JSON array")

    accounts = []
    for item in payload:
        missing = {"account_email", "host", "username", "password"} - set(item)
        if missing:
            raise ImapConfigError(f"Missing IMAP config fields: {', '.join(sorted(missing))}")
        accounts.append(
            ImapAccount(
                account_email=item["account_email"],
                host=item["host"],
                username=item["username"],
                password=item["password"],
                port=int(item.get("port", 993)),
                mailbox=item.get("mailbox", "INBOX"),
            )
        )
    return accounts


class ImapIngestionClient:
    def __init__(self, sanitizer: Optional[EmailSanitizer] = None):
        self.sanitizer = sanitizer or EmailSanitizer()

    def iter_sanitized_emails(
        self,
        accounts: Iterable[ImapAccount],
        *,
        limit_per_account: int = 25,
        mailbox: Optional[str] = None,
        since_uid: Optional[int] = None,
        search_query: str = "ALL",
    ) -> Iterator[SanitizedEmail]:
        for account in accounts:
            yield from self._iter_account(
                account,
                mailbox=mailbox or account.mailbox,
                limit=limit_per_account,
                since_uid=since_uid,
                search_query=search_query,
            )

    def _iter_account(
        self,
        account: ImapAccount,
        *,
        mailbox: str,
        limit: int,
        since_uid: Optional[int],
        search_query: str,
    ) -> Iterator[SanitizedEmail]:
        with imaplib.IMAP4_SSL(account.host, account.port) as conn:
            conn.login(account.username, account.password)
            conn.select(mailbox, readonly=True)

            status, data = conn.uid("search", None, search_query)
            if status != "OK" or not data:
                return

            uids = [int(uid) for uid in data[0].split() if uid]
            if since_uid is not None:
                uids = [uid for uid in uids if uid > since_uid]

            for uid in reversed(uids[-limit:]):
                status, msg_data = conn.uid("fetch", str(uid), "(RFC822)")
                if status != "OK":
                    continue
                raw_message = self._extract_raw_message(msg_data)
                if not raw_message:
                    continue
                message = email.message_from_bytes(raw_message)
                yield self._sanitize_message(message, account, uid)

    def _sanitize_message(self, message: Message, account: ImapAccount, uid: int) -> SanitizedEmail:
        body_html, fallback_text = self._extract_bodies(message)
        subject = str(email.header.make_header(email.header.decode_header(message.get("Subject", ""))))
        sender = str(email.header.make_header(email.header.decode_header(message.get("From", ""))))
        date_received = self._parse_date(message.get("Date"))
        message_id = message.get("Message-ID") or f"{account.account_email}:{uid}"

        return self.sanitizer.sanitize(
            body_html,
            subject=subject,
            sender=sender,
            account_email=account.account_email,
            message_id=message_id,
            date_received=date_received,
            fallback_text=fallback_text,
            imap_uid=uid,
        )

    def _extract_bodies(self, message: Message) -> tuple[str, str]:
        html_parts = []
        text_parts = []

        if message.is_multipart():
            parts = message.walk()
        else:
            parts = [message]

        for part in parts:
            content_type = part.get_content_type()
            disposition = (part.get_content_disposition() or "").lower()
            if disposition == "attachment":
                continue

            if content_type not in {"text/html", "text/plain"}:
                continue

            payload = part.get_payload(decode=True)
            if not payload:
                continue
            charset = part.get_content_charset() or "utf-8"
            decoded = payload.decode(charset, errors="replace")
            if content_type == "text/html":
                html_parts.append(decoded)
            else:
                text_parts.append(decoded)

        return "\n".join(html_parts), "\n".join(text_parts)

    def _extract_raw_message(self, msg_data) -> bytes:
        for item in msg_data:
            if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], bytes):
                return item[1]
        return b""

    def _parse_date(self, raw_date: Optional[str]) -> str:
        if not raw_date:
            return ""
        try:
            return parsedate_to_datetime(raw_date).isoformat()
        except Exception:
            return raw_date
