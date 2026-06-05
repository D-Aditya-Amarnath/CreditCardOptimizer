import os
import json
import chromadb
from chromadb.utils import embedding_functions
from typing import List, Optional, Dict, Any


class HierarchicalVectorStore:
    def __init__(self, persist_dir: str = "./chroma_db"):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()

        self.email_collection = self.client.get_or_create_collection(
            name="emails",
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"}
        )

        self.offer_collection = self.client.get_or_create_collection(
            name="offer_chunks",
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"}
        )

        self.summary_collection = self.client.get_or_create_collection(
            name="merchant_summaries",
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"}
        )

    def add_email(self, email_id: str, full_text: str, sender: str,
                  date_received: str, account_email: str):
        self.email_collection.add(
            ids=[email_id],
            documents=[full_text[:8000]],
            metadatas=[{
                "sender": sender or "",
                "date_received": str(date_received) if date_received else "",
                "account_email": account_email,
            }]
        )

    def add_chunk(self, chunk_id: str, email_id: str, text: str,
                  chunk_type: str, weight: float, sender: str,
                  date_received: str, account_email: str, metadata: Dict[str, Any]):
        self.offer_collection.add(
            ids=[chunk_id],
            documents=[text[:2000]],
            metadatas=[{
                "email_id": email_id,
                "chunk_type": chunk_type,
                "weight": weight,
                "merchants": json.dumps(metadata.get("merchants", [])),
                "cards": json.dumps(metadata.get("cards", [])),
                "discount_percent": metadata.get("discount_percent"),
                "min_spend": metadata.get("min_spend"),
                "max_cashback": metadata.get("max_cashback"),
                "expiry_date": metadata.get("expiry_date"),
                "offer_type": metadata.get("offer_type"),
                "sender": sender or "",
                "date_received": str(date_received) if date_received else "",
                "account_email": account_email,
            }]
        )

    def search(self, query: str, intent: str = "search",
               top_k: int = 15, use_reranker: bool = True,
               filters: Dict = None) -> List[Dict[str, Any]]:
        if intent == "recommend":
            candidates = self._search_collection(
                self.offer_collection, query, top_k=top_k * 2, filters=filters
            )
        elif intent == "search":
            offer_results = self._search_collection(
                self.offer_collection, query, top_k=10
            )
            email_results = self._search_collection(
                self.email_collection, query, top_k=5
            )
            candidates = self._merge_results(offer_results, email_results)
        else:
            candidates = self._search_collection(
                self.offer_collection, query, top_k=top_k
            )

        if use_reranker and candidates:
            candidates = self._apply_domain_boosts(candidates, query)

        candidates = self._filter_by_weight(candidates, min_weight=0.3)

        return candidates[:top_k]

    def _search_collection(self, collection, query: str,
                           top_k: int = 15, filters: Dict = None) -> List[Dict]:
        count = collection.count()
        if count == 0:
            return []

        actual_k = min(top_k, count)

        try:
            results = collection.query(
                query_texts=[query],
                n_results=actual_k,
                include=["documents", "metadatas", "distances"]
            )
        except Exception:
            return []

        output = []
        if results and results.get('ids') and results['ids']:
            for i, doc_id in enumerate(results['ids'][0]):
                meta = (results.get('metadatas') or [[{}]])[0][i] if results.get('metadatas') else {}
                doc = (results.get('documents') or [['']])[0][i] if results.get('documents') else ""
                distance = (results.get('distances') or [[0]])[0][i] if results.get('distances') else 0

                merchants = meta.get("merchants", "[]")
                if isinstance(merchants, str):
                    try:
                        merchants = json.loads(merchants)
                    except Exception:
                        merchants = []

                cards = meta.get("cards", "[]")
                if isinstance(cards, str):
                    try:
                        cards = json.loads(cards)
                    except Exception:
                        cards = []

                output.append({
                    "chunk_id": doc_id,
                    "email_id": meta.get("email_id", doc_id),
                    "document": doc,
                    "body_preview": doc[:1500],
                    "subject": meta.get("subject", ""),
                    "sender": meta.get("sender", ""),
                    "date_received": meta.get("date_received", ""),
                    "account_email": meta.get("account_email", ""),
                    "similarity": round(1 - distance, 3),
                    "chunk_type": meta.get("chunk_type", "general"),
                    "weight": meta.get("weight", 1.0),
                    "merchants": merchants,
                    "cards": cards,
                    "discount_percent": meta.get("discount_percent"),
                    "min_spend": meta.get("min_spend"),
                    "max_cashback": meta.get("max_cashback"),
                    "expiry_date": meta.get("expiry_date"),
                    "offer_type": meta.get("offer_type"),
                    "metadata": meta,
                })

        return output

    def _merge_results(self, offer_results: List, email_results: List) -> List:
        seen_ids = set()
        merged = []

        for r in offer_results:
            if r["chunk_id"] not in seen_ids:
                seen_ids.add(r["chunk_id"])
                merged.append(r)

        for r in email_results:
            if r["chunk_id"] not in seen_ids:
                seen_ids.add(r["chunk_id"])
                merged.append(r)

        return merged

    def _apply_domain_boosts(self, candidates: List[Dict], query: str) -> List[Dict]:
        query_lower = query.lower()
        query_banks = self._extract_banks(query_lower)
        query_merchants = self._extract_merchants(query_lower)

        for c in candidates:
            score = c.get("similarity", 0)

            sender_lower = c.get("sender", "").lower()
            if any(bank in sender_lower for bank in query_banks):
                score += 0.15

            if set(c.get("merchants", [])) & set(query_merchants):
                score += 0.1

            if c.get("chunk_type") == "offer":
                score += 0.05

            if self._is_recent(c.get("date_received", ""), days=30):
                score += 0.05

            if c.get("expiry_date") and self._is_expired(c.get("expiry_date")):
                score -= 0.25

            c["final_score"] = score

        return sorted(candidates, key=lambda x: x.get("final_score", x.get("similarity", 0)), reverse=True)

    def _filter_by_weight(self, candidates: List[Dict], min_weight: float = 0.0) -> List[Dict]:
        return [c for c in candidates if c.get("weight", 1.0) >= min_weight]

    def _extract_banks(self, text: str) -> set:
        banks = {
            "hdfc": "hdfc bank", "sbi": "sbi card", "icici": "icici bank",
            "axis": "axis bank", "kotak": "kotak", "yes bank": "yes bank",
            "indusind": "indusind", "idfc": "idfc first", "rbl": "rbl bank",
            "federal": "federal bank", "amex": "amex", "bajaj": "bajaj",
            "onecard": "onecard", "slice": "slice",
        }
        return {k for k, v in banks.items() if k in text}

    def _extract_merchants(self, text: str) -> set:
        merchants = {
            "amazon", "myntra", "swiggy", "zomato", "flipkart",
            "bigbasket", "bookmyshow", "makemytrip", "dominos",
            "uber", "ola", "netmeds", "ajio", "nykaa",
        }
        return {m for m in merchants if m in text}

    def _is_recent(self, date_str: str, days: int = 30) -> bool:
        if not date_str:
            return False
        try:
            from datetime import datetime, timedelta
            if 'T' in date_str:
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            else:
                dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
            return (datetime.utcnow() - dt).days <= days
        except Exception:
            return False

    def _is_expired(self, expiry_str: str) -> bool:
        if not expiry_str:
            return False
        try:
            from datetime import datetime
            for fmt in ["%d %B %Y", "%Y-%m-%d", "%d-%m-%Y"]:
                try:
                    dt = datetime.strptime(expiry_str.strip(), fmt)
                    return dt < datetime.utcnow()
                except ValueError:
                    continue
        except Exception:
            pass
        return False

    def upsert_merchant_summary(self, merchant: str, summary_text: str, metadata: Dict):
        self.summary_collection.upsert(
            ids=[merchant.lower().replace(" ", "_")],
            documents=[summary_text],
            metadatas=[metadata]
        )

    def count(self) -> Dict[str, int]:
        return {
            "emails": self.email_collection.count(),
            "offer_chunks": self.offer_collection.count(),
            "merchant_summaries": self.summary_collection.count(),
        }

    def reindex_from_db(self, db_manager) -> int:
        from models import RawEmailModel, ChunkModel
        indexed = 0

        with db_manager.get_session() as session:
            emails = session.query(RawEmailModel).all()
            for email in emails:
                full_text = f"{email.subject}\n{email.body_text or ''}"
                self.add_email(
                    email_id=email.email_id,
                    full_text=full_text,
                    sender=email.sender,
                    date_received=str(email.date_received) if email.date_received else "",
                    account_email=email.account_email
                )
                indexed += 1

            chunks = session.query(ChunkModel).all()
            for chunk in chunks:
                self.add_chunk(
                    chunk_id=f"{chunk.email_id}_chunk_{chunk.chunk_index}",
                    email_id=chunk.email_id,
                    text=chunk.text,
                    chunk_type=chunk.chunk_type,
                    weight=chunk.weight,
                    sender="",
                    date_received="",
                    account_email="",
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

        return indexed

    def clear(self):
        try:
            self.client.delete_collection("emails")
            self.client.delete_collection("offer_chunks")
            self.client.delete_collection("merchant_summaries")
        except Exception:
            pass
