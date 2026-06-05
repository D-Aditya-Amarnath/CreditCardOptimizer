from typing import List, Dict, Any, Optional


SYSTEM_PROMPTS = {
    "search": """You are the Financial Offer Intelligence Agent.
You are given REAL email data retrieved from the user's inbox.
Summarize the emails for the user. Show dates, subjects, senders, and key details.
Look for expiry dates or deadlines in the email body text.
Be helpful, concise, and conversational.""",

    "recommend": """You are the Financial Offer Intelligence Agent.
Based on the REAL promotional email data retrieved below, recommend the best credit card
for the user's purchase. Compare offers and rank by cashback/discount value.
ONLY use the data below. NEVER invent offers.
When multiple offers apply, show them ranked by value.""",

    "greeting": """You are a helpful assistant. Greet the user and briefly explain
what you can help with: searching credit card offers, getting recommendations,
and syncing emails.""",
}

NEGATIVE_INJECTIONS = {
    "search": """
DO NOT:
- Invent cashback percentages not explicitly in the provided emails
- Invent expiry dates not in the provided emails
- Invent card names not in the retrieved emails
- Speculate about future offers

IF INFORMATION IS MISSING:
- Say: "I don't have emails about [topic]"
- Say: "The retrieved emails don't specify [detail]"
- Do NOT guess or fill gaps
""",
    "recommend": """
RECOMMENDATION RULES:
- Only recommend cards explicitly mentioned in the retrieved emails
- Always state the source email and date for each recommendation
- If no offer matches the user's spend amount, say so clearly
- Do NOT invent offer terms to fill gaps
- If multiple offers apply, rank by: discount_percent DESC, then max_cashback DESC
- Flag if an offer appears expired
""",
}


def build_prompt(query: str, context: str, intent: str,
                 conflicts: List[Dict] = None, results: List[Dict] = None) -> Dict[str, str]:
    system = SYSTEM_PROMPTS.get(intent, SYSTEM_PROMPTS["search"])
    system += NEGATIVE_INJECTIONS.get(intent, "")

    if results:
        system += build_scope_injection(results)
        system += build_citation_requirement(results)

    if conflicts:
        system += build_conflict_injection(conflicts)

    return {
        "system": system,
        "user": f"Question: {query}\n\nRetrieved Data:\n{context}",
    }


def build_scope_injection(results: List[Dict]) -> str:
    if not results:
        return ""

    date_range = get_date_range(results)
    banks = list(set(extract_banks(r.get("sender", "")) for r in results))
    merchants = list(set(m for r in results for m in r.get("merchants", [])))
    cards = list(set(c for r in results for c in r.get("cards", [])))

    return f"""
RETRIEVAL SCOPE:
- Retrieved: {len(results)} relevant emails/chunks
- Date range: {date_range}
- Banks covered: {', '.join(banks) if banks else 'unknown'}
- Merchants covered: {', '.join(merchants) if merchants else 'unknown'}
- Cards mentioned: {', '.join(cards) if cards else 'unknown'}

Answer only within this scope. Do not reference offers outside this data.
"""


def build_citation_requirement(results: List[Dict]) -> str:
    return """
CITATION: For each recommendation or summary, cite the source by:
- Sender (e.g., "HDFC Bank")
- Date received
- This helps users verify and explore further.
"""


def build_conflict_injection(conflicts: List[Dict]) -> str:
    section = "\n⚠️ CONFLICT DETECTED:\n"
    for c in conflicts:
        section += f"- {c.get('description', c.get('type'))}\n"
        for item in c.get("items", []):
            section += f"  • {item.get('sender', 'Unknown')} ({item.get('date', '')}): "
            if item.get('discount'):
                section += f"{item['discount']}% cashback\n"
            elif item.get('expiry'):
                section += f"valid till {item['expiry']}\n"
            else:
                section += "\n"
    return section


def extract_banks(text: str) -> List[str]:
    banks = []
    text_lower = text.lower()
    bank_map = {
        "hdfc": "HDFC Bank", "sbi": "SBI Card", "icici": "ICICI Bank",
        "axis": "Axis Bank", "kotak": "Kotak Bank", "yes bank": "Yes Bank",
        "indusind": "IndusInd Bank", "idfc": "IDFC First Bank", "rbl": "RBL Bank",
        "federal": "Federal Bank", "amex": "American Express", "bajaj": "Bajaj Finserv",
    }
    for key, name in bank_map.items():
        if key in text_lower:
            banks.append(name)
    return banks


def get_date_range(results: List[Dict]) -> str:
    dates = [r.get("date_received", "") for r in results if r.get("date_received")]
    if not dates:
        return "unknown"
    dates.sort()
    return f"{dates[0][:10]} to {dates[-1][:10]}"
