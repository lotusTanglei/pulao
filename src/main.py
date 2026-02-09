import typer
from rich.console import Console
from rich.prompt import Prompt
from src.config import load_config, save_config, add_provider as add_provider_to_config, switch_provider
from src.i18n import t
from typing import Optional
import sys
import io

# Force UTF-8 encoding for stdin/stdout/stderr to prevent decoding errors with Chinese input
if sys.stdin.encoding != 'utf-8':
    try:
        sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except Exception:
        pass

# Add readline for better input handling (history, deletion fix)
try:
    import readline
except ImportError:
    try:
        import gnureadline as readline
    except ImportError:
        pass

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
    console.print("-" * 50)
    console.print(f"[bold]Available Commands / 可用命令:[/bold]")
    console.print("  • [cyan]deploy <instruction>[/cyan]: Deploy middleware (e.g., 'deploy redis') / 部署中间件")
    console.print("  • [cyan]config[/cyan] or [cyan]setup[/cyan] : Configure current provider / 配置当前提供商")
    console.print("  • [cyan]providers[/cyan]          : List all providers / 列出所有提供商")
    console.print("  • [cyan]use <name>[/cyan]          : Switch provider / 切换提供商")
    console.print("  • [cyan]add-provider <name>[/cyan] : Add new provider / 添加提供商")
    console.print("  • [cyan]exit[/cyan] or [cyan]quit[/cyan]   : Exit Pulao / 退出")
    console.print("-" * 50)
    
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
            
            if not instruction.strip():
                continue
            
            cmd_parts = instruction.strip().split()
            cmd_name = cmd_parts[0].lower()
            
            if cmd_name in ["exit", "quit"]:
                console.print("Bye!")
                break
                
            if cmd_name in ["config", "setup"]:
                config()
                cfg = load_config()
                continue

            if cmd_name == "providers":
                providers()
                continue
                
            if cmd_name == "use":
                if len(cmd_parts) < 2:
                    console.print("[red]Usage: use <name_or_index>[/red]")
                    continue
                use(cmd_parts[1])
                cfg = load_config()
                continue
                
            if cmd_name == "add-provider":
                if len(cmd_parts) < 2:
                    console.print("[red]Usage: add-provider <name>[/red]")
                    continue
                add_provider(cmd_parts[1])
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

@app.command(help="List all configured AI providers / 列出所有 AI 提供商")
def providers():
    """List all configured providers."""
    cfg = load_config()
    current = cfg.get("current_provider", "default")
    providers_dict = cfg.get("providers", {})
    
    console.print("[bold]Configured Providers / 已配置的提供商:[/bold]")
    
    # Sort providers to ensure consistent indexing
    # Always put 'default' first if exists, then alphabetical
    names = sorted(providers_dict.keys())
    if "default" in names:
        names.remove("default")
        names.insert(0, "default")
        
    for idx, name in enumerate(names, 1):
        details = providers_dict[name]
        status = "[green]* (current)[/green]" if name == current else ""
        console.print(f"  {idx}. [cyan]{name}[/cyan] {status}")
        console.print(f"     Base URL: {details.get('base_url')}")
        console.print(f"     Model:    {details.get('model')}")
        console.print("")

@app.command(name="add-provider", help="Add a new AI provider / 添加新的 AI 提供商")
def add_provider(name: str):
    """Add a new provider."""
    console.print(f"[bold blue]Adding Provider: {name}[/bold blue]")
    api_key = Prompt.ask(t("enter_api_key"), password=True)
    base_url = Prompt.ask(t("enter_base_url"))
    model = Prompt.ask(t("enter_model"))
    
    path = add_provider_to_config(name, api_key, base_url, model)
    console.print(f"[green]Provider '{name}' added successfully.[/green]")

@app.command(help="Switch to another AI provider / 切换 AI 提供商")
def use(name_or_index: str):
    """Switch current provider by name or index."""
    cfg = load_config()
    providers_dict = cfg.get("providers", {})
    
    # Prepare list for index lookup
    names = sorted(providers_dict.keys())
    if "default" in names:
        names.remove("default")
        names.insert(0, "default")
    
    target_name = name_or_index
    
    # Check if input is a digit (index)
    if name_or_index.isdigit():
        idx = int(name_or_index)
        if 1 <= idx <= len(names):
            target_name = names[idx - 1]
        else:
            console.print(f"[red]Invalid index: {idx}. Valid range: 1-{len(names)}[/red]")
            return

    try:
        switch_provider(target_name)
        console.print(f"[green]Switched to provider: {target_name}[/green]")
    except ValueError as e:
        console.print(f"[red]{str(e)}[/red]")

@app.command(help=t("cli_config_help"))
def config():
    """
    Configure CURRENT AI API settings (Key, URL, Model).
    """
    # Reload config to ensure language is set correctly
    current_config = load_config()
    current_provider_name = current_config.get("current_provider", "default")
    
    console.print(f"[bold blue]{t('config_title')} ({current_provider_name})[/bold blue]")
    
    api_key = Prompt.ask(t("enter_api_key"), default=current_config["api_key"] or None, password=True)
    base_url = Prompt.ask(t("enter_base_url"), default=current_config["base_url"])
    model = Prompt.ask(t("enter_model"), default=current_config["model"])
    
    # Save to current provider
    add_provider_to_config(current_provider_name, api_key, base_url, model)
    console.print(f"[green]{t('config_saved', path='config.yaml')}[/green]")

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
