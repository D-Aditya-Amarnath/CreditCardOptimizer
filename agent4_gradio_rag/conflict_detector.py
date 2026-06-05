import re
from typing import List, Dict, Any, Optional
from collections import defaultdict


class ConflictDetector:
    def detect(self, results: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        conflicts = []
        by_merchant = defaultdict(list)

        for r in results:
            text = r.get("body_preview", "") or r.get("document", "")
            merchants = r.get("merchants", [])
            if not merchants:
                merchants = self._extract_merchants(text)

            for merchant in merchants:
                by_merchant[merchant.lower()].append({
                    **r,
                    "merchant": merchant,
                    "discount": r.get("discount_percent") or self._extract_discount(text),
                    "min_spend": r.get("min_spend") or self._extract_min_spend(text),
                    "expiry": r.get("expiry_date") or self._extract_date(text),
                })

        for merchant, offers in by_merchant.items():
            if len(offers) < 2:
                continue

            discounts = set(o["discount"] for o in offers if o["discount"] is not None)
            if len(discounts) > 1:
                conflicts.append({
                    "type": "discount_conflict",
                    "merchant": merchant,
                    "description": f"Multiple cashback rates: {discounts}",
                    "items": [
                        {
                            "sender": o.get("sender", ""),
                            "date": o.get("date_received", ""),
                            "discount": o.get("discount"),
                            "source": o.get("email_id", ""),
                        }
                        for o in offers
                    ]
                })

            expiries = set(o["expiry"] for o in offers if o.get("expiry"))
            if len(exiries) > 1:
                conflicts.append({
                    "type": "expiry_conflict",
                    "merchant": merchant,
                    "description": f"Multiple expiry dates: {exiries}",
                    "items": [
                        {
                            "sender": o.get("sender", ""),
                            "date": o.get("date_received", ""),
                            "expiry": o.get("expiry"),
                            "source": o.get("email_id", ""),
                        }
                        for o in offers
                    ]
                })

            by_card = defaultdict(list)
            for o in offers:
                for card in o.get("cards", []):
                    by_card[card.lower()].append(o)

            for card, card_offers in by_card.items():
                if len(card_offers) >= 2:
                    card_discounts = set(o["discount"] for o in card_offers if o["discount"])
                    if len(card_discounts) > 1:
                        sorted_offers = sorted(
                            card_offers,
                            key=lambda x: x.get("date_received", ""),
                            reverse=True
                        )
                        conflicts.append({
                            "type": "offer_update",
                            "merchant": merchant,
                            "card": card,
                            "description": f"Terms updated for {card} on {merchant}",
                            "current": sorted_offers[0],
                            "previous": sorted_offers[1] if len(sorted_offers) > 1 else None,
                        })

        return conflicts

    def _extract_merchants(self, text: str) -> List[str]:
        merchants = {
            "amazon", "myntra", "swiggy", "zomato", "flipkart",
            "bigbasket", "bookmyshow", "makemytrip", "dominos",
            "uber", "ola", "netmeds", "ajio", "nykaa", "tata cliq",
        }
        text_lower = text.lower()
        return [m for m in merchants if m in text_lower]

    def _extract_discount(self, text: str) -> Optional[float]:
        patterns = [
            r'(\d+)%\s*(?:cashback|off|discount)',
            r'flat\s+(\d+)%',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1))
                except (ValueError, IndexError):
                    pass
        return None

    def _extract_min_spend(self, text: str) -> Optional[float]:
        patterns = [
            r'(?:min|minimum)\s*(?:spend)[:\s]*₹?\s*([\d,]+)',
            r'above\s*₹?\s*([\d,]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1).replace(',', ''))
                except (ValueError, IndexError):
                    pass
        return None

    def _extract_date(self, text: str) -> Optional[str]:
        patterns = [
            r'(?:valid|expires|till|until)\s+(?:till|until)?\s*(\d{1,2}\s+\w+\s+\d{4})',
            r'(\d{1,2}\s+\w+\s+\d{4})',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None
