from typing import List, Dict, Any
from datetime import datetime, timedelta
from database import DatabaseManager
from models import TransactionModel


class SpendAnalyzer:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def compute_patterns(self, profile_id: int, days: int = 90) -> Dict[str, Any]:
        transactions = self.db.get_transactions_by_profile(profile_id, days=days)
        debit_txns = [t for t in transactions if t.transaction_type == 'debit']

        return {
            "by_category": self.category_breakdown(debit_txns),
            "monthly": self.db.get_monthly_spend(profile_id, months=3),
            "frequency": self.db.get_transaction_frequency(profile_id, days=days),
            "avg_per_category": self.average_by_category(debit_txns),
            "top_merchants": self.db.get_top_merchants(profile_id, days=days, limit=10),
            "trend": self.compute_trend(debit_txns),
            "total_90d": sum(t.amount or 0 for t in debit_txns),
            "avg_monthly": self.avg_monthly(debit_txns, days=days),
            "category_count": self.category_count(debit_txns),
        }

    def category_breakdown(self, transactions: List[TransactionModel]) -> Dict[str, float]:
        result = {}
        for t in transactions:
            cat = t.category or 'other'
            result[cat] = result.get(cat, 0) + (t.amount or 0)
        return dict(sorted(result.items(), key=lambda x: x[1], reverse=True))

    def average_by_category(self, transactions: List[TransactionModel]) -> Dict[str, float]:
        cat_totals = {}
        cat_counts = {}
        for t in transactions:
            cat = t.category or 'other'
            cat_totals[cat] = cat_totals.get(cat, 0) + (t.amount or 0)
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        return {
            cat: round(cat_totals[cat] / cat_counts[cat], 2)
            for cat in cat_totals
        }

    def category_count(self, transactions: List[TransactionModel]) -> Dict[str, int]:
        result = {}
        for t in transactions:
            cat = t.category or 'other'
            result[cat] = result.get(cat, 0) + 1
        return dict(sorted(result.items(), key=lambda x: x[1], reverse=True))

    def avg_monthly(self, transactions: List[TransactionModel], days: int = 90) -> float:
        if not transactions:
            return 0.0
        total = sum(t.amount or 0 for t in transactions)
        months = days / 30.0
        return round(total / months, 2)

    def compute_trend(self, transactions: List[TransactionModel]) -> str:
        if len(transactions) < 10:
            return "insufficient_data"

        cutoff_30d = datetime.utcnow() - timedelta(days=30)
        cutoff_60d = datetime.utcnow() - timedelta(days=60)

        recent = [t for t in transactions if t.transaction_date and t.transaction_date >= cutoff_30d]
        older = [t for t in transactions if t.transaction_date and cutoff_60d <= t.transaction_date < cutoff_30d]

        if not recent or not older:
            return "insufficient_data"

        recent_avg = sum(t.amount or 0 for t in recent) / max(len(recent), 1)
        older_avg = sum(t.amount or 0 for t in older) / max(len(older), 1)

        if older_avg == 0:
            return "increasing"

        change = ((recent_avg - older_avg) / older_avg) * 100

        if change > 15:
            return "increasing"
        elif change < -15:
            return "decreasing"
        return "stable"

    def get_category_emoji(self, category: str) -> str:
        emoji_map = {
            "food": "🍔",
            "shopping": "🛒",
            "travel": "✈️",
            "groceries": "🛒",
            "healthcare": "💊",
            "entertainment": "🎬",
            "payments": "💳",
            "subscriptions": "📱",
            "fuel": "⛽",
            "other": "💰",
        }
        return emoji_map.get(category, "💰")

    def get_category_insights(self, patterns: Dict) -> List[str]:
        insights = []
        by_cat = patterns.get("by_category", {})

        if not by_cat:
            return ["No transaction data available yet."]

        top_cat = max(by_cat.items(), key=lambda x: x[1])
        total = sum(by_cat.values())
        pct = (top_cat[1] / total * 100) if total > 0 else 0

        insights.append(
            f"You spend most on **{top_cat[0].title()}** — ₹{top_cat[1]:,.0f} ({pct:.0f}% of total)"
        )

        trend = patterns.get("trend", "stable")
        if trend == "increasing":
            insights.append("📈 Your spending is increasing over time")
        elif trend == "decreasing":
            insights.append("📉 Your spending has decreased recently")
        else:
            insights.append("➡️ Your spending is stable")

        frequency = patterns.get("frequency", {})
        if frequency.get("per_month"):
            insights.append(
                f"💳 You make ~{frequency['per_month']:.0f} transactions per month"
            )

        return insights
