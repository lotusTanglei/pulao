"""
用户界面 (UI) 渲染模块

本模块负责 CLI 界面的渲染，使用 Rich 库实现美观的终端输出。

主要功能：
1. ASCII Logo 显示
2. 顶部状态栏（版本、提供商、模型、语言）
3. 命令帮助表格
4. 富文本面板渲染

依赖库：
- rich: 富文本终端输出库

视觉风格：
- 主色调：青色 (cyan)、蓝色 (blue)
- 强调色：黄色 (yellow)、绿色 (green)
"""

# ============ 第三方库导入 ============
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.layout import Layout
from rich import box

# ============ 本地模块导入 ============
from src import __version__  # 项目版本号
from src.i18n import t  # 国际化翻译函数

# 创建 Rich 控制台对象
console = Console()


# ============ ASCII Logo 定义 ============

PULAO_LOGO = r"""
  ____        _             
 |  _ \ _   _| | __ _  ___  
 | |_) | | | | |/ _` |/ _ \ 
 |  __/| |_| | | (_| | (_) |
 |_|    \__,_|_|\__,_|\___/ 
"""


# ============ 界面渲染函数 ============

def print_header(cfg):
    """
    打印程序顶部标题栏
    
    显示内容包括：
    1. ASCII Logo
    2. 当前配置信息（版本、提供商、模型、语言）
    3. 可用命令列表
    
    参数:
        cfg: 配置字典，包含 current_provider, model, language 等信息
    
    布局说明：
        - 左侧：ASCII Logo（青色粗体）
        - 右侧：信息表格（蓝色标签，黄色值）
        - 底部：命令帮助列表
    
    命令列表：
        - ! <command>: 执行 Shell 命令
        - deploy <instruction>: 部署中间件
        - config / setup: 配置提供商
        - providers: 列出所有提供商
        - use <name>: 切换提供商
        - add-provider <name>: 添加提供商
        - update-library: 更新模板库
        - exit / quit: 退出程序
    """
    # 清空控制台
    console.clear()
    
    # 获取当前配置信息
    current_provider = cfg.get("current_provider", "default")
    model = cfg.get("model", "unknown")
    language = cfg.get("language", "en")
    
    # 创建网格布局（无边框）
    grid = Table.grid(expand=True)
    grid.add_column(justify="left", ratio=1)
    grid.add_column(justify="right", ratio=1)
    
    # 左侧：ASCII Logo
    logo_text = Text(PULAO_LOGO, style="bold cyan")
    
    # 右侧：信息表格
    info_table = Table.grid(padding=(0, 2))
    info_table.add_column(justify="right", style="bold blue")
    info_table.add_column(justify="left", style="bold yellow")
    
    # 添加信息行
    info_table.add_row("Version :", f"v{__version__}")
    info_table.add_row("Provider :", current_provider)
    info_table.add_row("Model :", model)
    info_table.add_row("Language :", language)
    
    # 组合左右两部分
    grid.add_row(logo_text, info_table)
    
    # 包装成面板
    header_panel = Panel(
        grid,
        style="blue",
        border_style="cyan",
        title="[bold cyan]AI-Powered DevOps Assistant[/bold cyan]",
        title_align="center",
        padding=(0, 2)
    )
    
    console.print(header_panel)
    
    # 显示命令列表标题
    console.print(Text("Available Commands / 可用命令:", style="bold white"))
    
    # 创建命令表格
    cmd_table = Table(box=None, show_header=False, padding=(0, 2), expand=True)
    cmd_table.add_column(style="bold green", width=25)
    cmd_table.add_column(style="white")
    
    # 定义命令列表
    commands = [
        ("! <command>", "Execute shell command (e.g., '!ls') / 执行系统命令"),
        ("deploy <instruction>", "Deploy middleware (e.g., 'deploy redis') / 部署中间件"),
        ("config / setup", "Configure provider / 配置提供商"),
        ("providers", "List all providers / 列出所有提供商"),
        ("use <name>", "Switch provider / 切换提供商"),
        ("add-provider <name>", "Add new provider / 添加提供商"),
        ("update-library", "Update template library from GitHub / 更新模板库"),
        ("exit / quit", "Exit Pulao / 退出")
    ]
    
    # 添加命令到表格
    for cmd, desc in commands:
        cmd_table.add_row(f"• {cmd}", desc)
        
    console.print(cmd_table)
    
    # 分隔线
    console.print(Text("─" * console.width, style="dim blue"))
