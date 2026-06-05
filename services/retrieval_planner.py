import re
from typing import List, Dict, Any, Optional


class RetrievalPlanner:
    def plan(self, query: str, intent: str, conversation_history: List = None) -> Dict[str, Any]:
        query_lower = query.lower()
        is_followup = self._is_followup(query_lower, conversation_history)
        complexity = self._assess_complexity(query_lower)
        has_amount = self._extract_amount(query_lower)
        num_entities = self._count_entities(query_lower)

        if is_followup and conversation_history:
            return {
                "mode": "expand",
                "query": self._extract_new_terms(query_lower, conversation_history),
                "top_k": 5,
                "expand_from": conversation_history[-1].get("retrieved_ids", []),
                "intent": intent,
            }

        if complexity == "high" or num_entities >= 3:
            return {
                "mode": "multi_stage",
                "query": query,
                "top_k": 15,
                "intent": intent,
            }

        if has_amount:
            return {
                "mode": "filtered",
                "query": query,
                "filters": {"min_spend_lte": has_amount},
                "top_k": 10,
                "intent": intent,
            }

        top_k = self._adaptive_top_k(intent, query_lower)
        return {
            "mode": "simple",
            "query": query,
            "top_k": top_k,
            "intent": intent,
        }

    def _is_followup(self, query: str, history: List = None) -> bool:
        if not history:
            return False
        followup_signals = ["and", "also", "what about", "with", "but", "same", "too", "="]
        return any(signal in query for signal in followup_signals)

    def _assess_complexity(self, query: str) -> str:
        tokens = query.split()
        if len(tokens) <= 3 and not any(c in query for c in ["and", "or", "₹", "%"]):
            return "low"
        if len(tokens) >= 10 or query.count("and") >= 2:
            return "high"
        return "medium"

    def _extract_amount(self, query: str) -> Optional[float]:
        match = re.search(r'₹?\s*([\d,]+)', query)
        if match:
            try:
                return float(match.group(1).replace(',', ''))
            except ValueError:
                pass
        match = re.search(r'(\d+)%', query)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
        return None

    def _count_entities(self, query: str) -> int:
        entities = {
            "hdfc", "sbi", "icici", "axis", "kotak", "yes", "indusind",
            "amazon", "myntra", "swiggy", "zomato", "flipkart",
            "bookmyshow", "makemytrip",
        }
        return sum(1 for e in entities if e in query)

    def _extract_new_terms(self, query: str, history: List) -> str:
        return query

    def _adaptive_top_k(self, intent: str, query: str) -> int:
        if intent == "recommend":
            return 15
        if intent == "list_recent":
            return 5
        if len(query.split()) <= 2:
            return 10
        return 5
