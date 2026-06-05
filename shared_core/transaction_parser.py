import re
from datetime import datetime
from typing import Optional, List
from shared_core.models import TransactionPayload
from shared_core.merchant_normalizer import MerchantNormalizer


BANK_TRANSACTION_PATTERNS = {
    "hdfc": {
        "sender_domains": ["hdfcbank.com", "hdfc.bank.in"],
        "amount": [r'₹\s*([\d,]+\.?\d*)', r'rs\.?\s*([\d,]+\.?\d*)', r'([\d,]+\.?\d*)\s*INR'],
        "merchant": [
            r'(?:at|on|to)\s+([A-Za-z][A-Za-z\s&\-]+?)(?:\s+on|\s+for|\s+₹|$)',
            r'transaction at\s+([A-Za-z][A-Za-z\s&\-]+)',
        ],
        "card_last4": [r'\*{2,}(\d{4})', r'\.(\d{4})\s*$', r'card\s*(\d{4})'],
        "date": [r'(\d{1,2}\s+\w+\s+\d{4})', r'(\d{4}-\d{2}-\d{2})'],
    },
    "sbi": {
        "sender_domains": ["sbicard.com", "sbi.co.in", "sbi.bank.in"],
        "amount": [r'₹\s*([\d,]+\.?\d*)', r'rs\.?\s*([\d,]+\.?\d*)'],
        "merchant": [r'at\s+([A-Za-z][A-Za-z\s&\-]+?)(?:\s+on|\s+for|\s+₹|$)'],
        "card_last4": [r'\*{2,}(\d{4})', r'ending\s+(\d{4})'],
        "date": [r'(\d{1,2}\s+\w+\s+\d{4})'],
    },
    "icici": {
        "sender_domains": ["icicibank.com", "icici.bank.in"],
        "amount": [r'₹\s*([\d,]+\.?\d*)', r'([\d,]+\.?\d*)\s*INR'],
        "merchant": [r'on\s+([A-Za-z][A-Za-z\s&\-]+?)(?:\s+on|\s+for|\s+₹|$)'],
        "card_last4": [r'\*{2,}(\d{4})'],
        "date": [r'(\d{1,2}\s+\w+\s+\d{4})'],
    },
    "axis": {
        "sender_domains": ["axisbank.com", "axis.bank.in"],
        "amount": [r'₹\s*([\d,]+\.?\d*)', r'rs\.?\s*([\d,]+\.?\d*)'],
        "merchant": [r'at\s+([A-Za-z][A-Za-z\s&\-]+?)(?:\s+on|\s+for|\s+₹|$)'],
        "card_last4": [r'\*{2,}(\d{4})'],
        "date": [r'(\d{1,2}\s+\w+\s+\d{4})'],
    },
    "kotak": {
        "sender_domains": ["kotak.com", "kotakbank.in"],
        "amount": [r'₹\s*([\d,]+\.?\d*)'],
        "merchant": [r'at\s+([A-Za-z][A-Za-z\s&\-]+?)(?:\s+on|\s+for|\s+₹|$)'],
        "card_last4": [r'\*{2,}(\d{4})'],
        "date": [r'(\d{1,2}\s+\w+\s+\d{4})'],
    },
}

TRANSACTION_INDICATORS = [
    r"transaction alert",
    r"txn\s+alert",
    r"spent\s*(?:rs|inr|₹)",
    r"debited\s*(?:rs|inr|₹)",
    r"₹\s*[\d,]+\.?\d*\s*(?:spent|debit|paid)",
    r"payment\s*(?:of|made)\s*(?:rs|inr|₹)",
    r"purchase\s*(?:of|made)\s*(?:rs|inr|₹)",
    r"rs\.?\s*[\d,]+\.?\d*\s*(?:spent|debit)",
    r"card\s+payment",
    r"upi\s+(?:debit|payment|transfer)",
    r"(?:neft|imps|rtgs)\s+debit",
    r"nach\s+mandate",
]

PROMOTIONAL_INDICATORS = [
    r"cashback",
    r"discount",
    r"offer",
    r"reward",
    r"flat\s+\d+%\s*(?:off|cashback)",
    r"₹\s*[\d,]+\s*(?:cashback|off|discount)",
    r"bonus\s+points",
    r"limited\s+time",
    r"exclusive\s+offer",
]


class TransactionParser:
    def __init__(self, merchant_normalizer: MerchantNormalizer = None):
        self.merchant_normalizer = merchant_normalizer or MerchantNormalizer()

    def classify_email_type(self, sender: str, subject: str, body_text: str) -> str:
        combined = f"{subject} {body_text}".lower()

        promo_score = sum(1 for p in PROMOTIONAL_INDICATORS if re.search(p, combined))
        txn_score = sum(1 for p in TRANSACTION_INDICATORS if re.search(p, combined))

        if txn_score > promo_score:
            return "transactional"
        elif promo_score > txn_score:
            return "promotional"
        return "promotional"

    def parse_transaction(self, sender: str, subject: str, body_text: str,
                          email_id: str, account_email: str, date_received: datetime) -> Optional[TransactionPayload]:
        if not self.is_transaction_email(sender, subject, body_text):
            return None

        bank = self._detect_bank(sender)
        patterns = BANK_TRANSACTION_PATTERNS.get(bank, {})

        amount = self._extract_field(body_text, patterns.get("amount", []))
        if amount:
            amount = float(amount.replace(',', ''))
            if amount <= 0:
                return None

        merchant_raw = self._extract_merchant(body_text, patterns.get("merchant", []), subject)
        if merchant_raw:
            merchant_normalized, category = self.merchant_normalizer.normalize(merchant_raw)
        else:
            merchant_normalized, category = "unknown", "other"
            merchant_raw = subject[:50]

        card_last4 = self._extract_field(body_text, patterns.get("card_last4", []))
        card_name = self._extract_card_name(body_text, bank)
        bank_name = self._detect_bank_name(bank)

        tx_date = self._extract_date(body_text, patterns.get("date", []), date_received)

        return TransactionPayload(
            email_id=email_id,
            account_email=account_email,
            merchant_raw=merchant_raw or subject[:50],
            merchant_normalized=merchant_normalized,
            amount=amount,
            transaction_date=tx_date,
            card_last4=card_last4,
            card_name=card_name,
            bank_name=bank_name,
            transaction_type="debit",
            category=category,
        )

    def is_transaction_email(self, sender: str, subject: str, body_text: str) -> bool:
        combined = f"{subject} {body_text}".lower()
        score = sum(1 for p in TRANSACTION_INDICATORS if re.search(p, combined))
        return score >= 1

    def _detect_bank(self, sender: str) -> Optional[str]:
        sender_lower = sender.lower()
        for bank, patterns in BANK_TRANSACTION_PATTERNS.items():
            for domain in patterns.get("sender_domains", []):
                if domain in sender_lower:
                    return bank
        return None

    def _detect_bank_name(self, bank: str) -> str:
        names = {
            "hdfc": "HDFC Bank", "sbi": "SBI Card", "icici": "ICICI Bank",
            "axis": "Axis Bank", "kotak": "Kotak Bank", "yes": "Yes Bank",
            "indusind": "IndusInd Bank", "idfc": "IDFC First Bank",
            "rbl": "RBL Bank", "federal": "Federal Bank",
        }
        return names.get(bank, bank.title() if bank else "Unknown")

    def _extract_field(self, text: str, patterns: List[str]) -> Optional[str]:
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _extract_merchant(self, text: str, patterns: List[str], subject: str) -> Optional[str]:
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                merchant = match.group(1).strip()
                if len(merchant) > 2 and len(merchant) < 60:
                    return merchant

        subject_clean = re.sub(r'^(?:transaction alert|txn|debit|spent|payment)\s*:?\s*', '', subject, flags=re.IGNORECASE)
        subject_clean = re.sub(r'₹[\d,\.]+\s*(?:spent|debit|paid)?\s*', '', subject_clean, flags=re.IGNORECASE)
        subject_clean = re.sub(r'rs\.?\s*[\d,\.]+\s*(?:spent|debit|paid)?\s*', '', subject_clean, flags=re.IGNORECASE)
        subject_clean = subject_clean.strip(' -:')
        if subject_clean and len(subject_clean) > 2:
            return subject_clean[:60]

        return None

    def _extract_card_name(self, text: str, bank: str) -> Optional[str]:
        card_patterns = [
            r'(hdfc\s+\w+(?:\s+\w+)?)',
            r'(sbi\s+\w+(?:\s+\w+)?)',
            r'(icici\s+\w+(?:\s+\w+)?)',
            r'(axis\s+\w+(?:\s+\w+)?)',
            r'(kotak\s+\w+(?:\s+\w+)?)',
            r'(regalia(?:\s+\w+)?)',
            r'(moneyback(?:\s+\w+)?)',
            r'(amazon\s+pay)',
        ]
        for pattern in card_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).title()
        return None

    def _extract_date(self, text: str, patterns: List[str], fallback: datetime) -> datetime:
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = match.group(1).strip()
                for fmt in ["%d %B %Y", "%d %b %Y", "%Y-%m-%d", "%d-%m-%Y"]:
                    try:
                        return datetime.strptime(date_str, fmt)
                    except ValueError:
                        continue
        return fallback
