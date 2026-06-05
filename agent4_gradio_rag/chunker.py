import re
from typing import List, Optional
from bs4 import BeautifulSoup
import httpx
from shared_core.models import ChunkModel


MERCHANT_ALIASES = {
    "amazon": ["amazon", "amazn", "amzn"],
    "myntra": ["myntra"],
    "swiggy": ["swiggy"],
    "zomato": ["zomato"],
    "flipkart": ["flipkart", "fk", "fkart"],
    "bigbasket": ["bigbasket", "bbasket"],
    "bookmyshow": ["bookmyshow", "bms"],
    "makemytrip": ["makemytrip", "mmt", "goibibo"],
    "cleartrip": ["cleartrip"],
    "dominos": ["dominos", "domino's"],
    "pizza hut": ["pizza hut", "pizzahut"],
    "mcdonalds": ["mcdonald", "mcd"],
    "kfc": ["kfc"],
    "uber": ["uber"],
    "ola": ["ola"],
    "netmeds": ["netmeds", "pharmeasy", "apollo"],
    "ajio": ["ajio"],
    "tata cliq": ["tatacliq", "tata cliq", "cliq"],
    "nykaa": ["nykaa"],
    "shopify stores": ["shopify"],
}

BANK_ALIASES = {
    "hdfc bank": ["hdfc", "hdfc bank", "hdfcbank"],
    "sbi card": ["sbi", "sbi card", "sbicard", "state bank"],
    "icici bank": ["icici", "icici bank", "icicibank"],
    "axis bank": ["axis", "axis bank", "axisbank"],
    "kotak": ["kotak", "kotak bank", "kotakbank"],
    "yes bank": ["yes bank", "yesbank"],
    "indusind": ["indusind", "indusind bank"],
    "idfc first": ["idfc", "idfc first", "idfcfirst"],
    "rbl bank": ["rbl", "rbl bank"],
    "federal bank": ["federal", "federal bank"],
    "amex": ["amex", "american express", "americanexpress"],
    "bajaj": ["bajaj", "bajaj finserv"],
    "onecard": ["onecard", "one card"],
    "slice": ["slice"],
    "uni cards": ["uni", "uni cards"],
}

BOILERPLATE_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"unsubscribe",
        r"if you (?:do not|no longer) wish",
        r"this email was sent to",
        r"privacy policy",
        r"terms?\s*(?:&\s*)?conditions?",
        r"registered office",
        r"©\s*\d{4}.*bank",
        r"mail id.*not.*receive",
        r"stop receiving",
        r"view in browser",
        r"image.*not.*display",
        r"click here to unsubscribe",
        r"to unsubscribe click",
        r"this message was sent",
        r"you are receiving this because",
    ]
]


class SemanticChunker:
    def chunk_email(self, body_text: str, body_html: str, email_id: str) -> List[ChunkModel]:
        all_chunks = []
        seen_texts = set()

        if body_html:
            html_chunks = self._chunk_by_html(body_html, email_id)
            all_chunks.extend(html_chunks)

        para_chunks = self._chunk_by_paragraphs(body_text, email_id)
        all_chunks.extend(para_chunks)

        offer_chunks = self._chunk_by_offer_regex(body_text, email_id)
        all_chunks.extend(offer_chunks)

        all_chunks = self._deduplicate(all_chunks, seen_texts)
        all_chunks = self._classify_and_score(all_chunks)

        return all_chunks

    def _chunk_by_html(self, body_html: str, email_id: str) -> List[ChunkModel]:
        soup = BeautifulSoup(body_html, "html.parser")
        chunks = []

        for elem in soup.find_all(['div', 'td', 'p', 'li', 'tr']):
            text = elem.get_text(separator="\n", strip=True)
            text = re.sub(r'\n{3,}', '\n\n', text)

            if len(text) < 30:
                continue
            if self._is_boilerplate(text):
                continue

            chunk = ChunkModel(
                email_id=email_id,
                chunk_index=len(chunks),
                text=text,
                source="html",
                chunk_type="general",
                weight=1.0,
            )
            chunks.append(chunk)

        return chunks

    def _chunk_by_paragraphs(self, body_text: str, email_id: str) -> List[ChunkModel]:
        paragraphs = re.split(r'\n\s*\n', body_text)
        chunks = []
        for i, para in enumerate(paragraphs):
            para = para.strip()
            if len(para) < 30:
                continue
            if self._is_boilerplate(para):
                continue

            chunk = ChunkModel(
                email_id=email_id,
                chunk_index=len(chunks),
                text=para,
                source="paragraph",
                chunk_type="general",
                weight=1.0,
            )
            chunks.append(chunk)

        return chunks

    def _chunk_by_offer_regex(self, body_text: str, email_id: str) -> List[ChunkModel]:
        offer_patterns = [
            r'(?:cashback|discount|flat\s+\d+%)\s*(?:on|at|for)?\s*[\w\s]+?(?:valid|expires|till|until|upto|up to|maximum|max)[\s\S]{0,500}',
            r'(?:₹\s*\d+|\d+%)\s*(?:off|cashback|discount|reward)[\s\S]{0,500}?(?:valid|expires|till|until|minimum)',
            r'(?:use|using|with)\s*(?:your\s+)?(?:hdfc|sbi|icici|axis|kotak|yes|indusind|idfc|rbl|federal)[a-z\s]*(?:card|cards)?[\s\S]{0,400}?(?:cashback|discount|offer|reward)',
        ]

        chunks = []
        for i, pattern in enumerate(offer_patterns):
            for match in re.finditer(pattern, body_text, re.IGNORECASE):
                text = match.group(0).strip()
                if len(text) > 40:
                    chunk = ChunkModel(
                        email_id=email_id,
                        chunk_index=len(chunks),
                        text=text,
                        source="regex_offer",
                        chunk_type="offer",
                        weight=1.5,
                    )
                    chunks.append(chunk)

        return chunks

    def _deduplicate(self, chunks: List[ChunkModel], seen: set) -> List[ChunkModel]:
        result = []
        for chunk in chunks:
            normalized = chunk.text.lower().strip()[:100]
            if normalized not in seen:
                seen.add(normalized)
                result.append(chunk)
        return result

    def _classify_and_score(self, chunks: List[ChunkModel]) -> List[ChunkModel]:
        for chunk in chunks:
            chunk_type = self._classify_type(chunk.text)
            chunk.chunk_type = chunk_type
            chunk.weight = self._compute_weight(chunk_type)

            meta = self._extract_metadata(chunk.text)
            chunk.merchants = meta["merchants"]
            chunk.cards = meta["cards"]
            chunk.discount_percent = meta["discount_percent"]
            chunk.min_spend = meta["min_spend"]
            chunk.max_cashback = meta["max_cashback"]
            chunk.expiry_date = meta["expiry_date"]
            chunk.offer_type = meta["offer_type"]

        return [c for c in chunks if c.chunk_type != "boilerplate"]

    def _classify_type(self, text: str) -> str:
        text_lower = text.lower()
        if self._is_boilerplate(text):
            return "boilerplate"
        if any(kw in text_lower for kw in ['cashback', 'discount', 'offer', '₹', '% off', 'reward']):
            return "offer"
        if len(text) < 100:
            return "short"
        return "general"

    def _compute_weight(self, chunk_type: str) -> float:
        return {
            "offer": 1.5,
            "offer_header": 1.2,
            "general": 1.0,
            "boilerplate": 0.0,
            "legal": 0.2,
            "footer": 0.3,
            "short": 0.5,
        }.get(chunk_type, 1.0)

    def _is_boilerplate(self, text: str) -> bool:
        text_lower = text.lower()
        return any(p.search(text_lower) for p in BOILERPLATE_PATTERNS)

    def _extract_metadata(self, text: str) -> dict:
        merchants = self._extract_merchants(text)
        cards = self._extract_cards(text)
        discount = self._extract_number(text, [
            r'(\d+)%\s*(?:cashback|off|discount)',
            r'flat\s+(\d+)%',
            r'(\d+)\s*percent',
        ])
        min_spend = self._extract_number(text, [
            r'(?:min|minimum)\s*(?:spend|transaction)[:\s]*₹?\s*([\d,]+)',
            r'above\s*₹?\s*([\d,]+)',
            r'transact\s*(?:for|min)\s*₹?\s*([\d,]+)',
        ])
        max_cashback = self._extract_number(text, [
            r'(?:max|maximum|upto|up to|cap)[:\s]*₹?\s*([\d,]+)',
            r'₹([\d,]+)\s*(?:max|cashback)',
        ])
        expiry = self._extract_date(text)
        offer_type = self._classify_offer_type(text)

        return {
            "merchants": merchants,
            "cards": cards,
            "discount_percent": discount,
            "min_spend": min_spend,
            "max_cashback": max_cashback,
            "expiry_date": expiry,
            "offer_type": offer_type,
        }

    def _extract_merchants(self, text: str) -> List[str]:
        text_lower = text.lower()
        found = []
        for merchant, aliases in MERCHANT_ALIASES.items():
            if any(a in text_lower for a in aliases):
                found.append(merchant)
        return list(set(found))

    def _extract_cards(self, text: str) -> List[str]:
        text_lower = text.lower()
        found = []
        for card, aliases in BANK_ALIASES.items():
            if any(a in text_lower for a in aliases):
                found.append(card)
        return list(set(found))

    def _extract_number(self, text: str, patterns: List[str]) -> Optional[float]:
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1).replace(',', ''))
                except (ValueError, IndexError):
                    pass
        return None

    def _extract_date(self, text: str) -> Optional[str]:
        date_patterns = [
            r'(?:valid|expires|till|until)\s+(?:till|until)?\s*(\d{1,2}\s+\w+\s+\d{4})',
            r'(\d{1,2}\s+\w+\s+\d{4})',
            r'(\d{4}-\d{2}-\d{2})',
        ]
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _classify_offer_type(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        if 'cashback' in text_lower:
            return 'cashback'
        if 'reward' in text_lower or 'points' in text_lower:
            return 'reward_points'
        if 'discount' in text_lower or '% off' in text_lower:
            return 'discount'
        return 'offer'
