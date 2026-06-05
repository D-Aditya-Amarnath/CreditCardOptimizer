# Know Your Card (KYC) - Comprehensive System Documentation

Welcome to the definitive documentation for the Know Your Card (KYC) project. This repository contains a complex, multi-agent artificial intelligence application designed specifically for Indian credit card users. Its primary goal is to securely ingest personal promotional emails locally, cross-reference them against verified banking rules, and provide intelligent, privacy-first recommendations on which credit card to use for specific purchases.

The architecture is explicitly local-first. It refuses to send your sensitive financial or personal email data to external cloud APIs like OpenAI or Anthropic. Instead, it relies entirely on localized Llama architectures, Model Context Protocol (MCP), and advanced Agent-to-Agent (A2A) orchestration.

---

## 1. Architectural Paradigms

### The Model Context Protocol (MCP) Implementation
This application heavily leverages **FastMCP**. Instead of hardcoding API calls directly into the LLM logic, we spin up an MCP server locally. This server acts as an abstracted bridge. It connects to your SQLite database and raw email inbox, processes the data, and exposes it as a set of standardized "tools" to the LLM. This prevents the LLM from executing raw queries and sandboxes its data access strictly to what the MCP server permits.

### Agent-to-Agent (A2A) Protocols via CrewAI
While the local RAG inference is handled linearly, the Ground Truth data gathering is fully autonomous. We use **CrewAI** to orchestrate A2A communication. When scraping the internet for credit card rules, a "Navigator" agent communicates with an "Extractor" agent, passing context back and forth until the data is verified against `.bank.in` domains.

### Memory State
Currently, the Gradio user interface visually tracks chat history within the browser session. However, the core `KycRagEngine` local inference loop is strictly **stateless**. Every query is processed fresh without historical context appended to the prompt. To implement true LLM memory, the `history` object from Gradio must be explicitly formatted into the `local_llama.py` context window.

---

## 2. Exhaustive File Directory & Codebase Breakdown

Below is a mandatory, in-depth explanation of every single code file, configuration file, and script present in the repository, organized by their respective Agent.

### Agent 1: Email Ingestion & FastMCP (`agent1_ingestion/`)
This agent is responsible for the secure retrieval, sanitization, and transmission of your personal promotional emails. It ensures zero tracking pixels or malicious scripts reach the LLM.

*   **`__init__.py`**: 
    A standard Python file that initializes the `agent1_ingestion` directory as a module, allowing other parts of the application (like the Shared Core) to import its classes cleanly.

*   **`email_sanitizer.py`**:
    This is one of the most critical security files in the project. It uses `BeautifulSoup` to parse raw HTML emails retrieved from IMAP. It aggressively strips out `<script>`, `<iframe>`, `<link>`, and tracking `<img>` tags. Furthermore, it contains a massive dictionary called `BANK_NAME_HINTS` which maps over 40+ Indian legacy banks and modern fintechs (like Slice, OneCard, Jupiter, Scapia, HDFC, SBI) to their official names based on the sender's email domain.

*   **`imap_ingestion.py`**:
    The core ingestion engine. Unlike older APIs that required OAuth, this script connects directly to modern IMAP servers (Gmail, Outlook, Yahoo) using standard Python `imaplib`. It fetches emails securely, passes them to the `email_sanitizer.py`, and then commits the cleaned string to the `offers.db` SQLite database using the Shared Core models.

*   **`kyc_mcp_server.py`**:
    The active FastMCP server. It exposes two primary tools to the local network: `list_recent_sanitized_emails` and `get_email_context`. It pulls directly from the local database and caches the sanitized emails in memory, ensuring the LLM can instantly fetch context without re-querying the database every single time.

*   **`gmail_collector.py`**:
    *Legacy Prototype:* This file contains the older implementation of email collection that relied heavily on Google's specific OAuth API. It is kept in the repository purely for historical reference and backward compatibility if the IMAP ingestion fails.

*   **`mcp_server.py`**:
    *Legacy Prototype:* The original, bare-bones implementation of the Model Context Protocol before it was upgraded to the much faster and more robust `FastMCP` architecture found in `kyc_mcp_server.py`.

*   **`setup.py`**:
    *Legacy Prototype:* An older initialization script that was previously used to bootstrap the environment before the transition to Docker and Docker Compose. It contains basic `rich` console prints.

---

### Agent 2: Ground Truth Scraper (`agent2_ground_truth/`)
This agent ensures the LLM never hallucinates. It builds a factual database of credit card terms directly from official Indian bank domains.

*   **`__init__.py`**:
    Initializes the scraper directory as a Python module.

*   **`ground_truth_scraper.py`**:
    The flagship Cloud execution script. Deployed on Modal infrastructure, it boots up a CrewAI instance. It contains a massive list of 36+ Indian Banks and NBFCs. It explicitly instructs its "Navigator" agent to prioritize `.bank.in` domains (as mandated by the RBI) over generic `.com` domains to prevent phishing or outdated rules. It utilizes PDFSearchTool and WebsiteSearchTool to scrape "Most Important Terms and Conditions" (MITC) documents.

*   **`schemas/indian_cards_db.schema.json`**:
    A rigorous JSON Schema file. It forces the CrewAI "Structurer" agent to format its output exactly according to this blueprint. It demands arrays of objects containing `issuer`, `reward_rate`, `lounge_access`, and `category_exclusions`.

*   **`schemas/offer_extraction.schema.json`**:
    A secondary JSON Schema designed to govern what constitutes a valid "Offer" in the system, dictating fields for expiry dates, minimum spends, and maximum cashback caps.

---

### Agent 3: Fine-Tuning Pipeline (`agent3_finetuning/`)
To achieve local-first privacy, we need a small model that fits on a standard laptop GPU. This agent handles the creation of that model.

*   **`__init__.py`**:
    Initializes the fine-tuning directory as a Python module.

*   **`synthetic_data.py`**:
    Since we refuse to use real user emails to train the model (for privacy reasons), this script runs on Modal and uses `meta-llama/Llama-3.1-70B-Instruct` to artificially hallucinate 1,000 highly realistic promotional emails. This dataset serves as the safe training material.

*   **`finetune_unsloth.py`**:
    The core training loop. Using the `unsloth` library on Modal, it takes the synthetic dataset and fine-tunes the `Qwen/Qwen2.5-Coder-3B-Instruct` model to specifically excel at extracting JSON data from banking emails.

*   **`export_gguf.py`**:
    Once fine-tuning is complete, this script quantizes (compresses) the raw PyTorch weights into a 4-bit `.gguf` format. This drastic compression allows the LLM to run entirely on your local machine using `llama.cpp` instead of requiring expensive cloud compute.

---

### Agent 4: Gradio RAG Interface (`agent4_gradio_rag/`)
This massive directory contains both the current active frontend UI and the extensive suite of legacy prototype backend services.

#### Active Frontend & Inference Files
*   **`__init__.py`**:
    Module initializer.

*   **`app_gradio.py`**:
    The primary user interface. Built with Gradio, it constructs a responsive, premium web layout featuring a sidebar for account selection, a central chat interface for querying the RAG engine, and an HTML pane to render active local offers. It serves as the primary Docker entrypoint.

*   **`kyc_rag_engine.py`**:
    The brain of the operation. When the user types a question into Gradio, this script takes over. It queries the local SQLite database for relevant emails, fetches the user's saved cards, formats a massive context prompt, and sends it to the Local Llama engine for inference.

*   **`local_llama.py`**:
    The lowest-level inference wrapper. It uses `llama-cpp-python` to load the 4-bit `.gguf` model from the disk. It strictly enforces JSON schema outputs using `guided-generation` ensuring the LLM never responds with unstructured conversational text when data is expected.

*   **`static/app.js`**:
    Custom client-side JavaScript injected into the Gradio UI to handle specific browser-side DOM manipulations and enhance the interactive feel of the application.

*   **`static/kyc_theme.css`**:
    The primary visual stylesheet. It overrides Gradio's default blocky appearance, implementing glassmorphism, smooth transitions, customized typography (Google Inter), and sophisticated dark-mode compatible variables.

*   **`static/style.css`**:
    A secondary stylesheet previously used for older prototype interfaces, maintained for historical UI reference.

#### Legacy RAG Microservices
These files represent the complex historical pipeline used before the system was consolidated into the single `kyc_rag_engine.py`.
*   **`chat.py`**: An older command-line interactive chat script.
*   **`cli.py`**: A Typer-based Command Line Interface for managing the system via terminal commands.
*   **`run.py`**: The old Uvicorn entrypoint for the FastAPI server.
*   **`orchestrator.py`**: The previous manager that dictated which sub-service should handle a request.
*   **`recommendation.py`**: A legacy script specifically dedicated to formatting output recommendations.
*   **`chunker.py`**: Split massive emails into smaller token-chunks to fit inside smaller context windows.
*   **`conflict_detector.py`**: An experimental script designed to cross-reference multiple emails and detect conflicting bank terms.
*   **`context_compressor.py`**: Attempted to use summarization to shrink the context window before inference.
*   **`prompt_builder.py`**: Dynamically assembled Jinja-style templates for the LLM.
*   **`rag_service.py`**: The original Retrieval-Augmented Generation implementation before the Gradio transition.
*   **`retrieval_auditor.py`**: Logged exactly which vectors were retrieved to audit accuracy.
*   **`retrieval_planner.py`**: Pre-planned semantic search queries before executing them on ChromaDB.

#### Legacy FastAPI Backend (`agent4_gradio_rag/backend/`)
Before Gradio, the project used a massive FastAPI architecture with Jinja HTML templates.
*   **`main.py`**: The FastAPI application instance definition.
*   **`config.py`**: Environment variable and secret management.
*   **`deps.py`**: FastAPI dependency injection (handling database sessions and authentication).
*   **`routers/accounts.py`**: API endpoints for managing bank accounts.
*   **`routers/chat.py`**: API endpoints for managing the streaming chat responses.
*   **`routers/dashboard.py`**: API endpoints providing summary metrics for the frontend dashboard.
*   **`routers/emails.py`**: API endpoints for manually triggering IMAP syncs.
*   **`routers/notifications.py`**: API endpoints for managing user alerts.
*   **`routers/offers.py`**: API endpoints returning structured JSON offers.
*   **`routers/profiles.py`**: API endpoints managing user profile data.
*   **`routers/settings.py`**: API endpoints for application configuration.
*   **`routers/transactions.py`**: API endpoints for viewing mocked or real transaction history.
*   **`routers/user.py`**: API endpoints handling user creation and validation.
*   **`templates/*.html`**: Over 10 individual Jinja2 HTML files (e.g., `dashboard.html`, `cards.html`, `compare.html`) that previously constructed the frontend views before Gradio replaced them.

---

### 5. Shared Core (`shared_core/`)
This directory contains utility files, database connections, and ORM models that are imported across multiple Agents.

*   **`__init__.py`**:
    Initializes the shared core module.

*   **`database.py`**:
    The core SQLAlchemy engine. It connects to `sqlite:///offers.db` and provides methods like `initialize_schema()`, `get_all_accounts()`, and `get_user_cards()`.

*   **`models.py`**:
    The definitive schema definitions mapping Python classes to SQLite tables. Contains models like `UserProfile`, `RawEmailModel`, `ChunkModel`, `CardNetworkRule`, and `SyncHistory`.

*   **`vector_store.py`**:
    The ChromaDB semantic search integration. It initializes a persistent local vector database in the `./chroma_db` directory, allowing the application to convert text into embeddings and perform nearest-neighbor similarity searches.

*   **`banner_extractor.py`**:
    A specialized utility script designed to analyze image URLs found within emails and extract text from promotional banners using OCR or cloud vision APIs.

*   **`card_network_service.py`**:
    A calculation engine. It takes rules from the Ground Truth database and mathematically calculates exact cashback amounts based on the merchant category, base earning percent, and maximum monthly caps.

*   **`llm_extractor.py`**:
    A generalized wrapper used in older phases to interact with the LLM for simple data extraction tasks outside of the core RAG loop.

*   **`merchant_normalizer.py`**:
    A data-cleaning utility. It takes messy merchant strings (e.g., "AMZN PAY INDIA PVT LTD") and normalizes them to clean brand names ("Amazon") so the `card_network_service` can correctly identify accelerated rewards.

*   **`spend_analyzer.py`**:
    A utility script that analyzes a user's transaction history to identify spending patterns and categories.

*   **`structured_extractor.py`**:
    Another legacy cloud-extraction script utilizing Instructor or similar libraries to enforce Pydantic structured outputs from OpenAI.

*   **`transaction_parser.py`**:
    A regex-heavy utility that parses SMS or email transaction alerts to extract amounts, dates, and raw merchant strings.

---

### 6. Tests (`tests/`)
*   **`test_llm.py`**: A python script specifically for running unit tests against the local inference engine.
*   **`test_query.txt`**: A sample text file containing hardcoded queries used by the test script to benchmark RAG performance.

---

### 7. Root Configuration Files
These files sit in the top-level directory and dictate how the entire project environment is built and managed.

*   **`Dockerfile`**:
    The definitive blueprint for the containerized environment. It uses `python:3.12-slim`, installs system dependencies like `sqlite3` and `tesseract-ocr`, copies the `requirements.txt`, installs pip packages, and exposes port `7860`. Crucially, it sets the `CMD` to launch `agent4_gradio_rag/app_gradio.py`.

*   **`docker-compose.yml`**:
    The orchestrator for Docker. It defines the volume mappings (ensuring `offers.db`, `chroma_db`, and your downloaded `models` persist on your local hard drive and aren't wiped when the container restarts). It also injects essential environment variables like `KYC_MCP_COMMAND`.

*   **`requirements.txt`**:
    The massive pip dependency list. Contains everything from `gradio`, `fastapi`, and `sqlalchemy` to massive ML libraries like `torch`, `transformers`, `llama-cpp-python`, and `crewai`.

*   **`AGENT_TASK.md`**:
    An internal markdown file tracking the historical progress of the project, including checked-off features, known bugs, and the phase-by-phase implementation plan.

*   **`README.md`**:
    This exact 350+ line documentation file you are currently reading, providing unparalleled insight into the architecture.

*   **`.gitignore`**:
    Specifies which files Git should ignore (e.g., `__pycache__`, `.venv`, `.env`, the massive `.gguf` model files, and the local `.db` files) to keep the repository clean.

---

## 3. Execution & Deployment Instructions

### How to View the Frontend (Without IMAP Email Access)
If you simply want to browse the user interface, chat with the AI, and view the SQLite data without messing with `.env` files, FastMCP, or IMAP synchronization, you can run the Gradio application natively on your host machine. 

Ensure your virtual environment is active, and run from the root directory:
```bash
python agent4_gradio_rag/app_gradio.py
```
*Note: Because of our automatic `sys.path` injection, you do not need to mess with `PYTHONPATH` exports.*
This will launch the web UI at `http://0.0.0.0:7860`. You can interact fully; however, clicking "Refresh Offers" will simply bypass fetching live emails.

### How to Execute the Ground Truth Scraper (Agent 2)
To update the underlying banking rules from the 36+ Indian banks, execute the CrewAI Modal script:
```bash
modal run agent2_ground_truth/ground_truth_scraper.py
```

### How to Execute the Full Production System
To run the fully integrated app securely:
1. Download your `.gguf` model into the `./models/` directory.
2. Provide your IMAP credentials.
3. Run Docker Compose:
```bash
docker-compose up --build
```
Docker will automatically initialize the database, boot up the secure `kyc_mcp_server.py` in the background, map all persistent volumes, and serve the Gradio UI securely.
