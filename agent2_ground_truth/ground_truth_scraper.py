import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import modal


TARGET_ISSUERS = [
    "HDFC Bank", "SBI Card", "ICICI Bank", "Axis Bank", "Bajaj Finserv", 
    "American Express India", "Kotak Mahindra Bank", "YES Bank", "IDFC FIRST Bank", 
    "RBL Bank", "IndusInd Bank", "Standard Chartered Bank India", "BOB Financial", 
    "Union Bank of India", "Punjab National Bank", "Canara Bank", "HSBC India", 
    "AU Small Finance Bank", "Federal Bank", "South Indian Bank", "CSB Bank", 
    "DBS Bank India", "Bank of India", "Indian Bank", "Bank of Maharashtra", 
    "Central Bank of India", "Indian Overseas Bank", "UCO Bank", "Punjab & Sind Bank", 
    "Karur Vysya Bank", "Karnataka Bank", "City Union Bank", "Tamilnad Mercantile Bank", 
    "Dhanlaxmi Bank", "J&K Bank", "SBM Bank India", "OneCard", "Slice", "Jupiter", 
    "Uni Cards", "Scapia", "Fi Money", "Tata Capital", "Aditya Birla Finance"
]
OUTPUT_DIR = Path("/tmp/kyc_ground_truth")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "crewai",
        "crewai_tools",
        "chromadb>=0.5.0",
        "scrapfly-sdk",
        "pydantic>=2",
        "requests",
        "beautifulsoup4",
        "pypdf",
    )
)

app = modal.App("kyc-ground-truth-scraper", image=image)


def source_id(issuer: str, url: str) -> str:
    digest = hashlib.sha256(f"{issuer}:{url}".encode()).hexdigest()[:12]
    return f"{issuer.lower().replace(' ', '-')}-{digest}"


def checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_source_manifest(issuer: str, url: str, source_type: str, text: str, status: str) -> dict[str, Any]:
    return {
        "source_id": source_id(issuer, url),
        "issuer": issuer,
        "url": url,
        "source_type": source_type,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "checksum": checksum(text) if text else None,
        "parser_status": status,
    }


def fallback_card_record(issuer: str, source: dict[str, Any]) -> dict[str, Any]:
    return {
        "issuer": issuer,
        "card_name": f"{issuer} credit card rules",
        "network": None,
        "rules": {
            "reward_rate": None,
            "lounge_access": None,
            "reward_caps": None,
            "category_exclusions": [],
            "fees": None,
            "validity_notes": "Needs CrewAI extraction from official source.",
        },
        "source_ids": [source["source_id"]],
    }


def run_crewai_scrape() -> dict[str, Any]:
    """Run official-source discovery and extraction through CrewAI."""
    from crewai import Agent, Crew, Task
    from crewai_tools import PDFSearchTool, SerperDevTool, WebsiteSearchTool

    search_tool = SerperDevTool()
    web_tool = WebsiteSearchTool()
    pdf_tool = PDFSearchTool()

    navigator = Agent(
        role="Bank Navigator",
        goal="Find official Indian issuer card pages and MITC PDFs for credit card rules.",
        backstory="A precise financial researcher that only trusts official issuer sources.",
        tools=[search_tool],
        verbose=True,
    )
    extractor = Agent(
        role="Web and PDF Extractor",
        goal="Extract reward rules, lounge criteria, caps, fees, exclusions, and validity notes.",
        backstory="A cautious parser that preserves source provenance for every claim.",
        tools=[web_tool, pdf_tool],
        verbose=True,
    )
    structurer = Agent(
        role="JSON Structurer",
        goal="Convert extracted issuer material into the Know Your Card cards database schema.",
        backstory="A schema-first data engineer who emits only validated JSON.",
        verbose=True,
    )

    tasks = [
        Task(
            description=(
                "Find official URLs and MITC PDF URLs for these issuers: "
                f"{', '.join(TARGET_ISSUERS)}. "
                "CRITICAL INSTRUCTION: The RBI has made it compulsory for Indian banks to use the '.bank.in' domain. "
                "You MUST prioritize finding and using URLs that end in '.bank.in' (e.g., hdfc.bank.in, icici.bank.in) for all banking institutions. "
                "Return issuer, URL, source type, and notes."
            ),
            expected_output="A source manifest table with official URLs and MITC PDFs.",
            agent=navigator,
        ),
        Task(
            description=(
                "For each official URL/PDF, extract rules for rewards, lounge access criteria, "
                "reward caps, merchant/category exclusions, fees, and validity windows."
            ),
            expected_output="Markdown extraction notes grouped by issuer and source URL.",
            agent=extractor,
        ),
        Task(
            description=(
                "Return a JSON object with keys generated_at, cards, and sources matching "
                "agent2_ground_truth/schemas/indian_cards_db.schema.json."
            ),
            expected_output="Strict JSON only.",
            agent=structurer,
        ),
    ]

    crew = Crew(agents=[navigator, extractor, structurer], tasks=tasks, verbose=True)
    raw = crew.kickoff()
    content = str(raw).strip()
    start = content.find("{")
    end = content.rfind("}") + 1
    if start < 0 or end <= start:
        raise ValueError("CrewAI did not return JSON")
    return json.loads(content[start:end])


def write_outputs(payload: dict[str, Any]) -> str:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "indian_cards_db.json"
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(output_path)


@app.function(timeout=3600)
def build_indian_cards_db() -> dict[str, Any]:
    try:
        payload = run_crewai_scrape()
    except Exception as exc:
        sources = [
            build_source_manifest(
                issuer,
                f"https://www.google.com/search?q={issuer.replace(' ', '+')}+credit+card+MITC+official",
                "search_fallback",
                "",
                f"fallback_created_after_error: {exc}",
            )
            for issuer in TARGET_ISSUERS
        ]
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "cards": [fallback_card_record(source["issuer"], source) for source in sources],
            "sources": sources,
        }

    path = write_outputs(payload)
    return {"output_path": path, "card_count": len(payload.get("cards", [])), "payload": payload}


@app.local_entrypoint()
def main():
    result = build_indian_cards_db.remote()
    print(json.dumps(result, indent=2, ensure_ascii=False))
