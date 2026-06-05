# Know Your Card

Know Your Card (KYC) is a private financial offer intelligence app for Indian credit card users. It reads family credit-card offer emails locally, sanitizes them, validates claims against an official bank-rules knowledge base, and recommends the best card for a purchase.

The target system uses a dual architecture:

- **Local PC:** private email ingestion, FastMCP bridge, SQLite, ChromaDB, Gradio UI, and local GGUF inference through `llama-cpp-python`.
- **Modal Cloud:** heavy background scraping, synthetic data generation, and fine-tuning only. Personal email data must not be sent to Modal.

## Non-Negotiable Constraints

- Final live inference is local-only on a GTX 1050 with 4GB VRAM.
- Target runtime model is a quantized 3B GGUF model, loaded with `llama-cpp-python`.
- Final local inference must use JSON grammar/schema enforcement.
- No OpenAI, Anthropic, or other external LLM APIs are allowed in the final app.
- Personal email data stays local.
- Modal credits are reserved for CrewAI scraping, dataset generation, and fine-tuning.
- UI target is Gradio v4 with a custom dark theme and elemental offer badges.

## Current Branches And Worktrees

The project is split into one shared baseline plus four phase branches:

| Branch | Worktree | Purpose |
| --- | --- | --- |
| `kyc/base-prototype-snapshot` | `/home/aditya/CreditCardOptimizer` | Shared prototype baseline and project README |
| `kyc/phase-1-ingestion-fastmcp` | `/tmp/CreditCardOptimizer-worktrees/kyc-phase-1-ingestion` | IMAP ingestion, sanitizer, FastMCP email bridge |
| `kyc/phase-2-crew-scraper-modal` | `/tmp/CreditCardOptimizer-worktrees/kyc-phase-2-crew-scraper` | Modal CrewAI official-rules scraper |
| `kyc/phase-3-modal-finetune` | `/tmp/CreditCardOptimizer-worktrees/kyc-phase-3-finetune` | Modal synthetic data, Unsloth fine-tune, GGUF export |
| `kyc/phase-4-gradio-rag` | `/tmp/CreditCardOptimizer-worktrees/kyc-phase-4-gradio-rag` | Gradio UI, local llama inference, RAG orchestration |

Check all worktrees:

```bash
git worktree list
```

## Architecture

```text
Family inboxes
   |
   | local IMAP/Gmail/Outlook read-only access
   v
Email sanitizer
   - strips scripts/styles/hidden nodes/tracking pixels
   - preserves useful table layout
   - emits clean JSON email context
   |
   v
FastMCP local bridge
   - read-only tools
   - no unnecessary disk persistence
   |
   v
Gradio KYC app
   |
   | asks both local sources
   v
SQLite + ChromaDB local knowledge base <--- Modal-generated official bank rules
   |
   v
llama-cpp-python 3B GGUF with JSON grammar
   |
   v
Recommendation + structured JSON response
```

## Phase Status

### Phase 1: Ingestion And FastMCP

Branch: `kyc/phase-1-ingestion-fastmcp`

Implemented:

- `services/email_sanitizer.py`
- `services/imap_ingestion.py`
- `kyc_mcp_server.py`
- `tests/test_email_sanitizer.py`

Run tests:

```bash
cd /tmp/CreditCardOptimizer-worktrees/kyc-phase-1-ingestion
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest tests.test_email_sanitizer
```

Configure IMAP accounts locally:

```bash
export KYC_IMAP_ACCOUNTS='[
  {
    "account_email": "family@example.com",
    "host": "imap.gmail.com",
    "username": "family@example.com",
    "password": "app-password",
    "mailbox": "INBOX"
  }
]'
```

Run the local email bridge:

```bash
cd /tmp/CreditCardOptimizer-worktrees/kyc-phase-1-ingestion
.venv/bin/python kyc_mcp_server.py
```

### Phase 2: Modal CrewAI Ground Truth Scraper

Branch: `kyc/phase-2-crew-scraper-modal`

Implemented:

- `modal_jobs/ground_truth_scraper.py`
- `data/schemas/indian_cards_db.schema.json`

The scraper is designed to find official Indian issuer pages and MITC PDFs for HDFC, SBI Card, ICICI, Axis, and Bajaj Finserv, then emit a unified card-rules database.

Run locally through Modal:

```bash
cd /tmp/CreditCardOptimizer-worktrees/kyc-phase-2-crew-scraper
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
modal run modal_jobs/ground_truth_scraper.py
```

Expected output:

- `indian_cards_db.json`
- source manifest with URL, retrieval timestamp, checksum, and parser status
- Chroma/SQLite ingestion-ready card rules

### Phase 3: Modal Fine-Tuning Pipeline

Branch: `kyc/phase-3-modal-finetune`

Implemented:

- `modal_jobs/synthetic_data.py`
- `modal_jobs/finetune_unsloth.py`
- `modal_jobs/export_gguf.py`
- `data/schemas/offer_extraction.schema.json`

Run sequence:

```bash
cd /tmp/CreditCardOptimizer-worktrees/kyc-phase-3-finetune
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
modal run modal_jobs/synthetic_data.py --count 1000
modal run modal_jobs/finetune_unsloth.py
modal run modal_jobs/export_gguf.py
```

Final artifact should be downloaded into a local ignored model directory such as:

```text
models/kyc-qwen3b-q4.gguf
```

### Phase 4: Gradio UI And Local RAG

Branch: `kyc/phase-4-gradio-rag`

Implemented:

- `app_gradio.py`
- `static/kyc_theme.css`
- `services/local_llama.py`
- `services/kyc_rag_engine.py`

Run:

```bash
cd /tmp/CreditCardOptimizer-worktrees/kyc-phase-4-gradio-rag
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
export KYC_GGUF_MODEL_PATH=/home/aditya/CreditCardOptimizer/models/kyc-qwen3b-q4.gguf
export KYC_MCP_COMMAND="/tmp/CreditCardOptimizer-worktrees/kyc-phase-1-ingestion/.venv/bin/python /tmp/CreditCardOptimizer-worktrees/kyc-phase-1-ingestion/kyc_mcp_server.py"
.venv/bin/python app_gradio.py
```

Open:

```text
http://127.0.0.1:7860
```

## Existing Prototype Components

The baseline still includes the earlier FastAPI/RAG prototype:

- `backend/` for FastAPI routes and Jinja templates
- `database.py` for SQLAlchemy models and CRUD
- `models.py` for SQLAlchemy and Pydantic schemas
- `services/vector_store.py` for ChromaDB indexing
- `services/rag_service.py` for the older LM Studio style RAG flow
- `gmail_collector.py` and `orchestrator.py` for the Gmail API ingest path
- `mcp_server.py` for the earlier offer recommendation MCP server

These are useful references, but the final KYC app should use the Phase 1 and Phase 4 local-only path.

## Environment Variables

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | SQLite URL, defaults to `sqlite:///offers.db` |
| `KYC_IMAP_ACCOUNTS` | JSON array of local IMAP account configs |
| `KYC_IMAP_ACCOUNTS_FILE` | Path to local IMAP account config JSON |
| `KYC_GGUF_MODEL_PATH` | Path to local quantized 3B GGUF model |
| `KYC_LLAMA_N_CTX` | Context length for local llama |
| `KYC_LLAMA_N_GPU_LAYERS` | GPU layers for GTX 1050 tuning |
| `KYC_MCP_COMMAND` | Command used by Phase 4 to start/call the Phase 1 MCP bridge |

Do not commit secrets, app passwords, OAuth tokens, Chroma data, SQLite files, or GGUF model artifacts.

## Development Workflow

Commit baseline changes:

```bash
cd /home/aditya/CreditCardOptimizer
git status --short
git add -A
git commit -m "Describe baseline change"
```

Commit phase worktree changes:

```bash
cd /tmp/CreditCardOptimizer-worktrees/kyc-phase-1-ingestion
git status --short
git add -A
git commit -m "Describe phase change"
```

Merge baseline into a phase:

```bash
cd /tmp/CreditCardOptimizer-worktrees/kyc-phase-4-gradio-rag
git merge --no-edit kyc/base-prototype-snapshot
```

## Immediate Next Build Steps

1. Harden Phase 1 IMAP filtering with issuer-domain search queries and UID checkpointing.
2. Add JSON schema validation to Phase 4 local llama responses.
3. Add a local importer that converts Phase 2 `indian_cards_db.json` into SQLite and ChromaDB.
4. Replace older OpenAI-compatible LM Studio calls in the final path with `services/local_llama.py`.
5. Run a full local smoke test once a GGUF model is present.
