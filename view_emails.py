import os
import sys
from rich.console import Console
from agent1_ingestion.sync_manager import SyncManager
from dotenv import load_dotenv

load_dotenv()
console = Console()

def main():
    console.print(f"[bold cyan]Starting Email Delta Sync...[/bold cyan]")
    
    manager = SyncManager()
    
    try:
        new_emails = manager.sync(limit_per_account=50)
    except Exception as e:
        console.print(f"[red]Error during sync: {e}[/red]")
        return
        
    count = len(new_emails)
    if count == 0:
        console.print("[yellow]No new emails found since last sync.[/yellow]")
        return

    console.print(f"[bold green]Successfully extracted {count} NEW emails![/bold green]")
    
    for idx, email in enumerate(new_emails):
        console.print(f"\n[bold green]--- New Email {idx + 1} ---[/bold green]")
        console.print(f"[bold]Account:[/bold] {email.account_email}")
        console.print(f"[bold]Bank:[/bold] {email.bank_name}")
        console.print(f"[bold]Subject:[/bold] {email.subject}")
        console.print(f"[bold]Date:[/bold] {email.date_received}")
        console.print(f"\n[bold dim]Cleaned Body Preview:[/bold dim]\n{email.clean_body[:300]}...")
        
    console.print(f"\n[bold green]These {count} emails have been saved to 'offers.db' and appended to 'extracted_emails.csv'.[/bold green]")

if __name__ == "__main__":
    main()
