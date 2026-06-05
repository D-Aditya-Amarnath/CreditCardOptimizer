# Financial Offer Intelligence Agent

A RAG-powered web application that analyzes credit card offers from Gmail emails and provides personalized recommendations with spending insights.

## Architecture

### Hybrid RAG System
- **SQLite**: Source of truth for structured data (emails, offers, transactions, user profiles)
- **ChromaDB**: Semantic search with hierarchical indexing (emails, offer chunks, merchant summaries)
- **8 RAG Principles**: Semantic boundary chunking, hierarchical indexing, context-aware reranking, retrieval timing control, negative space injections, compression before injection, cross-document conflict detection, retrieval auditing

### Core Services
| Service | Purpose |
|---------|---------|
| `chunker.py` | Semantic boundary chunking with HTML structure analysis |
| `vector_store.py` | Hierarchical ChromaDB indexing with domain boosts |
| `rag_service.py` | Core RAG pipeline with conflict detection |
| `conflict_detector.py` | Cross-document offer conflict resolution |
| `retrieval_planner.py` | Adaptive top_k + intent classification |
| `prompt_builder.py` | System prompts with negative injections |
| `context_compressor.py` | Progressive truncation for LLM injection |
| `retrieval_auditor.py` | Per-query logging and metrics |
| `merchant_normalizer.py` | 2-layer normalization (rule-based + LLM) |
| `transaction_parser.py` | Per-bank regex patterns for transaction emails |
| `spend_analyzer.py` | Category breakdown, trends, frequency |
| `card_network_service.py` | Card acceptance + earning rate rules |
| `banner_extractor.py` | HTML via BeautifulSoup, images via Moondream |
| `structured_extractor.py` | LLM-based offer extraction at ingest |

### Web Stack
- **FastAPI** with Jinja2 templates
- **HTMX** for progressive enhancement
- **Tailwind CSS** (CDN)
- Session-based auth with bcrypt

---

## Quick Start

### 1. Setup LM Studio
1. Download **LM Studio** from https://lmstudio.ai/
2. Start LM Studio and download these models:
   - **llama3.2:3b** (or 3b-instruct) - For generation/chat
   - **nomic-embed-text** - For embeddings (if available in LM Studio, otherwise use local sentence-transformers)
3. Click "Start Server" in LM Studio - ensure it runs on port `1234`

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment (.env)
```bash
LMSTUDIO_BASE_URL=http://localhost:1234/v1
LMSTUDIO_API_KEY=lm-studio
DATABASE_URL=sqlite:///offers.db
SECRET_KEY=change-this-to-a-random-secret-key
```

### 4. Gmail API Setup
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project and enable **Gmail API**
3. Create OAuth credentials (Desktop App)
4. Download as `credentials.json` to project root

### 5. Run the App
```bash
# Option A: Direct Python
python run.py

# Option B: Docker
docker-compose up --build
```

### 6. Access Web UI
- Open `http://localhost:8000`
- First visit `/setup` to create account
- Visit `/sync` to link Gmail accounts
- Dashboard at `/dashboard` will auto-sync if enabled in settings

---

> **Note:** If you prefer Ollama, change `.env` to use `OLLAMA_BASE_URL` and pull models via `ollama pull`. Both are supported.

---

## Project Structure

```
CreditCardOptimizer/
├── models.py                    # SQLAlchemy models + Pydantic schemas
├── database.py                   # DatabaseManager with all CRUD
├── orchestrator.py               # Email processing pipeline
├── gmail_collector.py           # Gmail API with 90+ Indian bank domains
│
├── services/                     # 8 RAG principles implementation
│   ├── chunker.py               # Semantic boundary chunking
│   ├── vector_store.py          # Hierarchical ChromaDB indexing
│   ├── rag_service.py           # Core RAG pipeline
│   ├── conflict_detector.py     # Cross-doc conflict detection
│   ├── retrieval_planner.py    # Adaptive retrieval timing
│   ├── prompt_builder.py       # Negative injections
│   ├── context_compressor.py   # Compression before injection
│   ├── retrieval_auditor.py    # Retrieval auditing
│   ├── merchant_normalizer.py  # 2-layer merchant normalization
│   ├── transaction_parser.py   # Per-bank transaction parsing
│   ├── spend_analyzer.py       # Spend pattern analysis
│   ├── card_network_service.py # Card acceptance + earning rules
│   ├── banner_extractor.py     # HTML/image extraction
│   └── structured_extractor.py # LLM offer extraction
│
├── backend/
│   ├── main.py                 # FastAPI app + routes
│   ├── config.py               # Settings from .env
│   ├── deps.py                 # Auth dependency injection
│   ├── routers/                 # API endpoints
│   │   ├── dashboard.py        # Dashboard API
│   │   ├── chat.py             # Streaming chat (SSE)
│   │   ├── offers.py           # Offer list + compare
│   │   ├── user.py             # Card CRUD
│   │   ├── emails.py           # Email browser + sync
│   │   ├── notifications.py   # Notification API
│   │   ├── profiles.py         # Profile CRUD
│   │   ├── accounts.py         # Account linking + sync stream
│   │   ├── transactions.py     # Transaction history + spend API
│   │   └── settings.py         # User settings
│   └── templates/              # Jinja2 HTML templates
│       ├── base.html           # Nav + Tailwind + HTMX
│       ├── dashboard.html      # Stats + expiring offers
│       ├── chat.html           # Streaming chat UI
│       ├── compare.html        # Offer comparison
│       ├── cards.html         # Card management
│       ├── transactions.html   # Transaction history
│       ├── spend_analysis.html # Spend patterns
│       ├── emails.html        # Email browser
│       ├── sync.html          # Account sync UI
│       ├── profiles.html      # Profile management
│       ├── settings.html      # Auto-sync settings
│       └── loading.html       # SSE sync progress
│
├── static/
│   ├── style.css               # Custom styles
│   └── app.js                  # HTMX config + polling
│
├── .env                        # Environment config
├── requirements.txt            # Python dependencies
├── docker-compose.yml         # Docker setup
├── Dockerfile                 # Container definition
└── run.py                     # Convenience runner
```

---

## API Endpoints

### Pages (HTML)
| Endpoint | Description |
|----------|-------------|
| `/setup` | First-time account creation |
| `/login` | Login page |
| `/dashboard` | Main dashboard |
| `/chat/chat` | RAG chat interface |
| `/compare` | Offer comparison |
| `/cards` | Card management |
| `/transactions` | Transaction history |
| `/spend-analysis` | Spend patterns |
| `/emails` | Email browser |
| `/sync` | Account sync |
| `/profiles` | Family profiles |
| `/settings` | User settings |
| `/loading` | SSE sync progress |

### API Endpoints (JSON)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/dashboard/summary` | GET | Dashboard stats |
| `/api/offers` | GET | List offers |
| `/api/offers/compare` | GET | Compare offers + card recommendations |
| `/api/offers/search` | GET | Semantic search |
| `/api/cards` | GET/POST | List/Add cards |
| `/api/transactions` | GET | List transactions |
| `/api/transactions/spend-pattern` | GET | Spend analysis |
| `/api/emails` | GET | List emails |
| `/api/accounts/sync-stream` | GET | SSE sync events |
| `/api/profiles` | GET/POST | List/Create profiles |
| `/api/settings` | GET/PUT | Get/Update settings |
| `/api/chat` | GET | Streaming chat (SSE) |

---

## Database Schema

### Core Tables
- `raw_emails` - Gmail emails (with email_type: promotional/transactional)
- `offers` - Extracted credit card offers
- `banner_offers` - Banner images + extracted text
- `chunks` - Semantic chunks from emails
- `transactions` - Parsed transaction records

### User Tables
- `user_profiles` - User accounts
- `user_cards` - User's credit cards
- `user_settings` - Auto-sync preferences
- `profile_account_mappings` - Profile ↔ Gmail account links

### Supporting Tables
- `merchant_normalizations` - Raw → normalized merchant mappings
- `card_network_rules` - Card acceptance + earning rates
- `notifications` - In-app notifications
- `retrieval_audit` - RAG query logs
- `sync_history` - Sync run history

---

## Indian Bank/NBFC Domains (~90 domains)

The system recognizes Indian financial domains including:
- HDFC Bank, SBI, ICICI, Axis Bank, Kotak
- American Express, Citibank, HSBC
- Bajaj Finserv, Capital Float, Zip
- And more...

---

## Card Network Rules

Pre-seeded rules for common cards:
- American Express (Amex)
- HDFC Regalia Gold
- HDFC MoneyBack+
- SBI Card PRIME
- ICICI Amazon Pay
- Axis Ace

Each rule includes:
- `base_earning_percent` - Base reward rate
- `category_earnings` - Category-specific rates
- `accelerated_merchants` - Bonus earning merchants
- `excluded_merchants` - Merchants where card not accepted

---

## Troubleshooting

### Ollama Connection
Ensure Ollama is running:
```bash
ollama serve
```

### Gmail Authentication
If OAuth token expires, delete `.credentials/token.json` and re-authenticate.

### Database Issues
Delete `offers.db` and `chroma_db/` to start fresh:
```bash
rm offers.db
rm -rf chroma_db
```

### Port Already in Use
If port 8000 is busy, run with custom port:
```bash
python -c "from backend.main import app; import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8080)"
```