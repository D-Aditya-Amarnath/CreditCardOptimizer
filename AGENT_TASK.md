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
