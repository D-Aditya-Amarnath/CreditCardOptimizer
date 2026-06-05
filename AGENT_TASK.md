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
