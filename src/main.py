import typer
from rich.console import Console
from rich.prompt import Prompt
from src.config import load_config, save_config
from src.i18n import t
from typing import Optional

load_config()

app = typer.Typer(help=t("cli_desc"), invoke_without_command=True)
console = Console()

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """
    Pulao: AI-Powered DevOps Assistant
    """
    if ctx.invoked_subcommand is None:
        repl_loop()

def repl_loop():
    """Interactive Read-Eval-Print Loop"""
    console.print(f"[bold green]Pulao AI-Ops[/bold green] - {t('cli_desc')}")
    console.print("[dim]Type 'exit' or 'quit' to leave.[/dim]")
    
    cfg = load_config()
    
    # Check config first
    if not cfg["api_key"]:
        console.print(f"[yellow]{t('api_key_missing')}[/yellow]")
        if Prompt.ask("Do you want to configure now? / 是否立即配置?", choices=["y", "n"]) == "y":
            config()
            cfg = load_config() # Reload
        else:
            return

    from src.ai import process_deployment

    while True:
        try:
            instruction = Prompt.ask("\n[bold cyan]>[/bold cyan] ")
            
            if instruction.lower() in ["exit", "quit"]:
                console.print("Bye!")
                break
            
            if not instruction.strip():
                continue
                
            if instruction.lower() in ["config", "setup"]:
                config()
                cfg = load_config()
                continue
                
            # Process as deployment instruction
            try:
                process_deployment(instruction, cfg)
            except Exception as e:
                console.print(f"[bold red]{t('error_prefix')}[/bold red] {str(e)}")
                
        except KeyboardInterrupt:
            console.print("\nBye!")
            break
        except Exception as e:
            console.print(f"[bold red]System Error:[/bold red] {e}")

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

@app.command(help=t("cli_deploy_help"))
def deploy(instruction: Optional[str] = typer.Argument(None)):
    """
    Deploy middleware using natural language (One-off command).
    """
    from src.ai import process_deployment
    
    cfg = load_config()
    if not cfg["api_key"]:
        console.print(f"[red]{t('api_key_missing')}[/red]")
        raise typer.Exit(code=1)
        
    # If no instruction provided via CLI argument, ask interactively
    if not instruction:
        instruction = Prompt.ask(t("enter_instruction"))
        
    console.print(f"[bold cyan]{t('analyzing_request')}[/bold cyan] {instruction}")
    
    try:
        process_deployment(instruction, cfg)
    except Exception as e:
        console.print(f"[bold red]{t('error_prefix')}[/bold red] {str(e)}")
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()
