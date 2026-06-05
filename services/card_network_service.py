from typing import Optional, List, Tuple
from database import DatabaseManager


class CardNetworkService:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def get_card_rule(self, card_name: str) -> Optional[dict]:
        rule = self.db.get_card_network_rules(card_name)
        if not rule:
            return None
        return {
            "card_name": rule.card_name,
            "network": rule.network,
            "bank_name": rule.bank_name,
            "accepted_merchants": rule.accepted_merchants or [],
            "excluded_merchants": rule.excluded_merchants or [],
            "base_earning_percent": rule.base_earning_percent or 1.0,
            "category_earnings": rule.category_earnings or {},
            "accelerated_merchants": rule.accelerated_merchants or {},
            "max_monthly_points": rule.max_monthly_points,
        }

    def get_all_rules(self) -> List[dict]:
        rules = self.db.get_all_card_network_rules()
        return [
            {
                "id": r.id,
                "card_name": r.card_name,
                "network": r.network,
                "bank_name": r.bank_name,
                "base_earning_percent": r.base_earning_percent,
            }
            for r in rules
        ]

    def is_card_accepted(self, card_rule: dict, merchant_normalized: str) -> bool:
        excluded = card_rule.get("excluded_merchants", [])
        if excluded and merchant_normalized in excluded:
            return False

        accepted = card_rule.get("accepted_merchants", [])
        if accepted and merchant_normalized not in accepted:
            return False

        return True

    def get_earning_rate(self, card_rule: dict, merchant_normalized: str, category: str) -> float:
        base = card_rule.get("base_earning_percent", 1.0)
        category_rates = card_rule.get("category_earnings", {})
        accelerated = card_rule.get("accelerated_merchants", {})

        rate = base

        if category in category_rates:
            rate = category_rates[category]

        if merchant_normalized in accelerated:
            rate += accelerated[merchant_normalized]

        return rate

    def compute_cashback(self, card_rule: dict, merchant_normalized: str,
                         category: str, amount: float) -> dict:
        if not self.is_card_accepted(card_rule, merchant_normalized):
            return {
                "accepted": False,
                "reason": f"{card_rule['card_name']} is not accepted at this merchant",
                "earning_rate": 0,
                "cashback": 0,
            }

        rate = self.get_earning_rate(card_rule, merchant_normalized, category)
        cashback = (rate / 100) * amount

        max_cap = card_rule.get("max_monthly_points")
        if max_cap and cashback > max_cap:
            cashback = max_cap

        return {
            "accepted": True,
            "earning_rate": rate,
            "cashback": round(cashback, 2),
        }

    def recommend_best_card(self, user_cards: List[str], merchant_normalized: str,
                            category: str, amount: float) -> List[dict]:
        results = []

        for card_name in user_cards:
            rule = self.get_card_rule(card_name)
            if not rule:
                results.append({
                    "card_name": card_name,
                    "accepted": True,
                    "earning_rate": 1.0,
                    "cashback": round((1.0 / 100) * amount, 2),
                    "source": "default",
                })
                continue

            cashback_info = self.compute_cashback(rule, merchant_normalized, category, amount)
            results.append({
                "card_name": card_name,
                "network": rule.get("network"),
                "bank_name": rule.get("bank_name"),
                **cashback_info,
                "source": "rule",
            })

        return sorted(results, key=lambda x: x.get("cashback", 0), reverse=True)
