import os
from dotenv import load_dotenv
from rich.console import Console
from rich.prompt import Prompt
from openai import OpenAI

from agent4_gradio_rag.orchestrator import OfferAgentOrchestrator
from shared_core.database import DatabaseManager
from shared_core.vector_store import VectorStore

load_dotenv()
console = Console()

# ─── Shared Instances ───────────────────────────────────────────────────────
orchestrator = OfferAgentOrchestrator()
db = DatabaseManager()
vector_store = VectorStore()

# ─── LLM Client ────────────────────────────────────────────────────────────
llm_client = OpenAI(
    base_url=os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1"),
    api_key=os.getenv("LMSTUDIO_API_KEY", "lm-studio")
)

# ─── Intent + Keyword Classifier (single LLM call) ─────────────────────────

def classify_intent(user_input: str) -> tuple[str, str]:
    """Single LLM call: returns (intent, keyword)."""
    
    prompt = """You are a classifier. Given the user's message, output TWO things separated by a colon:
1. The intent: greeting, sync, reindex, search, or recommend
2. The search keyword: the specific bank/brand/product name. If none, write "all"

- greeting: User says hi/hello or casual conversation
- sync: User wants to fetch/load/check new emails from Gmail
- reindex: User wants to rebuild the vector index
- recommend: User wants to know which credit card to use for a purchase
- search: User asks about past emails, offers, or promotions

Examples:
"Hi there" → greeting:
"sync my emails" → sync:
"rebuild index" → reindex:
"SBI offers" → search:SBI
"ICICI bank promotions" → search:ICICI
"Amex Taj voucher expiry" → search:Taj
"best card for Amazon 5000" → recommend:Amazon
"what offers do I have" → search:all
"cashback on food delivery" → search:cashback food delivery
"travel deals" → search:travel deals

Reply with ONLY intent:keyword. Nothing else.

User message: """ + user_input

    try:
        response = llm_client.chat.completions.create(
            model="local-model",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=20
        )
        raw = response.choices[0].message.content.strip().lower().rstrip(".")
        
        if ":" in raw:
            parts = raw.split(":", 1)
            intent = parts[0].strip()
            keyword = parts[1].strip() if len(parts) > 1 else ""
        else:
            intent = raw
            keyword = ""
        
        valid = {"greeting", "sync", "reindex", "recommend", "search"}
        if intent not in valid:
            if "greet" in intent: intent = "greeting"
            elif "sync" in intent or "fetch" in intent: intent = "sync"
            elif "reindex" in intent or "rebuild" in intent: intent = "reindex"
            elif "recommend" in intent: intent = "recommend"
            else: intent = "search"
        
        return intent, keyword
        
    except Exception:
        normalized = user_input.strip().lower()
        if normalized in {"hi", "hello", "hey"}: return "greeting", ""
        if any(kw in normalized for kw in ["sync", "fetch", "load"]): return "sync", ""
        if any(kw in normalized for kw in ["reindex", "rebuild"]): return "reindex", ""
        if any(kw in normalized for kw in ["best card", "which card"]): return "recommend", ""
        return "search", ""


# ─── LLM Summarization ─────────────────────────────────────────────────────

def summarize_with_llm(user_question: str, email_data: str) -> str:
    """LLM summarizes real email data retrieved via semantic search."""
    system_prompt = """You are the Financial Offer Intelligence Agent.
You are given REAL email data retrieved from the user's inbox via semantic search.

RULES:
- Summarize the emails for the user. Show dates, subjects, senders, and key details.
- If a specific bank/topic is asked about, highlight the most relevant emails.
- Look for expiry dates or deadlines in the email body text.
- ONLY use the data below. NEVER invent information.
- Be helpful, concise, and conversational."""

    try:
        response = llm_client.chat.completions.create(
            model="local-model",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"User Question: {user_question}\n\nRetrieved Emails:\n{email_data}"}
            ],
            temperature=0.1
        )
        return response.choices[0].message.content or "I couldn't generate a response."
    except Exception as e:
        return f"Error communicating with LLM: {e}"


def recommend_with_llm(user_question: str, email_data: str) -> str:
    """LLM recommends best card based on semantically retrieved email offers."""
    system_prompt = """You are the Financial Offer Intelligence Agent.
Based on the REAL promotional email data retrieved below, recommend the best credit card 
for the user's purchase. Consider cashback, discounts, reward points, and caps.
ONLY use the data below. NEVER invent offers."""

    try:
        response = llm_client.chat.completions.create(
            model="local-model",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"User Question: {user_question}\n\nOffers:\n{email_data}"}
            ],
            temperature=0.1
        )
        return response.choices[0].message.content or "I couldn't generate a recommendation."
    except Exception as e:
        return f"Error communicating with LLM: {e}"


def format_semantic_results(results: list[dict]) -> str:
    """Formats ChromaDB semantic search results for the LLM."""
    if not results:
        return "NO EMAILS FOUND."
    parts = []
    for i, r in enumerate(results, 1):
        parts.append(
            f"--- Email {i} (similarity: {r['similarity']}) ---\n"
            f"Date: {r['date_received']}\n"
            f"From: {r['sender']}\n"
            f"Subject: {r['subject']}\n"
            f"Body:\n{r['body_preview']}"
        )
    return "\n\n".join(parts)


# ─── Main Chat Loop ────────────────────────────────────────────────────────

def chat_loop():
    console.print("[bold green]Financial Offer Intelligence Agent (RAG) is online![/bold green]")
    console.print(f"[dim]Vector DB: {vector_store.count()} emails indexed[/dim]")
    console.print("Commands: [cyan]sync[/cyan], [cyan]search[/cyan], [cyan]recommend[/cyan], [cyan]reindex[/cyan], [cyan]exit[/cyan]\n")
    
    while True:
        try:
            user_input = Prompt.ask("[bold blue]You[/bold blue]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold yellow]Goodbye![/bold yellow]")
            break
        
        if user_input.strip().lower() in ['exit', 'quit']:
            console.print("[bold yellow]Goodbye![/bold yellow]")
            break
        
        # ── LLM classifies intent + extracts keyword ──
        intent, keyword = classify_intent(user_input)
        console.print(f"[dim]  (intent={intent}, keyword={keyword or 'none'})[/dim]")
        
        # ── Greeting ──
        if intent == "greeting":
            console.print("\n[bold green]Agent:[/bold green] Hello! 👋 I'm your Financial Offer Agent (RAG-powered).\n"
                          "  • **sync emails** — pull new promotions from Gmail\n"
                          "  • **search** — semantic search across your emails\n"
                          "  • **recommend** — best card for a purchase\n"
                          "  • **reindex** — rebuild the vector search index\n")
            continue
        
        # ── Sync ──
        if intent == "sync":
            console.print("\n[dim cyan]  → Syncing & embedding emails...[/dim cyan]")
            new_count, account_count = orchestrator.sync_all_accounts()
            if new_count == -1:
                console.print("\n[bold green]Agent:[/bold green] Already synced today. Check again tomorrow!\n")
            else:
                console.print(f"\n[bold green]Agent:[/bold green] Synced & embedded {new_count} new emails "
                              f"from {account_count} account(s). "
                              f"Vector DB now has {vector_store.count()} emails indexed.\n")
            continue
        
        # ── Reindex ──
        if intent == "reindex":
            console.print("\n[dim cyan]  → Re-indexing all emails into vector DB...[/dim cyan]")
            count = orchestrator.reindex_vectors()
            console.print(f"\n[bold green]Agent:[/bold green] Re-indexed {count} emails. "
                          f"Vector DB now has {vector_store.count()} emails indexed.\n")
            continue
        
        # ── Recommend ──
        if intent == "recommend":
            search_query = keyword if keyword and keyword != "all" else user_input
            console.print(f"\n[dim cyan]  → Semantic search for '{search_query}'...[/dim cyan]")
            results = vector_store.search(search_query, top_k=10)
            email_data = format_semantic_results(results)
            
            console.print(f"[dim cyan]  → Found {len(results)} relevant emails. Analyzing...[/dim cyan]")
            answer = recommend_with_llm(user_input, email_data)
            console.print(f"\n[bold green]Agent:[/bold green] {answer}\n")
            continue
        
        # ── Search (default) ──
        search_query = keyword if keyword and keyword != "all" else user_input
        console.print(f"\n[dim cyan]  → Semantic search for '{search_query}'...[/dim cyan]")
        results = vector_store.search(search_query, top_k=10)
        email_data = format_semantic_results(results)
        
        if not results:
            console.print("\n[bold green]Agent:[/bold green] No emails indexed yet. Try 'sync emails' first, "
                          "then 'reindex' to build the search index.\n")
            continue
        
        console.print(f"[dim cyan]  → Found {len(results)} relevant emails. Summarizing...[/dim cyan]")
        answer = summarize_with_llm(user_input, email_data)
        console.print(f"\n[bold green]Agent:[/bold green] {answer}\n")


if __name__ == "__main__":
    try:
        chat_loop()
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Goodbye![/bold yellow]")
