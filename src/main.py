"""
Pulao 主入口模块

本模块是 Pulao 应用的入口点，负责：
1. 构建 CLI 命令行界面（使用 Typer 框架）
2. 实现交互式 REPL 循环
3. 注册并处理所有子命令（配置、部署、集群管理等）

依赖模块：
    - typer: CLI 框架
    - rich: 终端美化输出
    - prompt_toolkit: 交互式输入
"""

# ============ 标准库导入 ============
import sys
from typing import Optional

# ============ 第三方库导入 ============
import typer
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.text import Text

# ============ 本地模块导入 ============
from src.config import (
    load_config, 
    save_config, 
    add_provider as add_provider_to_config, 
    switch_provider
)
from src.i18n import t  # 国际化翻译函数
from src import __version__  # 项目版本号
from src.ui import print_header  # 打印头部 UI
from src.system_ops import execute_shell_command  # 执行 Shell 命令
from src.logger import setup_logging  # 日志系统初始化

# ============ 日志系统初始化 ============
# 在应用启动早期初始化日志系统，确保所有模块都能正常记录日志
logger = setup_logging()

# ============ Readline 导入 ============
# 尝试导入 readline 以支持命令行历史记录和光标移动
# 如果不可用，尝试 gnureadline（Windows 兼容）
# 如果都没有，则使用默认的 input()
try:
    import readline
except ImportError:
    try:
        import gnureadline as readline
    except ImportError:
        pass

# ============ 预加载配置 ============
# 在应用启动时加载配置，确保所有命令都能访问配置信息
load_config()

# ============ 应用初始化 ============
# 创建 Typer 应用实例
# help 参数显示 CLI 描述（从 i18n 翻译中获取）
app = typer.Typer(help=t("cli_desc"), invoke_without_command=True)

# 创建 Rich 控制台对象，用于彩色输出
console = Console()


# ============ 主回调函数 ============
@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """
    Pulao 主入口回调函数
    
    当用户直接运行 'pulao' 不带任何子命令时触发此函数。
    它会启动交互式 REPL 循环，让用户输入自然语言指令。
    
    参数:
        ctx: Typer 上下文对象，包含命令行参数信息
    """
    if ctx.invoked_subcommand is None:
        repl_loop()


# ============ Prompt Toolkit 导入 ============
# 延迟导入以避免启动时的性能开销
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML


# ============ 交互式 REPL 循环 ============
def repl_loop():
    """
    交互式 Read-Eval-Print 循环
    
    这是 Pulao 的核心交互模式，提供一个持续运行的命令行界面。
    用户可以输入各种指令，包括：
    - 自然语言部署指令（如 "部署一个 Redis"）
    - Shell 命令（以 ! 开头）
    - 管理命令（config, providers, use 等）
    
    循环流程：
    1. 显示提示符，等待用户输入
    2. 解析用户输入，识别命令类型
    3. 执行相应的处理函数
    4. 循环直到用户退出
    
    全局变量:
        无（使用 load_config() 动态加载配置）
    
    异常处理:
        KeyboardInterrupt: Ctrl+C 中断，继续循环
        EOFError: Ctrl+D 退出，结束程序
    """
    # 加载当前配置
    cfg = load_config()
    
    # ============ 配置检查 ============
    # 检查 API Key 是否已配置，如果没有则提示用户配置
    if not cfg["api_key"]:
        console.print(f"[yellow]{t('api_key_missing')}[/yellow]")
        # 询问用户是否立即配置
        if Prompt.ask("Do you want to configure now? / 是否立即配置?", choices=["y", "n"]) == "y":
            config()  # 调用配置命令
            cfg = load_config()  # 重新加载配置
        else:
            return  # 用户取消，返回退出
    
    # 延迟导入 AI 处理模块，避免启动时不必要的开销
    from src.ai import process_deployment
    
    # ============ 打印头部信息 ============
    # 显示 ASCII Logo 和当前配置信息
    print_header(cfg)

    # ============ Prompt Session 设置 ============
    # 配置 prompt_toolkit 会话，支持命令历史和底部工具栏
    style = Style.from_dict({
        'bottom-toolbar': '#aaaaaa bg:#333333',  # 底部工具栏样式
        'prompt': 'ansicyan bold',  # 提示符样式（青色加粗）
    })
    
    def get_bottom_toolbar():
        """
        获取底部工具栏内容
        
        显示当前 AI 提供商、模型名称和退出提示。
        每次提示符显示时都会调用此函数，以反映最新的配置信息。
        
        返回:
            HTML 格式的字符串，显示在终端底部
        """
        provider = cfg.get("current_provider", "default")
        model = cfg.get("model", "unknown")
        return HTML(f' <b>Provider:</b> {provider} | <b>Model:</b> {model} | <b>Exit:</b> Ctrl+D ')

    # 创建 Prompt Session
    session = PromptSession(style=style)

    # ============ 主循环 ============
    while True:
        try:
            # 获取用户输入
            # 使用 prompt_toolkit 显示底部工具栏
            instruction = session.prompt(
                HTML('<b>&gt;</b> '), 
                bottom_toolbar=get_bottom_toolbar
            )
            
            # 忽略空输入
            if not instruction.strip():
                continue
            
            # ============ Shell 命令处理 ============
            # 以 ! 开头的指令被识别为 Shell 命令
            if instruction.strip().startswith("!"):
                cmd = instruction.strip()[1:].strip()  # 去掉 ! 和空白
                if cmd:
                    execute_shell_command(cmd)  # 执行 Shell 命令
                continue

            # ============ 命令解析 ============
            # 将输入分割为命令和参数
            cmd_parts = instruction.strip().split()
            cmd_name = cmd_parts[0].lower()  # 命令名称（小写）
            
            # ============ 退出命令 ============
            if cmd_name in ["exit", "quit"]:
                console.print("Bye!")
                break
                
            # ============ 配置命令 ============
            # config 或 setup：配置当前 AI 提供商
            if cmd_name in ["config", "setup"]:
                config()
                cfg = load_config()
                print_header(cfg)  # 刷新头部信息
                continue

            # ============ 列出提供商命令 ============
            if cmd_name == "providers":
                providers()
                continue
                
            # ============ 切换提供商命令 ============
            if cmd_name == "use":
                if len(cmd_parts) < 2:
                    console.print("[red]Usage: use <name_or_index>[/red]")
                    continue
                use(cmd_parts[1])
                cfg = load_config()
                print_header(cfg)  # 刷新头部信息
                continue
                
            # ============ 添加提供商命令 ============
            if cmd_name == "add-provider":
                if len(cmd_parts) < 2:
                    console.print("[red]Usage: add-provider <name>[/red]")
                    continue
                add_provider(cmd_parts[1])
                cfg = load_config()
                continue
                
            # ============ 部署指令 ============
            # 其他所有输入都被视为部署/运维指令，发送给 AI 处理
            try:
                process_deployment(instruction, cfg)
            except Exception as e:
                console.print(f"[bold red]{t('error_prefix')}[/bold red] {str(e)}")
                
        except KeyboardInterrupt:
            # Ctrl+C 中断，只是继续循环
            continue
        except EOFError:
            # Ctrl+D 退出
            console.print("\nBye!")
            break
        except Exception as e:
            # 其他系统错误
            console.print(f"[bold red]System Error:[/bold red] {e}")


# ============ CLI 命令：列出所有 AI 提供商 ============
@app.command(help="List all configured AI providers / 列出所有 AI 提供商")
def providers():
    """
    列出所有已配置的 AI 提供商
    
    显示每个提供商的名称、Base URL、模型名称。
    当前使用的提供商会标记为 * (current)。
    
    依赖:
        load_config(): 加载当前配置
    """
    cfg = load_config()
    current = cfg.get("current_provider", "default")
    providers_dict = cfg.get("providers", {})
    
    console.print("[bold]Configured Providers / 已配置的提供商:[/bold]")
    
    # 排序：default 排在最前面，其余按字母顺序
    names = sorted(providers_dict.keys())
    if "default" in names:
        names.remove("default")
        names.insert(0, "default")
        
    # 遍历显示每个提供商的信息
    for idx, name in enumerate(names, 1):
        details = providers_dict[name]
        status = "[green]* (current)[/green]" if name == current else ""
        console.print(f"  {idx}. [cyan]{name}[/cyan] {status}")
        console.print(f"     Base URL: {details.get('base_url')}")
        console.print(f"     Model:    {details.get('model')}")
        console.print("")


# ============ CLI 命令：添加新的 AI 提供商 ============
@app.command(name="add-provider", help="Add a new AI provider / 添加新的 AI 提供商")
def add_provider(name: str):
    """
    添加新的 AI 提供商
    
    交互式提示用户输入新提供商的配置信息：
    - API Key（密码形式输入，不显示）
    - Base URL（API 端点地址）
    - Model（模型名称）
    
    参数:
        name: 提供商名称（从命令行参数获取）
    
    保存后自动更新配置文件。
    """
    console.print(f"[bold blue]Adding Provider: {name}[/bold blue]")
    # 交互式输入各项配置
    api_key = Prompt.ask(t("enter_api_key"), password=True)
    base_url = Prompt.ask(t("enter_base_url"))
    model = Prompt.ask(t("enter_model"))
    
    # 调用配置模块保存提供商信息
    path = add_provider_to_config(name, api_key, base_url, model)
    console.print(f"[green]Provider '{name}' added successfully.[/green]")


# ============ CLI 命令：切换 AI 提供商 ============
@app.command(help="Switch to another AI provider / 切换 AI 提供商")
def use(name_or_index: str):
    """
    切换当前使用的 AI 提供商
    
    支持两种方式指定提供商：
    1. 按名称：如 "use deepseek"
    2. 按索引：如 "use 1"（对应 providers 命令显示的顺序）
    
    参数:
        name_or_index: 提供商名称或索引（从命令行参数获取）
    
    异常:
        ValueError: 提供商名称不存在
    """
    cfg = load_config()
    providers_dict = cfg.get("providers", {})
    
    # 准备索引查找列表
    names = sorted(providers_dict.keys())
    if "default" in names:
        names.remove("default")
        names.insert(0, "default")
    
    target_name = name_or_index
    
    # 检查输入是否为数字（索引）
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


# ============ CLI 命令：配置当前 AI 提供商 ============
@app.command(help=t("cli_config_help"))
def config():
    """
    配置当前 AI 提供商的 API 设置
    
    交互式修改当前使用的提供商的配置：
    - API Key：用于调用 AI 服务的密钥
    - Base URL：AI 服务的 API 端点地址
    - Model：使用的模型名称
    
    配置会自动保存到 ~/.pulao/config.yaml 文件中。
    """
    # 重新加载配置，确保语言设置正确
    current_config = load_config()
    current_provider_name = current_config.get("current_provider", "default")
    
    console.print(f"[bold blue]{t('config_title')} ({current_provider_name})[/bold blue]")
    
    # 交互式输入各项配置（显示默认值供用户确认或修改）
    api_key = Prompt.ask(t("enter_api_key"), default=current_config["api_key"] or None, password=True)
    base_url = Prompt.ask(t("enter_base_url"), default=current_config["base_url"])
    model = Prompt.ask(t("enter_model"), default=current_config["model"])
    
    # 保存到当前提供商
    add_provider_to_config(current_provider_name, api_key, base_url, model)
    console.print(f"[green]{t('config_saved', path='config.yaml')}[/green]")


# ============ 程序入口 ============
if __name__ == "__main__":
    """
    主程序入口点
    
    当直接运行 python main.py 时触发。
    会调用 Typer 的 app() 方法启动 CLI 应用。
    """
    app()
