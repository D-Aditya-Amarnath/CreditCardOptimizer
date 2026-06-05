from fastapi import APIRouter, Depends, Query
from agent4_gradio_rag.backend.deps import get_current_user
from shared_core.models import UserProfile
from shared_core.database import DatabaseManager
from shared_core.vector_store import HierarchicalVectorStore
from shared_core.card_network_service import CardNetworkService

router = APIRouter(prefix="/api/offers")
db = DatabaseManager()
vector_store = HierarchicalVectorStore()
card_network_service = CardNetworkService(db)


@router.get("")
async def list_offers(
    merchant: str = None,
    limit: int = Query(50, ge=1, le=200),
    user: UserProfile = Depends(get_current_user)
):
    user_cards = [c.card_name for c in db.get_user_cards(user.id)]

    if merchant:
        offers = db.get_offers_by_merchant(merchant, user_cards=user_cards)
    else:
        offers = db.get_all_offers(user_cards=user_cards, limit=limit)

    return {
        "count": len(offers),
        "offers": [
            {
                "id": o.id,
                "merchant": o.merchant,
                "card_name": o.card_name,
                "offer_type": o.offer_type,
                "discount_percent": o.discount_percent,
                "min_spend": o.min_spend,
                "max_cashback": o.max_cashback,
                "valid_from": o.valid_from.isoformat() if o.valid_from else None,
                "valid_until": o.valid_until.isoformat() if o.valid_until else None,
                "source_email_id": o.source_email_id,
            }
            for o in offers
        ]
    }


@router.get("/compare")
async def compare_offers(
    merchant: str,
    amount: float = Query(..., gt=0),
    category: str = None,
    user: UserProfile = Depends(get_current_user)
):
    user_cards = [c.card_name for c in db.get_user_cards(user.id)]
    offers = db.compare_offers(merchant, amount, user_cards=user_cards)

    savings = []
    for o in offers:
        cashback = 0
        if o.discount_percent and o.discount_percent > 0:
            cashback = min(
                (o.discount_percent / 100) * amount,
                o.max_cashback or float('inf')
            )
        savings.append({
            "id": o.id,
            "merchant": o.merchant,
            "card_name": o.card_name,
            "discount_percent": o.discount_percent,
            "min_spend": o.min_spend,
            "max_cashback": o.max_cashback,
            "estimated_cashback": round(cashback, 2) if cashback else 0,
            "valid_until": o.valid_until.isoformat() if o.valid_until else None,
            "source_email_id": o.source_email_id,
        })

    best_card_recs = card_network_service.recommend_best_card(
        user_cards, merchant, category or "other", amount
    )

    savings.sort(key=lambda x: x["estimated_cashback"], reverse=True)

    return {
        "merchant": merchant,
        "amount": amount,
        "category": category,
        "offers": savings,
        "best_offer": savings[0] if savings else None,
        "card_recommendations": best_card_recs,
    }


@router.get("/search")
async def search_offers(
    q: str,
    user: UserProfile = Depends(get_current_user)
):
    user_cards = [c.card_name for c in db.get_user_cards(user.id)]
    results = vector_store.search(q, intent="recommend", top_k=10)
    return {"results": results, "count": len(results)}
