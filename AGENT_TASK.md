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
