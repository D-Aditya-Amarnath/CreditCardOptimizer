import json
from datetime import datetime, timezone
from pathlib import Path

import modal


OUTPUT_DIR = Path("/tmp/kyc_training_data")
SAMPLE_BANKS = ["HDFC Bank", "SBI Card", "ICICI Bank", "Axis Bank", "Bajaj Finserv"]

image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "vllm",
    "jsonschema",
    "pydantic>=2",
)

app = modal.App("kyc-synthetic-offer-data", image=image)


PROMPT_TEMPLATE = """Generate one synthetic Indian credit-card promotional email example.
The email must be messy, realistic, and privacy-safe with no real personal data.
Return strict JSON:
{{
  "input": {{"subject": "...", "messy_email_text": "...", "bank_name": "..."}},
  "output": {{"bank_name": "...", "offers": [{{"merchant": "...", "card_name": "...", "offer_type": "...", "discount_percent": 10, "min_spend": 3000, "max_cashback": 1500, "valid_from": "YYYY-MM-DD", "valid_until": "YYYY-MM-DD", "category": "..."}}]}}
}}
Issuer focus: {bank}
Vary merchants across dining, travel, flights, tech, groceries, fuel, and shopping.
"""


def fallback_example(i: int, bank: str) -> dict:
    merchant = ["Amazon", "Zomato", "MakeMyTrip", "BigBasket", "Croma"][i % 5]
    category = ["tech", "dining", "travel", "groceries", "tech"][i % 5]
    return {
        "input": {
            "subject": f"{bank}: Save more on {merchant}",
            "messy_email_text": (
                f"<html><body><table><tr><td>{bank}</td></tr></table>"
                f"Use your {bank} credit card at {merchant}. Get 10% instant discount "
                "on min spend Rs. 3000. Max benefit Rs. 1500. Valid till 2026-12-31."
                "<img width='1' height='1' src='https://tracker.example/open.png'></body></html>"
            ),
            "bank_name": bank,
        },
        "output": {
            "bank_name": bank,
            "offers": [{
                "merchant": merchant,
                "card_name": f"{bank} Credit Card",
                "offer_type": "discount",
                "discount_percent": 10,
                "min_spend": 3000,
                "max_cashback": 1500,
                "valid_from": None,
                "valid_until": "2026-12-31",
                "category": category,
            }],
        },
    }


@app.function(gpu="A100", timeout=3600)
def generate_offer_pairs(count: int = 1000) -> dict:
    examples = []
    try:
        from vllm import LLM, SamplingParams

        llm = LLM(model="meta-llama/Llama-3.1-70B-Instruct", tensor_parallel_size=1)
        sampling = SamplingParams(temperature=0.7, max_tokens=900)
        prompts = [PROMPT_TEMPLATE.format(bank=SAMPLE_BANKS[i % len(SAMPLE_BANKS)]) for i in range(count)]
        outputs = llm.generate(prompts, sampling)

        for i, output in enumerate(outputs):
            text = output.outputs[0].text.strip()
            start = text.find("{")
            end = text.rfind("}") + 1
            try:
                examples.append(json.loads(text[start:end]))
            except Exception:
                examples.append(fallback_example(i, SAMPLE_BANKS[i % len(SAMPLE_BANKS)]))
    except Exception:
        examples = [fallback_example(i, SAMPLE_BANKS[i % len(SAMPLE_BANKS)]) for i in range(count)]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / "offer_extraction_pairs.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for item in examples:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(examples),
        "path": str(path),
    }


@app.local_entrypoint()
def main(count: int = 1000):
    print(generate_offer_pairs.remote(count))
