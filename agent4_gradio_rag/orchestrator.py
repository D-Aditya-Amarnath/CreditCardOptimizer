import os
from datetime import datetime
from shared_core.database import DatabaseManager
from agent1_ingestion.gmail_collector import GmailCollector
from services.vector_store import HierarchicalVectorStore
from agent4_gradio_rag.chunker import SemanticChunker
from shared_core.banner_extractor import BannerExtractor
from shared_core.structured_extractor import StructuredExtractor
from shared_core.transaction_parser import TransactionParser
from shared_core.merchant_normalizer import MerchantNormalizer


class OfferAgentOrchestrator:
    def __init__(self):
        self.db = DatabaseManager()
        self.db.initialize_schema()
        self.collector = GmailCollector()
        self.vector_store = HierarchicalVectorStore()
        self.chunker = SemanticChunker()
        self.banner_extractor = BannerExtractor()
        self.structured_extractor = StructuredExtractor()
        self.merchant_normalizer = MerchantNormalizer(self.db)
        self.transaction_parser = TransactionParser(self.merchant_normalizer)

    def sync_all_accounts(self) -> tuple[int, int]:
        sync_file = ".last_sync"
        today = datetime.now().strftime("%Y-%m-%d")

        if os.path.exists(sync_file):
            with open(sync_file, "r") as f:
                last_sync = f.read().strip()
                if last_sync == today:
                    return -1, -1

        accounts = self.collector.get_configured_accounts()
        total_new = 0

        for account in accounts:
            count = self.sync_account(account)
            total_new += count

        with open(sync_file, "w") as f:
            f.write(today)

        return total_new, len(accounts)

    def sync_account(self, account_email: str) -> int:
        service, auth_email = self.collector.authenticate(email_address=account_email)
        latest_date = self.db.get_latest_email_date(auth_email)

        emails = self.collector.fetch_promotional_emails(
            service, authenticated_email=auth_email, after_timestamp=latest_date
        )

        new_count = 0

        for payload in emails:
            if self.db.raw_email_exists(payload.email_id):
                continue

            email_type = self.transaction_parser.classify_email_type(
                payload.sender, payload.subject, payload.body_text
            )
            payload.email_type = email_type

            self.db.insert_raw_email(payload)

            if email_type == "transactional":
                txn = self.transaction_parser.parse_transaction(
                    sender=payload.sender,
                    subject=payload.subject,
                    body_text=payload.body_text,
                    email_id=payload.email_id,
                    account_email=auth_email,
                    date_received=payload.date_received,
                )
                if txn:
                    profile = self.db.get_profile_by_account(auth_email)
                    if profile:
                        self.db.insert_transaction(txn, profile.id)
                    else:
                        self.db.insert_transaction(txn, profile_id=None)

                self.db.update_email_status(payload.email_id, "TXN_PARSED")

            else:
                banner_text = self._extract_banners(payload)
                combined_body = (payload.body_text or "") + "\n" + banner_text

                chunks = self.chunker.chunk_email(
                    body_text=combined_body,
                    body_html=payload.body_html or "",
                    email_id=payload.email_id
                )

                self._index_email_and_chunks(payload, chunks)
                self._extract_structured_offers(combined_body, payload)
                self.db.update_email_status(payload.email_id, "EXTRACTED")

            new_count += 1

        return new_count

    def _extract_banners(self, payload) -> str:
        banner_texts = []
        seen_urls = set()

        for url in (payload.image_urls or []):
            if url in seen_urls:
                continue
            seen_urls.add(url)

            result = self.banner_extractor.fetch_and_extract(url)
            self.db.insert_banner_offer(result, payload.email_id)

            if result.extraction_status == "success" and result.extracted_text:
                banner_texts.append(f"\n[From: {url}]\n{result.extracted_text}")

        return "\n".join(banner_texts)

    def _index_email_and_chunks(self, payload, chunks: list):
        full_text = f"{payload.subject}\n{payload.body_text or ''}"

        self.vector_store.add_email(
            email_id=payload.email_id,
            full_text=full_text,
            sender=payload.sender,
            date_received=str(payload.date_received) if payload.date_received else "",
            account_email=payload.account_email
        )

        for i, chunk in enumerate(chunks):
            chunk_id = f"{payload.email_id}_chunk_{i}"
            self.db.insert_chunk(chunk)

            self.vector_store.add_chunk(
                chunk_id=chunk_id,
                email_id=payload.email_id,
                text=chunk.text,
                chunk_type=chunk.chunk_type,
                weight=chunk.weight,
                sender=payload.sender,
                date_received=str(payload.date_received) if payload.date_received else "",
                account_email=payload.account_email,
                metadata={
                    "merchants": chunk.merchants or [],
                    "cards": chunk.cards or [],
                    "discount_percent": chunk.discount_percent,
                    "min_spend": chunk.min_spend,
                    "max_cashback": chunk.max_cashback,
                    "expiry_date": chunk.expiry_date,
                    "offer_type": chunk.offer_type,
                }
            )

    def _extract_structured_offers(self, body_text: str, payload):
        offers = self.structured_extractor.extract_from_text(
            body_text=body_text,
            email_id=payload.email_id,
            sender=payload.sender,
            account_email=payload.account_email
        )

        for offer in offers:
            if not self.db.offer_exists(offer.unique_hash):
                self.db.insert_offer(offer)

    def reindex_vectors(self) -> int:
        self.vector_store.clear()
        return self.vector_store.reindex_from_db(self.db)
