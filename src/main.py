import typer
from rich.console import Console
from rich.prompt import Prompt
from src.config import load_config, save_config
from src.i18n import t

# Note: We need to load config first to set the language, but config loading happens lazily in commands.
# However, Typer's help text is defined at module level. For now we use English for help text,
# or we could make it dynamic but that's complex. Let's stick to English for help text for now,
# or load config at module level (which might be slightly slow but acceptable).
load_config()

app = typer.Typer(help=t("cli_desc"))
console = Console()

@app.command(help=t("cli_config_help"))
def config():
    """
    Configure AI API settings (Key, URL, Model).
    """
    # Reload config to ensure language is set correctly
    current_config = load_config()
    
    console.print(f"[bold blue]{t('config_title')}[/bold blue]")
    
    api_key = Prompt.ask(t("enter_api_key"), default=current_config["api_key"] or None, password=True)
    base_url = Prompt.ask(t("enter_base_url"), default=current_config["base_url"])
    model = Prompt.ask(t("enter_model"), default=current_config["model"])
    
    path = save_config(api_key, base_url, model)
    console.print(f"[green]{t('config_saved', path=path)}[/green]")

from typing import Optional
import typer


@app.command(help=t("cli_deploy_help"))
def deploy(instruction: Optional[str] = typer.Argument(None)):
    """
    Deploy middleware using natural language.
    Example: ai-ops deploy "Deploy a high availability Redis cluster with 3 nodes"
    """
    from src.ai import process_deployment
    
    # If no instruction provided via CLI argument, ask interactively
    if not instruction:
        instruction = Prompt.ask(t("enter_instruction"))
    
    cfg = load_config()
    if not cfg["api_key"]:
        console.print(f"[red]{t('api_key_missing')}[/red]")
        raise typer.Exit(code=1)
        
    console.print(f"[bold cyan]{t('analyzing_request')}[/bold cyan] {instruction}")
    
    try:
        process_deployment(instruction, cfg)
    except Exception as e:
        console.print(f"[bold red]{t('error_prefix')}[/bold red] {str(e)}")
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()
