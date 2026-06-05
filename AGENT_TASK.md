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
