import os
import json
import re
import hashlib
from typing import List, Optional
from datetime import datetime
from openai import OpenAI
from models import OfferModel, OfferExtraction


class StructuredExtractor:
    def __init__(self):
        self._llm_client = None

    @property
    def llm_client(self):
        if self._llm_client is None:
            base_url = os.getenv("LMSTUDIO_BASE_URL", os.getenv("OLLAMA_BASE_URL", "http://localhost:1234/v1"))
            api_key = os.getenv("LMSTUDIO_API_KEY", os.getenv("OLLAMA_API_KEY", "lm-studio"))
            self._llm_client = OpenAI(base_url=base_url, api_key=api_key)
        return self._llm_client

    def extract_from_text(self, body_text: str, email_id: str,
                          sender: str, account_email: str) -> List[OfferModel]:
        if not body_text or len(body_text.strip()) < 50:
            return []

        prompt = f"""Extract ALL credit card offers from the text below.
For each offer, extract: merchant, card_name, offer_type, discount_percent,
min_spend, max_cashback, valid_from, valid_until.

Return a JSON array of offers. Example:
[{{"merchant": "amazon", "card_name": "HDFC Bank", "offer_type": "cashback",
"discount_percent": 10, "min_spend": 3000, "max_cashback": 1500,
"valid_from": "2026-03-01", "valid_until": "2026-03-31"}}]

If no offers found, return [].
Text:
{body_text[:4000]}
"""

        try:
            response = self.llm_client.chat.completions.create(
                model="llama3.2:3b-instruct",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=500,
            )

            raw = response.choices[0].message.content or ""
            json_str = self._extract_json(raw)

            if not json_str:
                return []

            offers_data = json.loads(json_str)
            if not isinstance(offers_data, list):
                return []

            offers = []
            for o in offers_data:
                try:
                    offer = self._to_offer_model(o, email_id, sender, account_email)
                    if offer:
                        offers.append(offer)
                except Exception:
                    continue

            return offers

        except Exception:
            return []

    def _extract_json(self, text: str) -> str:
        text = text.strip()
        if text.startswith("["):
            start, end = 0, len(text)
        else:
            start = text.find("[")
            end = text.rfind("]") + 1

        if start == -1:
            start = text.find("{")
            end = text.rfind("}") + 1

        if start == -1:
            return ""

        return text[start:end]

    def _to_offer_model(self, offer_dict: dict, email_id: str,
                         sender: str, account_email: str) -> Optional[OfferModel]:
        merchant = (offer_dict.get("merchant") or "unknown").lower().strip()
        card_name = offer_dict.get("card_name") or sender
        discount = offer_dict.get("discount_percent")

        hash_input = f"{merchant}{card_name}{discount}"
        unique_hash = hashlib.sha256(hash_input.encode()).hexdigest()

        valid_from = self._parse_date(offer_dict.get("valid_from"))
        valid_until = self._parse_date(offer_dict.get("valid_until"))

        return OfferModel(
            merchant=merchant,
            card_name=card_name,
            offer_type=offer_dict.get("offer_type", "cashback") or "cashback",
            discount_percent=discount,
            min_spend=offer_dict.get("min_spend"),
            max_cashback=offer_dict.get("max_cashback"),
            valid_from=valid_from,
            valid_until=valid_until,
            source_email_id=email_id,
            account_email=account_email,
            unique_hash=unique_hash,
        )

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        if not date_str:
            return None
        for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d %B %Y", "%B %d, %Y"]:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        return None
