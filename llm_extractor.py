import os
import json
from openai import OpenAI
from typing import Optional
from dotenv import load_dotenv

from models import OfferExtraction, EmailPayload

load_dotenv()

class OfferExtractor:
    """Object-Oriented handler for communicating with LMStudio and extracting structured offers."""
    
    SYSTEM_PROMPT = """
You are an AI system called **Financial Offer Intelligence Agent**.
Your purpose is to automatically analyze promotional emails from banks, NBFCs, and credit card companies in order to detect financial offers, structure them into usable data, validate their validity, and maximize savings during purchases.

When processing emails, follow this workflow:
1. Email Filtering: 
Determine whether the email originates from a financial institution and contains a promotional offer.
Ignore emails related to: OTP, statements, payment confirmations, KYC reminders, transaction alerts.
Only proceed if the email contains a promotion, cashback, reward, or discount offer. If it does not, return all nulls.

2. Offer Extraction:
Extract fields including: merchant, card_name, offer_type (cashback, discount, reward points), discount_percent, min_spend, max_cashback, valid_from, valid_until.
If a field is not available, return null.
Normalize merchant names when possible (e.g. Amazon, Amazon.in -> amazon).

OUTPUT FORMAT:
Always return valid structured JSON matching the requested schema. Do not include markdown formatting or explanations outside the JSON block.
"""

    def __init__(self, base_url: str = None, api_key: str = None):
        self.base_url = base_url or os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
        self.api_key = api_key or os.getenv("LMSTUDIO_API_KEY", "lm-studio")
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        
    def extract_from_payload(self, email_payload: EmailPayload) -> Optional[OfferExtraction]:
        """Sends the email content to LMStudio to extract structured offer data."""
        prompt = f"Date of Email: {email_payload.date_received}\nSubject: {email_payload.subject}\n\nEmail Body:\n{email_payload.body_text[:2000]}"
        
        try:
            response = self.client.chat.completions.create(
                model="local-model",
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0
            )
            
            result_content = response.choices[0].message.content
            if not result_content: return None
            
            # Strip markdown code fences if the LLM wraps output in ```json ... ```
            import re
            result_content = re.sub(r'^```(?:json)?\s*', '', result_content.strip())
            result_content = re.sub(r'\s*```$', '', result_content.strip())
            
            parsed_json = json.loads(result_content)
            
            # Handle nested structures: {"offer": {...}} or {"data": {...}}
            if isinstance(parsed_json, dict):
                # If the LLM wrapped the offer inside a key, try to unwrap it
                if 'offer' in parsed_json and isinstance(parsed_json['offer'], dict):
                    parsed_json = parsed_json['offer']
                elif 'data' in parsed_json and isinstance(parsed_json['data'], dict):
                    parsed_json = parsed_json['data']
                # If top-level has no 'merchant' key but has nested structure, skip
                expected_keys = {'merchant', 'card_name', 'offer_type'}
                if not any(k in parsed_json for k in expected_keys):
                    return None
            
            return OfferExtraction(**parsed_json)
            
        except Exception as e:
            print(f"Error extracting offer via LLM: {e}")
            return None
