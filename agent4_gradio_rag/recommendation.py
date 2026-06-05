from datetime import datetime
from shared_core.database import DatabaseManager
from shared_core.models import OfferModel

class RecommendationEngine:
    """OOP Component handling evaluation logic of card offers based on thresholds and active dates."""
    
    def __init__(self, db_manager: DatabaseManager):
         self.db = db_manager
         
    def get_best_offer(self, merchant_name: str, purchase_amount: float) -> list[tuple[OfferModel, float]]:
        """
        6. Recommendation Logic
        Finds the active offer for the merchant that provides the highest effective discount.
        Returns a sorted list of tuples: (Offer, Effective Discount Savings)
        """
        merchant_normalized = merchant_name.lower().strip()
        active_offers = self.db.get_all_active_offers_for_merchant(merchant_normalized)
        current_date = datetime.now()
        
        valid_offers = []
        
        for offer in active_offers:
            # Check date boundaries
            if offer.valid_until and offer.valid_until < current_date: continue
            # Check spend boundaries
            if offer.min_spend and purchase_amount < offer.min_spend: continue
                
            # Calculate effective discount
            effective_discount = 0.0
            if offer.discount_percent:
                effective_discount = purchase_amount * (offer.discount_percent / 100)
                if offer.max_cashback and effective_discount > offer.max_cashback:
                    effective_discount = offer.max_cashback
                    
            effective_discount = round(effective_discount, 2)
            valid_offers.append((offer, effective_discount))
            
        if not valid_offers:
            return []
            
        return sorted(valid_offers, key=lambda x: x[1], reverse=True)
