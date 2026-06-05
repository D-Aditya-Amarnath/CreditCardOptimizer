# Know Your Card (KYC) - The Ultimate Indian Credit Card Intelligence System

Welcome to the definitive, exhaustive documentation for the **Know Your Card (KYC)** project. 

Know Your Card is a highly sophisticated, multi-agent artificial intelligence application designed from the ground up for the Indian credit card ecosystem. In an era where financial data privacy is paramount, this system was built with a strict **local-first** philosophy. It refuses to send your sensitive personal promotional emails, transaction history, or financial data to external cloud APIs like OpenAI, Google, or Anthropic. 

Instead, KYC relies entirely on localized Large Language Model (LLM) architectures, the Model Context Protocol (MCP), and advanced Agent-to-Agent (A2A) orchestration. It securely bridges your personal emails with a local AI to recommend the absolute best credit card to use for any given purchase, maximizing your cashback and reward points.

---

## Table of Contents

1. [Architectural Paradigms](#1-architectural-paradigms)
2. [Data Flow & System Integration](#2-data-flow--system-integration)
3. [Exhaustive File Directory Breakdown](#3-exhaustive-file-directory-breakdown)
    - [Agent 1: Ingestion & FastMCP](#agent-1-ingestion--fastmcp)
    - [Agent 2: Ground Truth Scraper](#agent-2-ground-truth-scraper)
    - [Agent 3: Fine-Tuning Pipeline](#agent-3-fine-tuning-pipeline)
    - [Agent 4: Gradio RAG Interface](#agent-4-gradio-rag-interface)
    - [Shared Core](#shared-core)
    - [Root Configuration Files](#root-configuration-files)
4. [Standalone Agent Execution Guide](#4-standalone-agent-execution-guide)
    - [Running Agent 1 Independently](#running-agent-1-independently)
    - [Running Agent 2 Independently](#running-agent-2-independently)
    - [Running Agent 3 Independently](#running-agent-3-independently)
    - [Running Agent 4 (Frontend) Independently](#running-agent-4-frontend-independently)

---

## 1. Architectural Paradigms

### The Model Context Protocol (MCP) Implementation
This application heavily leverages the **Model Context Protocol (MCP)** via the `FastMCP` framework. 
Historically, AI applications hardcoded their data access logic directly into the LLM chain. This posed massive security risks. In KYC, we spin up an isolated MCP server locally on your machine. This server acts as an abstracted bridge. It connects to your SQLite database and raw email inbox, processes the data, and exposes it as a set of standardized, read-only "tools" to the LLM. 
This sandbox approach ensures the LLM can only query exactly what the FastMCP server permits, completely eliminating the risk of rogue AI executions mutating your database.

### Agent-to-Agent (A2A) Protocols via CrewAI
While the local RAG (Retrieval-Augmented Generation) inference is handled linearly, the Ground Truth data gathering is fully autonomous. We use **CrewAI** to orchestrate A2A communication. 
When scraping the internet for credit card rules, a "Navigator" agent communicates with an "Extractor" agent, passing context back and forth until the data is verified against `.bank.in` domains. Finally, a "Structurer" agent enforces JSON schema validation. This tri-agent conversation ensures zero hallucinations in the core banking rules.

### Local LLM Quantization (GGUF)
To ensure the LLM can run on consumer hardware (like laptops with limited VRAM), we utilize **GGUF** quantization. We take a massively powerful Qwen 3B model, fine-tune it on Modal, and compress its weights down to 4-bit precision. This allows the `llama-cpp-python` engine to load the entire neural network into standard system memory, achieving extremely fast inference speeds without requiring a $10,000 GPU.

### Memory State
Currently, the Gradio user interface visually tracks chat history within the browser session for a seamless user experience. However, the core `KycRagEngine` local inference loop is strictly **stateless**. Every query you type is processed fresh, without historical context appended to the prompt. This prevents context-window overflow and ensures lightning-fast responses. To implement true LLM memory, the `history` object from the Gradio frontend must be explicitly formatted into the `local_llama.py` context window.

---

## 2. Data Flow & System Integration

The KYC system operates across four distinct phases (Agents) that feed into one another:

1. **The Ingestion Phase (Agent 1):** Connects to your email via IMAP, pulls down HTML, sanitizes it of tracking pixels, and caches it via MCP.
2. **The Ground Truth Phase (Agent 2):** Scrapes the internet for absolute banking truths, completely independent of your personal data.
3. **The Fine-Tuning Phase (Agent 3):** Generates synthetic data and trains the AI model to understand the outputs of Agent 1 and Agent 2.
4. **The Interface Phase (Agent 4):** Provides the visual frontend, orchestrating the final RAG pipeline that combines your emails, the ground truth, and the fine-tuned AI to generate a financial recommendation.

---

## 3. Exhaustive File Directory Breakdown

Below is a mandatory, in-depth explanation of absolutely every single code file, configuration file, and script present in the repository. Nothing is skipped.

### Agent 1: Email Ingestion & FastMCP (`agent1_ingestion/`)
This agent is responsible for the secure retrieval, sanitization, and transmission of your personal promotional emails. It ensures zero tracking pixels or malicious scripts reach the LLM.

*   **`__init__.py`**: 
    A standard Python file that initializes the `agent1_ingestion` directory as a module. This allows other parts of the application to import its classes cleanly without path errors.

*   **`email_sanitizer.py`**:
    This is one of the most critical security files in the project. It uses the `BeautifulSoup` HTML parsing library to parse raw emails retrieved from IMAP. It aggressively strips out `<script>`, `<iframe>`, `<link>`, and tracking `<img>` tags. Furthermore, it contains a massive, exhaustive dictionary called `BANK_NAME_HINTS`. This map covers over 40+ Indian legacy banks and modern fintechs (like Slice, OneCard, Jupiter, Scapia, HDFC, SBI) to properly identify the official bank name based on the sender's email domain.

*   **`imap_ingestion.py`**:
    The core ingestion engine. Unlike older APIs that required complex Google OAuth configurations, this script connects directly to modern IMAP servers (Gmail, Outlook, Yahoo) using standard Python `imaplib`. It handles secure SSL connections, fetches unread emails securely, passes them to the `email_sanitizer.py`, and then commits the cleaned string to the `offers.db` SQLite database using the Shared Core SQLAlchemy models.

*   **`kyc_mcp_server.py`**:
    The active FastMCP server. It exposes two primary tools to the local network: `list_recent_sanitized_emails` and `get_email_context`. It pulls directly from the local database and caches the sanitized emails in memory. This ensures the LLM can instantly fetch context without re-querying the database every single time, drastically reducing latency.

*   **`gmail_collector.py`**:
    *Legacy Prototype:* This file contains the older implementation of email collection that relied heavily on Google's specific OAuth API and `credentials.json`. It is kept in the repository purely for historical reference and backward compatibility in case the IMAP ingestion method faces specific firewall restrictions.

*   **`mcp_server.py`**:
    *Legacy Prototype:* The original, bare-bones implementation of the Model Context Protocol before the system was upgraded to the much faster and more robust `FastMCP` architecture found in `kyc_mcp_server.py`.

*   **`setup.py`**:
    *Legacy Prototype:* An older initialization script that was previously used to bootstrap the environment, test database connections, and verify LLM pathways before the transition to fully automated Docker and Docker Compose setups. It utilizes `rich` console prints for terminal formatting.

---

### Agent 2: Ground Truth Scraper (`agent2_ground_truth/`)
This agent ensures the LLM never hallucinates. It builds a factual database of credit card terms directly from official Indian bank domains, ensuring cashback math is always accurate.

*   **`__init__.py`**:
    Initializes the scraper directory as a Python module, ensuring correct relative import resolutions.

*   **`ground_truth_scraper.py`**:
    The flagship Cloud execution script. Deployed on Modal serverless infrastructure, it boots up a highly complex CrewAI instance. It contains an exhaustive array of 36+ Indian Banks and NBFCs. It explicitly instructs its "Navigator" agent with a `CRITICAL INSTRUCTION` to prioritize `.bank.in` domains (as mandated by the RBI) over generic `.com` domains. This prevents the agent from scraping phishing sites or outdated third-party blogs. It utilizes `PDFSearchTool` and `WebsiteSearchTool` to parse complex "Most Important Terms and Conditions" (MITC) documents.

*   **`schemas/indian_cards_db.schema.json`**:
    A rigorous JSON Schema file. It forces the CrewAI "Structurer" agent to format its output exactly according to this blueprint. It demands structured arrays of objects containing keys like `issuer`, `reward_rate`, `lounge_access`, and `category_exclusions`. If the AI fails to match this schema, it is forced to regenerate.

*   **`schemas/offer_extraction.schema.json`**:
    A secondary JSON Schema designed to govern what constitutes a valid "Offer" in the system. It strictly dictates field requirements for expiry dates, minimum spends, and maximum cashback caps.

---

### Agent 3: Fine-Tuning Pipeline (`agent3_finetuning/`)
To achieve local-first privacy, we need a small model that fits on a standard laptop GPU or CPU. This agent handles the creation, training, and compression of that model.

*   **`__init__.py`**:
    Initializes the fine-tuning directory as a Python module.

*   **`synthetic_data.py`**:
    Since we refuse to use real user emails to train the model (for strict privacy and compliance reasons), this script runs on Modal and uses a massive Teacher model (`meta-llama/Llama-3.1-70B-Instruct`) to artificially hallucinate 1,000 highly realistic promotional emails. This dataset serves as the completely safe, anonymized training material for the smaller model.

*   **`finetune_unsloth.py`**:
    The core training loop. Using the highly optimized `unsloth` library on Modal A10G GPUs, it takes the synthetic dataset and fine-tunes the smaller `Qwen/Qwen2.5-Coder-3B-Instruct` model. It specifically trains the model to excel at extracting JSON data from the messy HTML structure of banking emails, applying LoRA (Low-Rank Adaptation) adapters to update the model weights efficiently.

*   **`export_gguf.py`**:
    Once fine-tuning is complete, this script performs quantization. It compresses the raw PyTorch weights into a highly optimized 4-bit `.gguf` format. This drastic compression reduces the model size from 12GB to under 3GB, allowing the LLM to run entirely on your local machine using `llama.cpp` instead of requiring expensive cloud compute nodes.

---

### Agent 4: Gradio RAG Interface (`agent4_gradio_rag/`)
This massive directory contains both the current active frontend web UI and the extensive suite of legacy prototype backend services.

#### Active Frontend & Inference Files
*   **`__init__.py`**:
    Module initializer. Ensures all internal modules can cross-reference each other.

*   **`app_gradio.py`**:
    The primary user interface and application entrypoint. Built with Gradio, it constructs a responsive, premium web layout featuring a sidebar for account selection, a central chat interface for querying the RAG engine, and an HTML pane to render active local offers. It serves as the primary Docker `CMD` execution target.

*   **`kyc_rag_engine.py`**:
    The brain of the operation. When the user types a question into the Gradio UI, this script takes over. It queries the local SQLite database for relevant emails, fetches the user's saved cards, formats a massive, highly-structured context prompt, and sends it directly to the Local Llama engine for inference.

*   **`local_llama.py`**:
    The lowest-level local inference wrapper. It imports `llama-cpp-python` to load the 4-bit `.gguf` model from the local disk into RAM. It strictly enforces JSON schema outputs using `guided-generation`, ensuring the LLM never goes off-script and responds with unstructured conversational text when strict dictionary data is expected.

*   **`static/app.js`**:
    Custom client-side JavaScript injected directly into the Gradio UI to handle specific browser-side DOM manipulations, scrolling logic, and enhance the overall interactive feel of the web application.

*   **`static/kyc_theme.css`**:
    The primary visual stylesheet. It overrides Gradio's default blocky appearance, implementing modern glassmorphism, smooth CSS transitions, customized typography (importing Google Inter), and sophisticated dark-mode compatible variables to ensure a premium user experience.

*   **`static/style.css`**:
    A secondary stylesheet previously used for older prototype interfaces, maintained strictly for historical UI reference and legacy component support.

#### Legacy RAG Microservices
These files represent the complex historical pipeline used before the system was consolidated into the highly efficient single `kyc_rag_engine.py`. They are preserved for architectural reference.
*   **`chat.py`**: An older command-line interactive chat script that allowed terminal-based interactions.
*   **`cli.py`**: A Typer-based Command Line Interface for managing the system via raw terminal commands.
*   **`run.py`**: The old Uvicorn entrypoint for the legacy FastAPI server.
*   **`orchestrator.py`**: The previous manager that dictated which sub-service should handle a specific user request.
*   **`recommendation.py`**: A legacy script specifically dedicated to formatting output recommendations.
*   **`chunker.py`**: Split massive emails into smaller token-chunks to fit inside extremely limited early context windows.
*   **`conflict_detector.py`**: An experimental script designed to cross-reference multiple emails and detect conflicting bank terms or overlapping promotional dates.
*   **`context_compressor.py`**: Attempted to use summarization to shrink the context window before inference, replaced by larger context windows in Qwen.
*   **`prompt_builder.py`**: Dynamically assembled Jinja-style templates for the LLM.
*   **`rag_service.py`**: The original Retrieval-Augmented Generation implementation before the Gradio transition.
*   **`retrieval_auditor.py`**: Logged exactly which vectors were retrieved to audit semantic accuracy.
*   **`retrieval_planner.py`**: Pre-planned semantic search queries before executing them on ChromaDB.

#### Legacy FastAPI Backend (`agent4_gradio_rag/backend/`)
Before Gradio was adopted for rapid UI iteration, the project used a massive FastAPI architecture with traditional Jinja HTML templates.
*   **`main.py`**: The FastAPI application instance definition.
*   **`config.py`**: Environment variable and secret management.
*   **`deps.py`**: FastAPI dependency injection (handling database sessions and mock authentication).
*   **`routers/accounts.py`**: API endpoints for managing bank accounts.
*   **`routers/chat.py`**: API endpoints for managing the streaming Server-Sent Events (SSE) chat responses.
*   **`routers/dashboard.py`**: API endpoints providing summary metrics for the frontend dashboard.
*   **`routers/emails.py`**: API endpoints for manually triggering IMAP syncs via HTTP requests.
*   **`routers/notifications.py`**: API endpoints for managing user alerts.
*   **`routers/offers.py`**: API endpoints returning structured JSON offers.
*   **`routers/profiles.py`**: API endpoints managing user profile data.
*   **`routers/settings.py`**: API endpoints for application configuration.
*   **`routers/transactions.py`**: API endpoints for viewing mocked or real transaction history.
*   **`routers/user.py`**: API endpoints handling user creation and validation.
*   **`templates/*.html`**: Over 10 individual Jinja2 HTML files (e.g., `dashboard.html`, `cards.html`, `compare.html`, `login.html`) that previously constructed the frontend views before Gradio replaced them.

---

### 5. Shared Core (`shared_core/`)
This directory contains utility files, database connections, and ORM models that are universally imported across all Agents to prevent code duplication.

*   **`__init__.py`**:
    Initializes the shared core module.

*   **`database.py`**:
    The core SQLAlchemy engine. It connects to the `sqlite:///offers.db` file and provides all necessary CRUD (Create, Read, Update, Delete) wrapper methods like `initialize_schema()`, `get_all_accounts()`, and `get_user_cards()`.

*   **`models.py`**:
    The definitive schema definitions mapping Python classes to SQLite tables. Contains models like `UserProfile`, `RawEmailModel`, `ChunkModel`, `CardNetworkRule`, and `SyncHistory`.

*   **`vector_store.py`**:
    The ChromaDB semantic search integration. It initializes a persistent local vector database in the `./chroma_db` directory, allowing the application to mathematically convert text into dense embeddings and perform extremely fast nearest-neighbor similarity searches for banking rules.

*   **`banner_extractor.py`**:
    A specialized utility script designed to analyze image URLs found within emails and extract text from promotional banners using OCR or cloud vision APIs.

*   **`card_network_service.py`**:
    A crucial calculation engine. It takes the Ground Truth database rules and mathematically calculates exact cashback amounts based on the merchant category, the card's base earning percent, category multipliers, and maximum monthly caps.

*   **`llm_extractor.py`**:
    A generalized wrapper used in older phases to interact with the LLM for simple data extraction tasks outside of the core RAG loop.

*   **`merchant_normalizer.py`**:
    A data-cleaning utility. It takes messy, raw merchant strings (e.g., "AMZN PAY INDIA PVT LTD") and normalizes them to clean brand names ("Amazon") so the `card_network_service.py` can correctly identify if accelerated rewards apply.

*   **`spend_analyzer.py`**:
    A utility script that analyzes a user's transaction history to identify broad spending patterns and categories.

*   **`structured_extractor.py`**:
    Another legacy cloud-extraction script utilizing Instructor or similar libraries to enforce Pydantic structured outputs from OpenAI.

*   **`transaction_parser.py`**:
    A regex-heavy utility that parses highly unstructured SMS or email transaction alerts to extract specific amounts, transaction dates, and raw merchant strings.

---

### 6. Tests (`tests/`)
*   **`test_llm.py`**: A python script specifically for running unit tests against the local inference engine to ensure schema compliance.
*   **`test_query.txt`**: A sample text file containing hardcoded test queries used by the test script to benchmark RAG retrieval performance.

---

### 7. Root Configuration Files
These files sit in the top-level directory and dictate how the entire project environment is built, configured, and managed.

*   **`Dockerfile`**:
    The definitive blueprint for the containerized Linux environment. It uses `python:3.12-slim`, installs system-level dependencies like `sqlite3` and `tesseract-ocr`, copies the `requirements.txt`, installs pip packages via pip, and exposes network port `7860`. Crucially, it sets the `CMD` entrypoint to launch `agent4_gradio_rag/app_gradio.py`.

*   **`docker-compose.yml`**:
    The orchestrator for Docker. It defines the volume mappings (ensuring `offers.db`, `chroma_db`, and your downloaded `models/` directory persist on your local hard drive and aren't wiped when the container restarts). It also injects essential environment variables like `KYC_MCP_COMMAND` to link the containers together.

*   **`requirements.txt`**:
    The massive pip dependency list. Contains everything from web frameworks (`gradio`, `fastapi`) and ORMs (`sqlalchemy`) to massive Machine Learning libraries like `torch`, `transformers`, `llama-cpp-python`, and `crewai`.

*   **`AGENT_TASK.md`**:
    An internal markdown file tracking the historical progress of the project, including checked-off features, known bugs, design decisions, and the phase-by-phase implementation plan.

*   **`README.md`**:
    This exact exhaustive documentation file you are currently reading, providing unparalleled insight into the architecture.

*   **`.gitignore`**:
    Specifies exactly which files Git should ignore (e.g., `__pycache__`, `.venv`, `.env`, the massive `.gguf` model files, and the local `.db` files) to keep the remote GitHub repository clean and free of massive binary files.

---

## 4. Standalone Agent Execution Guide

The Know Your Card system is highly modular. You are not forced to run the entire system inside Docker if you only want to test or utilize a specific component. You can call each Agent individually without dependencies on the others.

### Running Agent 1 Independently (Email Ingestion & FastMCP)
If you only want to spin up the local MCP server to serve your emails to an external tool (like Claude Desktop or an external LangChain script), you can run Agent 1 in absolute isolation. 

1. Ensure your `.env` contains your `KYC_IMAP_ACCOUNTS` credentials.
2. Run the MCP server directly from the root:
```bash
python agent1_ingestion/kyc_mcp_server.py
```
This will start the FastMCP SSE/stdio listener. It will not load the UI, it will not load the Llama model, and it will not run CrewAI. It simply exposes the email tools natively.

### Running Agent 2 Independently (Ground Truth Scraper)
If you want to update the SQLite database with the latest banking rules, you don't need the frontend or the LLM. You simply need Modal and CrewAI.

1. Ensure you have Modal authenticated (`modal token new`).
2. Execute the Modal script directly:
```bash
modal run agent2_ground_truth/ground_truth_scraper.py
```
This will spin up a cloud environment, deploy the CrewAI agents, scrape the `.bank.in` domains, and download the resulting `indian_cards_db.json` to your local machine, completely independent of the rest of the KYC ecosystem.

### Running Agent 3 Independently (Fine-Tuning)
If you wish to retrain the local Qwen 3B model on new synthetic data without touching the frontend:

1. Generate the synthetic data on Modal:
```bash
modal run agent3_finetuning/synthetic_data.py
```
2. Kick off the Unsloth fine-tuning loop:
```bash
modal run agent3_finetuning/finetune_unsloth.py
```
3. Export the newly trained weights into GGUF:
```bash
modal run agent3_finetuning/export_gguf.py
```
This pipeline is entirely decoupled from the actual RAG engine.

### Running Agent 4 (Frontend) Independently
**If you want to view the frontend GUI, test the Chatbot, and see the layout, but you DO NOT want to provide IMAP email access or run the MCP server:**

You can run the Gradio application natively on your host machine in complete isolation. Because of our automatic `sys.path` injection handling, the script natively understands where the Shared Core databases are located.

1. Ensure your virtual environment is active.
2. Ensure you have placed your model inside `./models/qwen2.5-coder-3b-instruct-q4_k_m.gguf`.
3. Run this single command from the root directory:
```bash
python3 agent4_gradio_rag/app_gradio.py
```

This will instantly launch the web UI at `http://0.0.0.0:7860`. You can interact fully with the UI, query the local database, and chat with the local model. 
*Note: Because Agent 1 is disabled in this scenario, clicking the "Refresh Offers" button in the UI will gracefully fail or bypass fetching live emails, but the core RAG chatbot will continue to function seamlessly based on previously cached data.*

---
*End of Documentation.*
