import os
import sys
from rich.console import Console
from rich.prompt import Prompt, Confirm
from database import DatabaseManager
from gmail_collector import GmailCollector

console = Console()

def setup_environment():
    console.print("[bold cyan]Welcome to the Financial Offer Intelligence Agent Setup![/bold cyan]\n")
    
    # Check for credentials.json
    if not os.path.exists("credentials.json"):
        console.print("[bold red]ERROR: 'credentials.json' not found![/bold red]")
        console.print("Please download your OAuth Desktop Client ID from the Google Cloud Console.")
        console.print("Save it in this directory as 'credentials.json' and run 'python setup.py' again.")
        sys.exit(1)
        
    # Setup .env
    if not os.path.exists(".env"):
        console.print("[yellow]No .env file found. Let's create one.[/yellow]")
        lm_url = Prompt.ask("Enter your LMStudio Base URL", default="http://localhost:1234/v1")
        lm_key = Prompt.ask("Enter your LMStudio API Key", default="lm-studio")
        db_url = Prompt.ask("Enter your Database URL", default="sqlite:///offers.db")
        
        with open(".env", "w") as f:
            f.write(f"LMSTUDIO_BASE_URL={lm_url}\n")
            f.write(f"LMSTUDIO_API_KEY={lm_key}\n")
            f.write(f"DATABASE_URL={db_url}\n")
            
        console.print("[green]Created .env file successfully![/green]\n")
    else:
        console.print("[green]Found existing .env structure![/green]\n")

    # Initialize DB
    console.print("[cyan]Initializing Database Schemas...[/cyan]")
    db = DatabaseManager()
    db.initialize_schema()
    console.print("[green]Schema verified![/green]\n")
    
    # Add first Gmail Account
    collector = GmailCollector()
    accounts = collector.get_configured_accounts()
    
    if not accounts:
        if Confirm.ask("You haven't bound a Gmail account yet. Authenticate one now?"):
            try:
                console.print("[cyan]Opening browser for Google Login...[/cyan]")
                _, auth_email = collector.authenticate(force_new=True)
                console.print(f"[bold green]Successfully bound Account: {auth_email}[/bold green]\n")
            except Exception as e:
                console.print(f"[bold red]Failed to authenticate: {e}[/bold red]")
                sys.exit(1)
    else:
        console.print(f"[green]Found {len(accounts)} configured Gmail accounts.[/green]\n")
        if Confirm.ask("Would you like to bind an additional Gmail account?"):
            try:
                console.print("[cyan]Opening browser for Google Login...[/cyan]")
                _, auth_email = collector.authenticate(force_new=True)
                console.print(f"[bold green]Successfully bound Account: {auth_email}[/bold green]\n")
            except Exception as e:
                 console.print(f"[bold red]Failed to authenticate: {e}[/bold red]")
        
    console.print("[bold cyan]Setup Complete![/bold cyan]")
    console.print("You can verify your connection by running [bold]python chat.py[/bold] to speak with the agent or manually running [bold]docker-compose up[/bold]!")

if __name__ == "__main__":
    setup_environment()
