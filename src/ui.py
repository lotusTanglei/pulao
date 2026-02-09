from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.layout import Layout
from rich import box
from src import __version__
from src.i18n import t

console = Console()

# ASCII Logo
PULAO_LOGO = r"""
  ____        _             
 |  _ \ _   _| | __ _  ___  
 | |_) | | | | |/ _` |/ _ \ 
 |  __/| |_| | | (_| | (_) |
 |_|    \__,_|_|\__,_|\___/ 
"""

def print_header(cfg):
    """
    Print the persistent UI header with ASCII logo and status.
    """
    console.clear()
    
    current_provider = cfg.get("current_provider", "default")
    model = cfg.get("model", "unknown")
    language = cfg.get("language", "en")
    
    # Create the main layout table (invisible borders)
    grid = Table.grid(expand=True)
    grid.add_column(justify="left", ratio=1)
    grid.add_column(justify="right", ratio=1)
    
    # Left side: Logo
    logo_text = Text(PULAO_LOGO, style="bold cyan")
    
    # Right side: Info Table
    info_table = Table.grid(padding=(0, 2))
    info_table.add_column(justify="right", style="bold blue")
    info_table.add_column(justify="left", style="bold yellow")
    
    info_table.add_row("Version :", f"v{__version__}")
    info_table.add_row("Provider :", current_provider)
    info_table.add_row("Model :", model)
    info_table.add_row("Language :", language)
    
    grid.add_row(logo_text, info_table)
    
    # Wrap in a Panel
    header_panel = Panel(
        grid,
        style="blue",
        border_style="cyan",
        title="[bold cyan]AI-Powered DevOps Assistant[/bold cyan]",
        title_align="center",
        padding=(0, 2)
    )
    
    console.print(header_panel)
    
    # Command List
    console.print(Text("Available Commands / 可用命令:", style="bold white"))
    
    cmd_table = Table(box=None, show_header=False, padding=(0, 2), expand=True)
    cmd_table.add_column(style="bold green", width=25)
    cmd_table.add_column(style="white")
    
    # Add all commands
    commands = [
        ("deploy <instruction>", "Deploy middleware (e.g., 'deploy redis') / 部署中间件"),
        ("config / setup", "Configure provider / 配置提供商"),
        ("providers", "List all providers / 列出所有提供商"),
        ("use <name>", "Switch provider / 切换提供商"),
        ("add-provider <name>", "Add new provider / 添加提供商"),
        ("exit / quit", "Exit Pulao / 退出")
    ]
    
    for cmd, desc in commands:
        cmd_table.add_row(f"• {cmd}", desc)
        
    console.print(cmd_table)
    console.print(Text("─" * console.width, style="dim blue"))
