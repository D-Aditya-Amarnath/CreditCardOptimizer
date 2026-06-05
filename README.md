# Know Your Card (KYC)

Know Your Card is a local, privacy-first financial offer intelligence application for Indian credit card users. It securely bridges your personal promotional emails with a local Large Language Model to recommend the best credit card for a given purchase, without ever sending your personal data to the cloud.

## System Architecture: The 4 Agents

The project is structured around four distinct "Agents" (phases of the data pipeline), each responsible for a specific part of the system.

### 1. Agent 1: Ingestion & FastMCP (`agent1_ingestion/`)
**Purpose:** Securely connect to your email inboxes, download promotional emails, strip out tracking pixels, and serve this clean data to the local LLM.
**Model Used:** None. This agent relies purely on standard Python tools (BeautifulSoup, IMAP) to sanitize data safely.
**Key Files:**
- `imap_ingestion.py`: Connects to multiple email providers (Gmail, Outlook, Yahoo) via IMAP.
- `email_sanitizer.py`: Removes malicious scripts and tracking pixels from HTML.
- `kyc_mcp_server.py`: A FastMCP local server that exposes the clean email data as read-only tools for the AI.

### 2. Agent 2: Ground Truth Scraper (`agent2_ground_truth/`)
**Purpose:** Build a definitive "Ground Truth" database of credit card rules (reward caps, exclusions, lounge access) directly from official bank websites. This prevents the AI from hallucinating rules.
**Model Used:** **OpenAI GPT-4o** (via CrewAI framework). Because this data is public, we use powerful cloud models to navigate complex PDFs and websites.
**Key Files:**
- `ground_truth_scraper.py`: CrewAI orchestrated web scraping jobs running on Modal.
- `schemas/`: JSON schemas enforcing the exact structure of the scraped bank rules.

### 3. Agent 3: Fine-Tuning Pipeline (`agent3_finetuning/`)
**Purpose:** Optimize a tiny, fast model that can run entirely locally on low-end hardware (like a 4GB VRAM GPU) while maintaining high accuracy in extracting credit card offers.
**Models Used:**
- **Teacher Model:** `meta-llama/Llama-3.1-70B-Instruct` (Used to generate 1,000 synthetic/fake email examples so we never train on real personal data).
- **Student Model:** `Qwen/Qwen2.5-Coder-3B-Instruct` (The small model that learns from the synthetic data via Unsloth).
**Key Files:**
- `synthetic_data.py`: Generates the training dataset.
- `finetune_unsloth.py`: Fine-tunes the Qwen 3B model.
- `export_gguf.py`: Compresses the model into a 4-bit `.gguf` file for local use.

### 4. Agent 4: Gradio RAG Interface (`agent4_gradio_rag/`)
**Purpose:** The final user application. A local web UI that ties everything together. It takes your query, asks the MCP server for relevant emails, queries the SQLite Ground Truth database, and asks the local model for a recommendation.
**Model Used:** Your fine-tuned **Qwen2.5-Coder-3B-Instruct-GGUF** (running locally via `llama-cpp-python`).
**Key Files:**
- `app_gradio.py`: The Gradio web interface.
- `kyc_rag_engine.py`: The orchestrator that fields questions, fetches email context, and runs local inference.
- `local_llama.py`: The local inference engine enforcing JSON schema outputs.

### Shared Core (`shared_core/`)
Contains shared logic used by multiple agents:
- `database.py` & `models.py`: SQLAlchemy schemas for users, cards, and emails.
- `vector_store.py`: ChromaDB integration for semantic search of bank rules.

---

## How to Run the App (Using Docker)

Everything you need to launch the app locally is provided in the Docker configuration.

**Prerequisites:**
1. You must have your downloaded GGUF model placed in the `./models/` directory (e.g., `qwen2.5-coder-3b-instruct-q4_k_m.gguf`).
2. Make sure Docker and Docker Compose are installed.

**Launch Command:**
```bash
docker-compose up --build
```

**What happens?**
1. Docker builds the environment and auto-initializes your SQLite database (`offers.db`).
2. The `kyc_mcp_server.py` starts in the background to safely read your emails.
3. The `app_gradio.py` server starts and exposes the Web UI.
4. Visit **http://127.0.0.1:7860** in your browser to start chatting with your local, private AI!
