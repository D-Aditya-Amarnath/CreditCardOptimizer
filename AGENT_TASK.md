# Agent 1 Task: Ingestion & FastMCP Server

Branch: `kyc/phase-1-ingestion-fastmcp`
Worktree: `/tmp/CreditCardOptimizer-worktrees/kyc-phase-1-ingestion`

## Mission
Build the local privacy-preserving data bridge for Know Your Card. Personal email data must remain local. Do not introduce external LLM APIs.

## Constraints
- Final live inference path must support local-only operation.
- Sanitized email context may be exposed to the local LLM through MCP tools, but should not be unnecessarily persisted.
- Preserve existing Gmail collector/database patterns where useful, but add IMAP support for Gmail and Outlook accounts.
- Prefer typed schemas and tests over ad hoc dictionaries.

## Deliverables
- `services/email_sanitizer.py`
  - BeautifulSoup-based sanitizer.
  - Remove `script`, `style`, hidden nodes, tracking pixels, remote beacon images, and unsafe attributes.
  - Preserve useful table layout as readable text.
  - Emit schema: `{"bank_name": "", "subject": "", "clean_body": ""}` plus optional metadata if needed.
- `services/imap_ingestion.py`
  - Secure multi-account IMAP iterator for family Gmail/Outlook inboxes.
  - Config from environment or local config file excluded from git.
  - UID/window based incremental scan.
- `mcp_server.py` or `kyc_mcp_server.py`
  - Use `mcp.server.fastmcp.FastMCP`.
  - Expose read-only tools such as `list_recent_sanitized_emails`, `get_email_context`, and `search_recent_emails`.
  - No write tools.
- Tests/fixtures for sanitizer behavior against representative promotional HTML.

## Acceptance Criteria
- Sanitizer strips executable/hidden/tracking content while preserving offer text and table semantics.
- IMAP logic can iterate multiple accounts without logging secrets.
- FastMCP server starts locally and exposes read-only sanitized email tools.
- No OpenAI/Anthropic or other external LLM dependency is added.

# Agent 2 Task: CrewAI Ground Truth Scraper on Modal

Branch: `kyc/phase-2-crew-scraper-modal`
Worktree: `/tmp/CreditCardOptimizer-worktrees/kyc-phase-2-crew-scraper`

## Mission
Build the heavy cloud dataset generation scraper for official Indian credit card rules and MITC documents. Modal credits are for this background job only.

## Constraints
- Cloud compute is Modal-only.
- Output must be usable locally by Phase 4 through SQLite/ChromaDB/JSON.
- Keep scraping sources auditable: official bank/NBFC URLs and downloaded MITC PDF provenance should be preserved.
- Do not mix personal email data into cloud scraping.

## Deliverables
- `modal_jobs/ground_truth_scraper.py`
  - `@modal.function(timeout=3600)` wrapper.
  - Modal image with `crewai`, `crewai_tools`, `chromadb`, `scrapfly-sdk`, PDF tooling, and markdown extraction dependencies.
- CrewAI agents/tasks:
  - Bank Navigator Agent using `SerperDevTool` for official URLs and MITC PDFs.
  - Web/PDF extractor tasks for HDFC, SBI, ICICI, Axis, and Bajaj.
  - JSON Structurer Agent that emits a unified card/rules schema.
- `data/schemas/indian_cards_db.schema.json`
- Export logic for:
  - `data/generated/indian_cards_db.json`
  - ChromaDB artifact or ingestion-ready markdown chunks.
  - Source manifest with URL, retrieval timestamp, checksum, and parser status.

## Acceptance Criteria
- Modal function can be deployed and run independently.
- JSON output validates against the schema.
- Each rule includes source references.
- Hidden/important rules such as lounge criteria, reward caps, exclusions, fees, and validity windows are represented when found.

# Agent 3 Task: Modal Synthetic Data & Fine-Tuning Pipeline

Branch: `kyc/phase-3-modal-finetune`
Worktree: `/tmp/CreditCardOptimizer-worktrees/kyc-phase-3-finetune`

## Mission
Create the cloud-only pipeline that synthesizes offer extraction examples, lightly fine-tunes the target 3B model, and exports a local 4-bit GGUF artifact for GTX 1050 inference.

## Constraints
- Modal cloud is permitted for heavy generation/training only.
- The final runtime model must be local GGUF and loaded through `llama-cpp-python`.
- Training data must not contain real personal email content unless explicitly anonymized and approved.
- Target model family should remain small enough for 4GB VRAM after quantization.

## Deliverables
- `modal_jobs/synthetic_data.py`
  - A100 Modal function that generates 1,000 pairs of messy Indian bank email text to clean JSON offer schema.
  - Schema validation and deduplication.
  - No real PII in generated examples.
- `modal_jobs/finetune_unsloth.py`
  - Unsloth LoRA/QLoRA fine-tune script for selected 3B model.
  - Evaluation split and JSON exactness metrics.
- `modal_jobs/export_gguf.py`
  - Merge/export path.
  - Quantize to 4-bit GGUF.
  - Download/sync instructions for local artifact directory excluded from git.
- `data/schemas/offer_extraction.schema.json`

## Acceptance Criteria
- Synthetic examples validate against schema.
- Fine-tuning job is reproducible from Modal secrets/config.
- GGUF artifact is generated or the exact export command path is implemented.
- A small local smoke test can load the final GGUF via `llama-cpp-python` and produce schema-constrained JSON.

# Agent 4 Task: Gradio v4 UI & Local RAG Inference

Branch: `kyc/phase-4-gradio-rag`
Worktree: `/tmp/CreditCardOptimizer-worktrees/kyc-phase-4-gradio-rag`

## Mission
Build the local Know Your Card UI and inference runtime. This is the final privacy-preserving app surface.

## Constraints
- Gradio v4 with customized `gr.Theme` and custom CSS.
- No external LLM APIs in final local inference.
- Use `llama-cpp-python` with a quantized 3B GGUF model and strict JSON grammar/schema enforcement.
- Personal email data must stay local.

## Deliverables
- `app_gradio.py` or `kyc_app.py`
  - `gr.Blocks` layout:
    - left `gr.Column(scale=1)` for user/family account selection.
    - center `gr.Column(scale=2)` for chat.
    - right `gr.Column(scale=1)` for active offers HTML.
  - `gr.Theme(primary_hue="orange", secondary_hue="blue", neutral_hue="slate")`.
  - Deep navy/charcoal dark-mode styling.
- `static/kyc_theme.css`
  - `.fire-badge`, `.water-badge`, `.wind-badge`, `.lightning-badge`, `.earth-badge`.
- `services/local_llama.py`
  - `llama-cpp-python` loader for 3B GGUF.
  - JSON grammar/schema-constrained generation.
- `services/kyc_rag_engine.py`
  - Calls FastMCP read-only email tools.
  - Queries local SQLite/ChromaDB ground-truth repository.
  - Builds two context windows: personal sanitized offers and verified bank rules.
  - Returns both user chat answer and machine-readable JSON.

## Acceptance Criteria
- App launches locally with Gradio.
- UI shows selectable accounts, chat, and elemental offer badges.
- Inference path uses local `llama-cpp-python`, not OpenAI-compatible APIs.
- Query path combines FastMCP email context and local rules database.
- JSON response is schema-constrained and validated before display.
