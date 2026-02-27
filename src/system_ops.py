"""
系统运维操作模块

本模块负责系统级别的运维操作，包括：
1. 收集系统信息（OS版本、Docker状态、运行中的容器、监听端口等）
2. 执行 Shell 命令

这些信息对于 AI 理解当前环境状态非常重要，会被包含在系统提示词中。

主要函数：
    - get_system_info(): 收集系统上下文信息
    - execute_shell_command(): 执行 Shell 命令并显示输出
"""

# ============ 标准库导入 ============
import subprocess
import platform
import socket
from typing import Optional

# ============ 第三方库导入 ============
from rich.console import Console

# ============ 本地模块导入 ============
from src.i18n import t  # 国际化翻译函数

# 创建 Rich 控制台对象
console = Console()


# ============ 系统信息收集函数 ============

def get_system_info() -> str:
    """
    收集系统信息用于 AI 上下文
    
    收集以下信息并返回格式化的字符串：
    1. 操作系统信息（名称、版本、架构）
    2. 内网 IP 地址
    3. Docker 版本和运行中的容器
    4. 监听的端口列表
    
    这些信息会被包含在 AI 的系统提示词中，帮助 AI 了解当前环境状态。
    
    返回:
        格式化的系统信息字符串，包含多行内容
    
    注意:
        - 容器列表最多显示 10 行，避免信息过长
        - 端口列表最多显示 10 行
        - 各项信息如果获取失败会显示 "Not detected"
    """
    info = []
    
    # ====== 1. 操作系统信息 ======
    try:
        info.append(f"OS: {platform.system()} {platform.release()} ({platform.machine()})")
    except:
        pass

    # ====== 2. 内网 IP 地址 ======
    try:
        hostname = socket.gethostname()
        ip_addr = socket.gethostbyname(hostname)
        info.append(f"Internal IP: {ip_addr}")
    except:
        pass

    # ====== 3. Docker 版本和容器 ======
    try:
        # 获取 Docker 版本
        docker_ver = subprocess.check_output(["docker", "--version"], text=True).strip()
        info.append(f"Docker: {docker_ver}")
        
        # 获取运行中的容器列表
        try:
            containers = subprocess.check_output(
                ["docker", "ps", "--format", "table {{.Names}}\t{{.Image}}\t{{.Ports}}"], 
                text=True
            ).strip()
            if containers:
                info.append("\n[Running Docker Containers]")
                # 限制显示前 10 行，避免过长
                lines = containers.split('\n')
                if len(lines) > 10:
                    info.append("\n".join(lines[:10]))
                    info.append(f"... ({len(lines)-10} more)")
                else:
                    info.append(containers)
        except:
            pass
    except:
        info.append("Docker: Not detected")
        
    # ====== 4. 监听端口 ======
    try:
        # 使用 lsof 命令获取监听端口
        # -i: 显示网络连接
        # -P: 不转换端口号
        # -n: 不解析主机名
        ports_output = subprocess.check_output("lsof -i -P -n | grep LISTEN | head -n 10", shell=True, text=True).strip()
        if ports_output:
            info.append("\n[Listening Ports (Host)]")
            info.append(ports_output)
    except:
        pass
        
    return "\n".join(info)


# ============ Shell 命令执行函数 ============

def execute_shell_command(command: str):
    """
    执行 Shell 命令并显示输出
    
    用于执行用户通过自然语言描述的系统命令。
    支持实时流式输出，即时显示命令执行过程中的输出。
    
    参数:
        command: 要执行的 Shell 命令字符串
    
    执行流程：
        1. 显示待执行的命令
        2. 使用 subprocess.Popen 异步执行
        3. 实时流式读取 stdout 并显示
        4. 执行完成后显示 stderr（如果有错误）
        5. 显示成功/失败状态
    
    注意:
        - 使用 shell=True 允许管道和复杂命令
        - 使用 executable="/bin/bash" 确保使用 bash
        - 危险操作（如删除）会在 ai.py 中由用户确认
    """
    # 显示待执行的命令
    console.print(f"[bold yellow]{t('executing_command')}:[/bold yellow] {command}")
    
    try:
        # 使用 Popen 异步执行，允许流式输出
        # shell=True: 允许管道、重定向等复杂命令
        # executable="/bin/bash": 指定使用 bash
        process = subprocess.Popen(
            command, 
            shell=True,
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True,
            executable="/bin/bash"
        )
        
        # 实时流式读取输出
        while True:
            output = process.stdout.readline()
            # 如果没有输出且进程已结束，退出循环
            if output == '' and process.poll() is not None:
                break
            # 逐行输出
            if output:
                console.print(output.strip())
                
        # 获取剩余的 stderr 输出
        stderr = process.stderr.read()
        if stderr:
            console.print(f"[red]{stderr}[/red]")
            
        # 显示执行结果状态
        if process.returncode == 0:
            console.print(f"[bold green]{t('command_success')}[/bold green]")
        else:
            console.print(f"[bold red]{t('command_failed')}[/bold red]")
            
    except Exception as e:
        console.print(f"[bold red]{t('error_executing_command')}[/bold red] {e}")
