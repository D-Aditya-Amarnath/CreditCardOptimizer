from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from backend.deps import get_current_user
from database import db

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("/")
async def list_transactions(
    profile_id: Optional[int] = None,
    days: int = 90,
    limit: int = 100,
    offset: int = 0,
    current_user=Depends(get_current_user)
):
    if profile_id is None:
        profile_id = current_user.id
    
    transactions = db.get_transactions_paginated(profile_id, limit=limit, offset=offset)
    
    return {
        "transactions": [
            {
                "id": t.id,
                "email_id": t.email_id,
                "merchant_raw": t.merchant_raw,
                "merchant_normalized": t.merchant_normalized,
                "amount": t.amount,
                "transaction_date": t.transaction_date.isoformat() if t.transaction_date else None,
                "card_last4": t.card_last4,
                "card_name": t.card_name,
                "bank_name": t.bank_name,
                "transaction_type": t.transaction_type,
                "category": t.category,
                "account_email": t.account_email,
            }
            for t in transactions
        ],
        "total": db.count_transactions(profile_id)
    }


@router.get("/spend-pattern")
async def get_spend_pattern(
    profile_id: Optional[int] = None,
    days: int = 90,
    current_user=Depends(get_current_user)
):
    if profile_id is None:
        profile_id = current_user.id
    
    by_category = db.get_spend_by_category(profile_id, days=days)
    monthly = db.get_monthly_spend(profile_id, months=3)
    frequency = db.get_transaction_frequency(profile_id, days=days)
    top_merchants = db.get_top_merchants(profile_id, days=days, limit=10)
    
    total_90d = sum(by_category.values())
    avg_monthly = total_90d / (days / 30) if days > 0 else 0
    
    trend = "stable"
    if len(monthly) >= 2:
        months = list(monthly.values())
        if months[0] > months[1] * 1.1:
            trend = "increasing"
        elif months[0] < months[1] * 0.9:
            trend = "decreasing"
    
    avg_per_category = {
        cat: round(amount / max(frequency["total_transactions"], 1) * len(by_category), 2)
        for cat, amount in by_category.items()
    }
    
    return {
        "by_category": by_category,
        "monthly": monthly,
        "frequency": frequency,
        "avg_per_category": avg_per_category,
        "top_merchants": top_merchants,
        "trend": trend,
        "total_90d": round(total_90d, 2),
        "avg_monthly": round(avg_monthly, 2)
    }


@router.get("/categories")
async def get_categories(
    profile_id: Optional[int] = None,
    current_user=Depends(get_current_user)
):
    if profile_id is None:
        profile_id = current_user.id
    
    from database import db as _db
    by_category = _db.get_spend_by_category(profile_id, days=90)
    
    category_emojis = {
        "food": "🍽️",
        "dining": "🍽️",
        "groceries": "🛒",
        "shopping": "🛍️",
        "travel": "✈️",
        "fuel": "⛽",
        "utilities": "💡",
        "entertainment": "🎬",
        "healthcare": "🏥",
        "education": "📚",
        "other": "📦",
    }
    
    return {
        "categories": [
            {
                "name": cat,
                "emoji": category_emojis.get(cat.lower(), "📦"),
                "amount": round(amount, 2),
            }
            for cat, amount in by_category.items()
        ]
    }
