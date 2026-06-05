import typer
from rich.console import Console
from rich.table import Table
from typing import Optional
from datetime import datetime

from agent4_gradio_rag.orchestrator import OfferAgentOrchestrator
from shared_core.database import DatabaseManager

app = typer.Typer(help="Financial Offer Intelligence Agent CLI (OOP Version)")
console = Console()

class CLIApp:
    """Typer CLI wrapper class."""
    
    def __init__(self):
        self.orchestrator = OfferAgentOrchestrator()
        self.db = DatabaseManager()

cli_instance = CLIApp()

@app.command()
def init():
    """Initialize the local database schemas."""
    cli_instance.db.initialize_schema()
    console.print("[green]Database schemas initialized successfully![/green]")

@app.command()
def add_account():
    """Authenticate a new Gmail account via OAuth."""
    console.print("[bold cyan]Starting Google OAuth Flow...[/bold cyan]")
    try:
        _, auth_email = cli_instance.orchestrator.collector.authenticate(force_new=True)
        console.print(f"[bold green]Successfully authenticated and added account: {auth_email}[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Failed to authenticate: {e}[/bold red]")

@app.command()
def list_accounts():
    """List all configured Gmail accounts."""
    accounts = cli_instance.orchestrator.collector.get_configured_accounts()
    if not accounts:
        console.print("[yellow]No accounts configured. Run `add-account` first.[/yellow]")
        return
        
    table = Table(title="Configured Accounts")
    table.add_column("Account Email", style="cyan")
    for account in accounts: table.add_row(account)
    console.print(table)

@app.command()
def sync(account: Optional[str] = typer.Option(None, help="Sync specific account email")):
    """Sync promotional offers from your inboxes."""
    accounts_to_sync = [account] if account else cli_instance.orchestrator.collector.get_configured_accounts()
    
    if not accounts_to_sync:
        console.print("[yellow]No accounts to sync. Add an account first.[/yellow]")
        return
        
    console.print(f"[bold]Starting sync for {len(accounts_to_sync)} account(s)...[/bold]")
    
    global_processed, global_added = 0, 0
    for acc in accounts_to_sync:
        console.print(f"Syncing [cyan]{acc}[/cyan]...")
        processed, added = cli_instance.orchestrator.sync_account(acc)
        console.print(f"  -> Processed {processed} new emails. Added {added} new offers.")
        global_processed += processed
        global_added += added
        
    console.print(f"[bold green]Sync complete! Total {global_added} new offers added from {global_processed} emails.[/bold green]")

@app.command()
def recommend(merchant: str, amount: float):
    """Find the best card to use for a specific purchase amount."""
    offers = cli_instance.orchestrator.get_recommendation(merchant, amount)
    
    if not offers:
        console.print(f"[yellow]No active offers found for {merchant} on a purchase of ₹{amount}.[/yellow]")
        return
        
    best_offer, best_savings = offers[0]
    console.print("\n[bold cyan]🔔 Available Offers:[/bold cyan]")
    
    table = Table()
    table.add_column("Card Name", style="magenta")
    table.add_column("Offer Type", style="blue")
    table.add_column("Discount %", justify="right")
    table.add_column("Max Cap", justify="right")
    table.add_column("Est. Savings", style="green", justify="right")
    table.add_column("Account Source", style="dim")
    
    for idx, (offer, savings) in enumerate(offers):
        table.add_row(
            f"{offer.card_name} {'⭐ BEST' if idx == 0 else ''}",
            offer.offer_type.capitalize(),
            f"{offer.discount_percent}%" if offer.discount_percent else "N/A",
            f"₹{offer.max_cashback}" if offer.max_cashback else "None",
            f"₹{savings}",
            offer.account_email
        )
        
    console.print(table)
    console.print(f"\n[bold green]➡️ BEST RECOMMENDATION: Use '{best_offer.card_name}' to save ₹{best_savings}[/bold green]\n")

@app.command()
def list_offers():
    """List all active offers in the datastore."""
    active_offers = cli_instance.db.get_all_offers()
    
    if not active_offers:
        console.print("[yellow]Database is empty.[/yellow]")
        return
        
    table = Table(title="All Active Offers")
    table.add_column("Merchant")
    table.add_column("Card")
    table.add_column("Discount")
    table.add_column("Expires On")
    table.add_column("Source Account")
    
    current_date = datetime.now()
    
    for offer in active_offers:
        status = "Active"
        if offer.valid_until and offer.valid_until < current_date:
            status = "[red]Expired[/red]"
            
        table.add_row(
            offer.merchant.capitalize(),
            offer.card_name,
            f"{offer.discount_percent}%",
            str(offer.valid_until.date()) if offer.valid_until else "No Expiry",
            offer.account_email
        )
        
    console.print(table)

if __name__ == "__main__":
    app()
