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
