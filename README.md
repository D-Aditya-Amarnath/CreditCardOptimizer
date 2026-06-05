# Know Your Card (KYC)

Know Your Card is a local, privacy-first financial offer intelligence application for Indian credit card users. It securely bridges your personal promotional emails with a local Large Language Model to recommend the best credit card for a given purchase, without ever sending your personal data to the cloud.

## Frequently Asked Questions

**Are we using MCP and A2A Protocol?**
Yes! 
*   **MCP (Model Context Protocol):** We use `FastMCP` in Agent 1 (`kyc_mcp_server.py`) to expose your sanitized email inbox as a secure, local-only tool set that the AI can read from. 
*   **A2A (Agent-to-Agent):** We use `CrewAI` in Agent 2 (`ground_truth_scraper.py`) which orchestrates multiple autonomous agents (Navigator, Extractor, Structurer) communicating with each other to scrape and structure banking rules.

**Does the LLM model have memory or chat conversations?**
Currently, the Gradio user interface visually *displays* chat history, but the underlying local Llama model inference engine (`kyc_rag_engine.py`) is stateless. It treats every question as a brand new query and does not remember previous chat turns. If you want full chat memory, we would need to append the `history` variable to the local Llama prompt.

---

## Exhaustive File-by-File Documentation

The project is structured around four distinct "Agents" (phases of the data pipeline) and a Shared Core. **Every single file** in the repository is documented below:

### 1. Agent 1: Ingestion & FastMCP (`agent1_ingestion/`)
**Purpose:** Securely connect to your email inboxes, download promotional emails, strip out tracking pixels, and serve this clean data via MCP.
*   `__init__.py`: Makes the folder a Python module.
*   `email_sanitizer.py`: Removes malicious scripts and tracking pixels from HTML emails, and uses `BANK_NAME_HINTS` to map sender domains (like slice, onecard, hdfc) to real banks.
*   `gmail_collector.py`: A legacy prototype script for collecting emails specifically from Google's API (restored for historical reference).
*   `imap_ingestion.py`: The modern email client that connects to multiple email providers (Gmail, Outlook, Yahoo) natively via IMAP.
*   `kyc_mcp_server.py`: The FastMCP server that bridges the gap, allowing the LLM to request emails directly from the local machine securely.
*   `mcp_server.py`: A legacy/prototype version of the MCP server.
*   `setup.py`: A legacy initialization script.

### 2. Agent 2: Ground Truth Scraper (`agent2_ground_truth/`)
**Purpose:** Build a definitive "Ground Truth" database of credit card rules (reward caps, exclusions, lounge access) directly from 36+ official bank websites (enforcing `.bank.in` domains) to prevent AI hallucinations.
*   `__init__.py`: Makes the folder a Python module.
*   `ground_truth_scraper.py`: The CrewAI script that deploys Agent-to-Agent (A2A) web scrapers to read bank PDFs and websites on Modal.
*   `schemas/indian_cards_db.schema.json`: The strict JSON schema that ensures the CrewAI agents output perfectly formatted Ground Truth data.
*   `schemas/offer_extraction.schema.json`: The JSON schema defining what an "Offer" looks like.

### 3. Agent 3: Fine-Tuning Pipeline (`agent3_finetuning/`)
**Purpose:** Optimize a tiny, fast model (Qwen 3B) that can run entirely locally on low-end hardware.
*   `__init__.py`: Makes the folder a Python module.
*   `synthetic_data.py`: Uses a large Llama 70B model to generate 1,000 fake/synthetic promotional emails so we can train without using your real data.
*   `finetune_unsloth.py`: The Unsloth script that fine-tunes the Qwen2.5 model on the synthetic data.
*   `export_gguf.py`: Compresses the fine-tuned model into a 4-bit `.gguf` file for the Gradio frontend to load locally.

### 4. Agent 4: Gradio RAG Interface (`agent4_gradio_rag/`)
**Purpose:** The final user application. A local web UI that queries the SQLite database and asks the local model for recommendations.
*   `__init__.py`: Makes the folder a Python module.
*   `app_gradio.py`: The main Gradio web application (frontend).
*   `kyc_rag_engine.py`: The RAG orchestrator that fields user questions, fetches database context, and talks to the local LLM.
*   `local_llama.py`: The local inference engine using `llama-cpp-python` to run the `.gguf` model.
*   `chat.py`, `cli.py`, `run.py`: Legacy execution scripts for the prototype terminal and chat interfaces.
*   `orchestrator.py`, `recommendation.py`: Legacy prototypes for managing data flows.
*   `chunker.py`, `conflict_detector.py`, `context_compressor.py`, `prompt_builder.py`, `rag_service.py`, `retrieval_auditor.py`, `retrieval_planner.py`: The historical suite of RAG microservices used to detect conflicting bank rules and build dynamic prompts.
*   `static/app.js`: Custom JavaScript for the UI.
*   `static/kyc_theme.css` & `static/style.css`: Custom CSS stylesheets making the Gradio UI look premium.
*   `backend/`: A massive legacy folder containing the old FastAPI web server, including `main.py`, `config.py`, `deps.py`, various HTML templates (`backend/templates/`), and API routers (`backend/routers/`).

### 5. Shared Core (`shared_core/`)
**Purpose:** Reusable database and data-processing logic shared across all Agents.
*   `__init__.py`: Makes the folder a Python module.
*   `database.py`: SQLAlchemy setup and query execution for the `offers.db` SQLite database.
*   `models.py`: SQLAlchemy ORM classes (Tables) representing Users, Cards, and Emails.
*   `vector_store.py`: ChromaDB integration for semantic search of bank rules.
*   `banner_extractor.py`, `card_network_service.py`, `llm_extractor.py`, `merchant_normalizer.py`, `spend_analyzer.py`, `structured_extractor.py`, `transaction_parser.py`: Utility scripts for parsing transaction text, mapping merchants, calculating cashback math, and interacting with Cloud LLMs.

### 6. Root Configuration Files
*   `Dockerfile` & `docker-compose.yml`: Instructions for building the containerized environment.
*   `requirements.txt`: The Python PIP package dependencies.
*   `AGENT_TASK.md`: Your internal development checklist and task tracker.
*   `README.md`: This exact file you are reading.

---

## How to View and Run Individual Agents

### Viewing the Frontend (Without IMAP Email Access)
If you want to view the Gradio user interface **without** triggering the MCP server or connecting to any email inboxes, you can run the UI directly from the command line:

```bash
# Ensure you are in the root directory, then run:
python agent4_gradio_rag/app_gradio.py
```
This will start the local server on `http://0.0.0.0:7860`. You can interact with the UI, query the local database, and chat with the local model, but the "Refresh Offers" button will simply bypass fetching live emails.

### Running Agent 2 (Ground Truth Scraper)
```bash
modal run agent2_ground_truth/ground_truth_scraper.py
```

### Running the Full System (With Docker)
```bash
docker-compose up --build
```
This mounts the database and starts both the FastMCP Email bridge (Agent 1) and the Gradio UI (Agent 4) simultaneously.
