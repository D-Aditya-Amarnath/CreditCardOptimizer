from typing import Optional, Tuple
import re


MERCHANT_ALIASES = {
    "amazon": ["amazon", "amazon.in", "amazn", "amazon.in", "amazon india", "amazon shopping", "amazn.in", "amazonpay"],
    "flipkart": ["flipkart", "flipkart.com", "fk", "fkart", "flipkart.in"],
    "swiggy": ["swiggy", "swiggy instamart", "swiggy genie", "swiggy.in"],
    "zomato": ["zomato", "zomato gold", "zomatolive", "zomato.in"],
    "myntra": ["myntra", "myntra fashion", "myntra.com"],
    "ajio": ["ajio", "ajio.com", "relianceretail"],
    "nykaa": ["nykaa", "nykaa fashion", "nykaa.com"],
    "tatacliq": ["tatacliq", "tata cliq", "cliq"],
    "bigbasket": ["bigbasket", "bbasket", "bigbasket.in", "bbasket.com"],
    "blinkit": ["blinkit", "blinkit.in", "blinkitsg"],
    "zepto": ["zepto", "zepto.in"],
    "dominos": ["dominos", "domino's", "dominos.in", "pizza hut"],
    "pizzahut": ["pizza hut", "pizzahut", "pizza hut.in"],
    "mcdonalds": ["mcdonald", "mcdonalds", "mcd", "mcdonald's"],
    "starbucks": ["starbucks", "starbucks india"],
    "kfc": ["kfc", "kfc india"],
    "subway": ["subway", "subway india"],
    "makemytrip": ["makemytrip", "mmt", "makemytrip.com", "goibibo"],
    "cleartrip": ["cleartrip", "cleartrip.com"],
    "irctc": ["irctc", "irctc.co.in", "irctc ibibo"],
    "uber": ["uber", "uber eats"],
    "ola": ["ola", "ola cabs", "ola food"],
    "redbus": ["redbus", "redbus.in"],
    "airindia": ["airindia", "air india", "airindia.in"],
    "bookmyshow": ["bookmyshow", "bms", "bookmyshow.com"],
    "inox": ["inox", "inox cinemas", "inoxonline"],
    "pvr": ["pvr", "pvr cinemas", "pvr.in"],
    "netmeds": ["netmeds", "netmeds.com", "pharmeasy", "pharmeasy.in"],
    "apollo": ["apollo", "apollo pharmacy", "apollo.in"],
    "1mg": ["1mg", "1mg.com", "one mg"],
    "phonepe": ["phonepe", "phone pe", "phonepe.com"],
    "paytm": ["paytm", "paytm.com", "paytmmall"],
    "gpay": ["gpay", "google pay", "tez"],
    "amazonprime": ["amazon prime", "prime video", "prime"],
    "netflix": ["netflix", "netflix india"],
    "spotify": ["spotify", "spotify india"],
    "disney": ["disney", "disney+hotstar", "hotstar", "jiohotstar"],
    "youtube": ["youtube", "youtube premium", "yt premium"],
    "apple": ["apple", "apple.com", "apple india", "app store"],
    "uberauto": ["uber auto", "uberauto"],
    "rapido": ["rapido", "rapido bike", "rapido.in"],
    "bounce": ["bounce", "bounce.in"],
}


MERCHANT_CATEGORY_MAP = {
    "amazon": "shopping",
    "flipkart": "shopping",
    "myntra": "shopping",
    "ajio": "shopping",
    "nykaa": "shopping",
    "tatacliq": "shopping",
    "bigbasket": "groceries",
    "blinkit": "groceries",
    "zepto": "groceries",
    "swiggy": "food",
    "zomato": "food",
    "dominos": "food",
    "pizzahut": "food",
    "mcdonalds": "food",
    "starbucks": "food",
    "kfc": "food",
    "subway": "food",
    "makemytrip": "travel",
    "cleartrip": "travel",
    "irctc": "travel",
    "redbus": "travel",
    "airindia": "travel",
    "uber": "travel",
    "ola": "travel",
    "uberauto": "travel",
    "rapido": "travel",
    "bounce": "travel",
    "bookmyshow": "entertainment",
    "inox": "entertainment",
    "pvr": "entertainment",
    "netmeds": "healthcare",
    "apollo": "healthcare",
    "1mg": "healthcare",
    "phonepe": "payments",
    "paytm": "payments",
    "gpay": "payments",
    "amazonprime": "subscriptions",
    "netflix": "subscriptions",
    "spotify": "subscriptions",
    "disney": "subscriptions",
    "youtube": "subscriptions",
    "apple": "subscriptions",
}


class MerchantNormalizer:
    def __init__(self, db_manager=None):
        self.db = db_manager

    def normalize(self, raw_name: str) -> Tuple[str, str]:
        if not raw_name:
            return "unknown", "other"

        raw_lower = raw_name.lower().strip()

        if self.db:
            cached = self.db.get_merchant_normalization(raw_lower)
            if cached:
                return cached.normalized_name, cached.category or "other"

        for canonical, aliases in MERCHANT_ALIASES.items():
            if raw_lower == canonical or raw_lower in aliases:
                category = MERCHANT_CATEGORY_MAP.get(canonical, "other")
                self._cache_result(raw_lower, canonical, category, aliases)
                return canonical, category

            for alias in aliases:
                if alias in raw_lower or raw_lower in alias:
                    category = MERCHANT_CATEGORY_MAP.get(canonical, "other")
                    self._cache_result(raw_lower, canonical, category, aliases)
                    return canonical, category

        category = self._infer_category(raw_lower)
        return raw_lower, category

    def _infer_category(self, text: str) -> str:
        category_keywords = {
            "food": ["restaurant", "cafe", "pizza", "burger", "food", "meal", "dining", "eatery"],
            "shopping": ["store", "shop", "mall", "retail", "fashion", "clothing", "shoes"],
            "travel": ["travel", "flight", "hotel", "booking", "cab", "taxi", "bus", "train"],
            "groceries": ["grocery", "supermarket", "mart", "vegetable", "fruit"],
            "healthcare": ["pharmacy", "medicine", "doctor", "hospital", "clinic", "health"],
            "entertainment": ["movie", "cinema", "theatre", "ticket", "game", "entertainment"],
            "payments": ["payment", "recharge", "bill", "utility"],
            "subscriptions": ["subscription", "membership", "premium", "streaming"],
        }

        for cat, keywords in category_keywords.items():
            if any(kw in text for kw in keywords):
                return cat

        return "other"

    def _cache_result(self, raw_name: str, normalized: str, category: str, aliases: list):
        if self.db:
            self.db.save_merchant_normalization(raw_name, normalized, category, aliases)
