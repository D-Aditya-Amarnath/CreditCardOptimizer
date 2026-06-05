from fastapi import APIRouter, Depends, Query
from backend.deps import get_current_user
from models import UserProfile
from database import DatabaseManager

router = APIRouter(prefix="/api/user")
db = DatabaseManager()


@router.get("/cards")
async def get_cards(user: UserProfile = Depends(get_current_user)):
    cards = db.get_user_cards(user.id)
    return {
        "cards": [
            {
                "id": c.id,
                "card_name": c.card_name,
                "bank_name": c.bank_name,
                "card_last4": c.card_last4,
                "card_network": c.card_network,
                "is_primary": c.is_primary,
                "added_at": c.added_at.isoformat() if c.added_at else None,
            }
            for c in cards
        ]
    }


@router.post("/cards")
async def add_card(
    card_name: str,
    bank_name: str = None,
    card_last4: str = None,
    card_network: str = None,
    is_primary: bool = False,
    user: UserProfile = Depends(get_current_user)
):
    card = db.add_user_card(
        user_id=user.id,
        card_name=card_name,
        bank_name=bank_name,
        card_last4=card_last4,
        card_network=card_network,
        is_primary=is_primary,
    )
    return {"id": card.id, "card_name": card.card_name}


@router.delete("/cards/{card_id}")
async def remove_card(card_id: int, user: UserProfile = Depends(get_current_user)):
    db.remove_user_card(user.id, card_id)
    return {"status": "ok"}


@router.post("/cards/{card_id}/primary")
async def set_primary_card(card_id: int, user: UserProfile = Depends(get_current_user)):
    db.set_primary_card(user.id, card_id)
    return {"status": "ok"}


@router.get("/profile")
async def get_profile(user: UserProfile = Depends(get_current_user)):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
    }
