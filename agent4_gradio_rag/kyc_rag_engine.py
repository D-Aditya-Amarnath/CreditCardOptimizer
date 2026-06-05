import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any, Optional

from shared_core.database import DatabaseManager
from agent4_gradio_rag.local_llama import LocalLlamaJsonGenerator
from shared_core.vector_store import HierarchicalVectorStore


@dataclass
class KycContext:
    email_context: list[dict[str, Any]]
    rule_context: list[dict[str, Any]]


class McpEmailClient:
    """Small MCP stdio client for the Phase 1 read-only email bridge."""

    def __init__(self, command: Optional[str] = None):
        self.command = command or os.getenv("KYC_MCP_COMMAND", "python agent1_ingestion/kyc_mcp_server.py")

    def list_recent_sanitized_emails(self, limit: int = 10, account_email: Optional[str] = None) -> list[dict[str, Any]]:
        return asyncio.run(self._call_tool("list_recent_sanitized_emails", {
            "limit": limit,
            "account_email": account_email,
        }))

    async def _call_tool(self, tool_name: str, arguments: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError as exc:
            raise RuntimeError("mcp package is required to call the local email bridge") from exc

        parts = self.command.split()
        params = StdioServerParameters(command=parts[0], args=parts[1:])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)

        if not result.content:
            return []
        raw = getattr(result.content[0], "text", "[]")
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else [parsed]


class KycRagEngine:
    def __init__(
        self,
        db: Optional[DatabaseManager] = None,
        vector_store: Optional[HierarchicalVectorStore] = None,
        email_client: Optional[McpEmailClient] = None,
        llm: Optional[LocalLlamaJsonGenerator] = None,
    ):
        self.db = db or DatabaseManager()
        self.vector_store = vector_store or HierarchicalVectorStore()
        self.email_client = email_client or McpEmailClient()
        self.llm = llm or LocalLlamaJsonGenerator()

    def answer(self, question: str, account_email: Optional[str] = None) -> dict[str, Any]:
        context = self.build_context(question, account_email=account_email)
        system_prompt = (
            "You are Know Your Card, a private local financial offer intelligence assistant. "
            "Use personal sanitized email context only as local evidence. Validate claims against "
            "official card rules when available. If evidence is weak, say so."
        )
        user_prompt = json.dumps({
            "question": question,
            "sanitized_email_context": context.email_context,
            "verified_rule_context": context.rule_context,
        }, ensure_ascii=False)
        return self.llm.generate_json(system_prompt, user_prompt)

    def build_context(self, question: str, account_email: Optional[str] = None) -> KycContext:
        email_context = self._safe_email_context(account_email=account_email)
        rule_context = self._rule_context(question)
        return KycContext(email_context=email_context, rule_context=rule_context)

    def _safe_email_context(self, account_email: Optional[str]) -> list[dict[str, Any]]:
        try:
            return self.email_client.list_recent_sanitized_emails(limit=10, account_email=account_email)
        except Exception as exc:
            return [{"source_type": "mcp_email_bridge", "error": str(exc)}]

    def _rule_context(self, question: str) -> list[dict[str, Any]]:
        results = []
        try:
            for item in self.vector_store.search(question, intent="search", top_k=8):
                results.append({
                    "source_type": "chroma",
                    "label": item.get("sender") or item.get("chunk_id", ""),
                    "text": item.get("body_preview") or item.get("document", ""),
                    "score": item.get("final_score", item.get("similarity")),
                })
        except Exception as exc:
            results.append({"source_type": "chroma", "error": str(exc)})

        try:
            for rule in self.db.get_all_card_network_rules():
                results.append({
                    "source_type": "sqlite_card_rule",
                    "label": rule.card_name,
                    "bank_name": rule.bank_name,
                    "network": rule.network,
                    "category_earnings": rule.category_earnings,
                    "excluded_merchants": rule.excluded_merchants,
                    "accelerated_merchants": rule.accelerated_merchants,
                })
        except Exception as exc:
            results.append({"source_type": "sqlite_card_rule", "error": str(exc)})

        return results[:12]

    def active_offer_badges(self, account_email: Optional[str] = None) -> list[dict[str, str]]:
        offers = []
        for email in self._safe_email_context(account_email=account_email):
            category = self._category_for_text(f"{email.get('subject', '')} {email.get('clean_body', '')}")
            offers.append({
                "title": email.get("subject", "Offer"),
                "bank": email.get("bank_name", ""),
                "category": category,
                "badge_class": self._badge_for_category(category),
            })
        return offers[:8]

    def _category_for_text(self, text: str) -> str:
        lowered = text.lower()
        if any(token in lowered for token in ("restaurant", "dining", "zomato", "swiggy")):
            return "Dining"
        if any(token in lowered for token in ("hotel", "travel", "lounge")):
            return "Travel"
        if "flight" in lowered or "airline" in lowered:
            return "Flights"
        if any(token in lowered for token in ("online", "amazon", "flipkart", "tech")):
            return "Tech"
        if any(token in lowered for token in ("grocery", "groceries", "fuel", "gas")):
            return "Groceries"
        return "Offer"

    def _badge_for_category(self, category: str) -> str:
        return {
            "Dining": "fire-badge",
            "Travel": "water-badge",
            "Flights": "wind-badge",
            "Tech": "lightning-badge",
            "Groceries": "earth-badge",
        }.get(category, "water-badge")
