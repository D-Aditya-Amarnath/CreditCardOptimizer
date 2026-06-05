from typing import List, Dict, Any


class ContextCompressor:
    def compress(self, results: List[Dict[str, Any]], query: str,
                 intent: str, max_chars: int = 8000) -> str:
        if intent == "recommend":
            return self._format_for_recommend(results, query)

        formatted = []
        for i, r in enumerate(results):
            if i < 3:
                text = r.get("body_preview", r.get("document", ""))[:600]
            elif i < 7:
                text = r.get("body_preview", r.get("document", ""))[:300]
            else:
                text = r.get("body_preview", r.get("document", ""))[:150]

            formatted.append(
                f"[{i + 1}] {r.get('sender', 'Unknown')} | {r.get('date_received', '')[:10]}\n"
                f"{text}"
            )

        combined = "\n\n".join(formatted)

        if len(combined) > max_chars:
            combined = combined[:max_chars] + "\n\n[... additional results truncated ...]"

        return combined

    def _format_for_recommend(self, results: List[Dict], query: str) -> str:
        lines = []
        for r in results:
            meta = {
                "discount_percent": r.get("discount_percent"),
                "min_spend": r.get("min_spend"),
                "max_cashback": r.get("max_cashback"),
                "expiry_date": r.get("expiry_date"),
                "offer_type": r.get("offer_type"),
            }

            lines.append(
                f"From: {r.get('sender', 'Unknown')} ({r.get('date_received', '')[:10]})\n"
                f"Offer: {meta.get('discount_percent', 'N/A')}% "
                f"{meta.get('offer_type', 'cashback')}\n"
                f"Min spend: ₹{meta.get('min_spend', 'any'):,.0f}" if meta.get("min_spend") else
                "Min spend: any\n"
                f"Max cap: ₹{meta.get('max_cashback', 'N/A'):,.0f}" if meta.get("max_cashback") else
                "Max cap: uncapped\n"
                f"Valid until: {meta.get('expiry_date', 'N/A')}\n"
                f"Details: {r.get('body_preview', r.get('document', ''))[:400]}"
            )

        return "\n---\n".join(lines)
