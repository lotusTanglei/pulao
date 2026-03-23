"""
Docker 环境检测与配置模块

本模块负责：
1. 检测 Docker 是否已安装并运行
2. 提供 Docker 安装引导
3. 配置 Docker 镜像加速源（国内加速）
4. 检测 Docker Compose 是否可用

使用场景：
    - 应用启动时自动检测环境
    - 用户主动检查环境状态
    - 配置镜像加速
"""

import subprocess
import platform
import os
import shutil
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass

from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.table import Table

from src.config import CONFIG_DIR
from src.logger import logger

console = Console()


@dataclass
class DockerStatus:
    """Docker 状态信息"""
    docker_installed: bool = False
    docker_running: bool = False
    docker_version: str = ""
    compose_installed: bool = False
    compose_version: str = ""
    compose_command: str = ""  # "docker compose" 或 "docker-compose"


# ============ Docker 镜像源配置 ============

MIRROR_SOURCES = {
    "aliyun": {
        "name": "阿里云镜像加速",
        "url": "https://registry.cn-hangzhou.aliyuncs.com",
        "description": "推荐华东地区用户使用"
    },
    "tencent": {
        "name": "腾讯云镜像加速",
        "url": "https://mirror.ccs.tencentyun.com",
        "description": "推荐华南地区用户使用"
    },
    "ustc": {
        "name": "中科大镜像加速",
        "url": "https://docker.mirrors.ustc.edu.cn",
        "description": "教育网用户推荐"
    },
    "163": {
        "name": "网易镜像加速",
        "url": "https://hub-mirror.c.163.com",
        "description": "稳定可靠"
    },
    "dockerhub": {
        "name": "Docker Hub（官方源）",
        "url": "https://registry-1.docker.io",
        "description": "官方源，国内可能较慢"
    }
}


# ============ Docker 检测函数 ============

def check_docker() -> DockerStatus:
    """
    检测 Docker 环境状态
    
    返回:
        DockerStatus 对象，包含 Docker 和 Docker Compose 的状态信息
    """
    status = DockerStatus()
    
    # 检测 Docker 是否安装
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            status.docker_installed = True
            status.docker_version = result.stdout.strip()
            logger.info(f"Docker installed: {status.docker_version}")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.warning("Docker not found")
        return status
    
    # 检测 Docker 是否运行
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            status.docker_running = True
            logger.info("Docker daemon is running")
        else:
            logger.warning("Docker daemon is not running")
    except subprocess.TimeoutExpired:
        logger.warning("Docker daemon check timeout")
    
    # 检测 Docker Compose（优先检测新版本 docker compose）
    try:
        result = subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            status.compose_installed = True
            status.compose_version = result.stdout.strip()
            status.compose_command = "docker compose"
            logger.info(f"Docker Compose (v2): {status.compose_version}")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    # 如果新版本不可用，检测旧版本 docker-compose
    if not status.compose_installed:
        try:
            result = subprocess.run(
                ["docker-compose", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                status.compose_installed = True
                status.compose_version = result.stdout.strip()
                status.compose_command = "docker-compose"
                logger.info(f"Docker Compose (v1): {status.compose_version}")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            logger.warning("Docker Compose not found")
    
    return status


def is_docker_ready() -> bool:
    """
    检查 Docker 环境是否就绪
    
    返回:
        True 如果 Docker 已安装、运行且 Compose 可用
    """
    status = check_docker()
    return status.docker_installed and status.docker_running and status.compose_installed


def get_compose_command() -> Optional[str]:
    """
    获取可用的 Docker Compose 命令
    
    返回:
        "docker compose" 或 "docker-compose"，如果都不可用返回 None
    """
    status = check_docker()
    return status.compose_command if status.compose_installed else None


# ============ Docker 安装引导 ============

INSTALL_GUIDES = {
    "Darwin": {
        "method": "Homebrew",
        "commands": [
            "brew install --cask docker",
        ],
        "post_install": "打开 Docker Desktop 应用并完成初始化设置",
        "url": "https://docs.docker.com/desktop/install/mac-install/"
    },
    "Linux": {
        "method": "官方脚本",
        "commands": [
            "curl -fsSL https://get.docker.com | sh",
            "sudo usermod -aG docker $USER",
        ],
        "post_install": "注销并重新登录以使用户组生效，然后启动 Docker 服务",
        "url": "https://docs.docker.com/engine/install/"
    },
    "Windows": {
        "method": "Docker Desktop",
        "commands": [],
        "post_install": "下载并安装 Docker Desktop for Windows",
        "url": "https://docs.docker.com/desktop/install/windows-install/"
    }
}


def print_docker_status(status: DockerStatus):
    """打印 Docker 状态信息"""
    table = Table(title="Docker 环境状态")
    table.add_column("组件", style="cyan")
    table.add_column("状态", style="green")
    table.add_column("版本信息")
    
    # Docker 状态
    if status.docker_installed:
        docker_status = "[green]✓ 已安装[/green]"
        if status.docker_running:
            docker_status += " [green]运行中[/green]"
        else:
            docker_status += " [yellow]未运行[/yellow]"
    else:
        docker_status = "[red]✗ 未安装[/red]"
    
    table.add_row("Docker", docker_status, status.docker_version or "-")
    
    # Docker Compose 状态
    if status.compose_installed:
        compose_status = f"[green]✓ 已安装[/green] ({status.compose_command})"
    else:
        compose_status = "[red]✗ 未安装[/red]"
    
    table.add_row("Docker Compose", compose_status, status.compose_version or "-")
    
    console.print(table)


def print_install_guide():
    """打印 Docker 安装引导"""
    system = platform.system()
    guide = INSTALL_GUIDES.get(system)
    
    if not guide:
        console.print(f"[yellow]未找到 {system} 系统的安装指南[/yellow]")
        console.print("请访问: https://docs.docker.com/get-docker/")
        return
    
    console.print(Panel.fit(
        f"[bold blue]Docker 安装指南 ({system})[/bold blue]\n\n"
        f"安装方式: {guide['method']}\n\n"
        f"安装命令:\n" + "\n".join([f"  [cyan]{cmd}[/cyan]" for cmd in guide['commands']]) + "\n\n"
        f"安装后操作: {guide['post_install']}\n\n"
        f"详细文档: [link]{guide['url']}[/link]",
        title="Docker 安装引导"
    ))


def guide_docker_setup() -> bool:
    """
    引导用户安装和配置 Docker
    
    返回:
        True 如果环境就绪，False 如果需要用户手动操作
    """
    status = check_docker()
    print_docker_status(status)
    
    if status.docker_installed and status.docker_running and status.compose_installed:
        console.print("\n[green]✓ Docker 环境已就绪！[/green]")
        return True
    
    console.print("\n[yellow]Docker 环境未就绪，需要安装或配置[/yellow]")
    
    # Docker 未安装
    if not status.docker_installed:
        if Confirm.ask("\n是否查看 Docker 安装指南？", default=True):
            print_install_guide()
        return False
    
    # Docker 未运行
    if not status.docker_running:
        console.print("\n[yellow]Docker 已安装但未运行[/yellow]")
        
        system = platform.system()
        if system == "Linux":
            if Confirm.ask("是否尝试启动 Docker 服务？", default=True):
                try:
                    subprocess.run(["sudo", "systemctl", "start", "docker"], check=True)
                    console.print("[green]Docker 服务已启动[/green]")
                    status = check_docker()
                    print_docker_status(status)
                except subprocess.CalledProcessError as e:
                    console.print(f"[red]启动失败: {e}[/red]")
                    console.print("请手动运行: sudo systemctl start docker")
                    return False
        elif system == "Darwin":
            console.print("[yellow]请打开 Docker Desktop 应用[/yellow]")
            return False
        else:
            console.print("[yellow]请手动启动 Docker 服务[/yellow]")
            return False
    
    # Docker Compose 未安装
    if not status.compose_installed:
        console.print("\n[yellow]Docker Compose 未安装[/yellow]")
        
        system = platform.system()
        if system == "Linux":
            if Confirm.ask("是否安装 Docker Compose 插件？", default=True):
                try:
                    subprocess.run([
                        "sudo", "apt-get", "update"
                    ], check=True)
                    subprocess.run([
                        "sudo", "apt-get", "install", "-y", 
                        "docker-compose-plugin"
                    ], check=True)
                    console.print("[green]Docker Compose 已安装[/green]")
                    status = check_docker()
                    print_docker_status(status)
                except subprocess.CalledProcessError:
                    console.print("[red]安装失败，请手动安装 Docker Compose[/red]")
                    return False
        else:
            console.print("[yellow]Docker Desktop 通常已包含 Docker Compose[/yellow]")
            console.print("请确保 Docker Desktop 版本是最新的")
            return False
    
    return is_docker_ready()


# ============ 镜像源配置 ============

def get_docker_config_dir() -> Path:
    """获取 Docker 配置目录"""
    system = platform.system()
    if system == "Darwin":
        return Path.home() / ".docker"
    elif system == "Linux":
        return Path("/etc/docker")
    elif system == "Windows":
        return Path.home() / ".docker"
    return Path.home() / ".docker"


def get_docker_daemon_config() -> Dict:
    """获取当前 Docker daemon 配置"""
    config_dir = get_docker_config_dir()
    config_file = config_dir / "daemon.json"
    
    if config_file.exists():
        try:
            import json
            with open(config_file, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read daemon.json: {e}")
    
    return {}


def set_mirror_source(mirror_key: str) -> bool:
    """
    配置 Docker 镜像加速源
    
    参数:
        mirror_key: 镜像源键名（如 "aliyun", "tencent"）
    
    返回:
        True 如果配置成功
    """
    if mirror_key not in MIRROR_SOURCES:
        console.print(f"[red]未知的镜像源: {mirror_key}[/red]")
        return False
    
    mirror = MIRROR_SOURCES[mirror_key]
    config_dir = get_docker_config_dir()
    config_file = config_dir / "daemon.json"
    
    # 读取现有配置
    config = get_docker_daemon_config()
    
    # 更新镜像源配置
    existing_mirrors = config.get("registry-mirrors", [])
    mirror_url = mirror["url"]
    
    # 如果镜像源已存在，移除它（避免重复）
    existing_mirrors = [m for m in existing_mirrors if m != mirror_url]
    
    # 将新镜像源添加到最前面
    existing_mirrors.insert(0, mirror_url)
    config["registry-mirrors"] = existing_mirrors
    
    # 写入配置文件
    try:
        config_dir.mkdir(parents=True, exist_ok=True)
        import json
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)
        
        console.print(f"[green]镜像源配置已保存: {config_file}[/green]")
        console.print(f"[green]当前镜像源: {mirror['name']} ({mirror_url})[/green]")
        
        # 提示重启 Docker
        console.print("\n[yellow]请重启 Docker 服务使配置生效：[/yellow]")
        if platform.system() == "Linux":
            console.print("  sudo systemctl restart docker")
        elif platform.system() == "Darwin":
            console.print("  在 Docker Desktop 中重启 Docker")
        
        return True
        
    except PermissionError:
        console.print("[red]权限不足，请使用 sudo 运行[/red]")
        return False
    except Exception as e:
        console.print(f"[red]配置失败: {e}[/red]")
        return False


def list_mirror_sources():
    """列出所有可用的镜像源"""
    table = Table(title="Docker 镜像加速源")
    table.add_column("键名", style="cyan")
    table.add_column("名称")
    table.add_column("地址")
    table.add_column("说明")
    
    for key, mirror in MIRROR_SOURCES.items():
        table.add_row(
            key,
            mirror["name"],
            mirror["url"],
            mirror["description"]
        )
    
    console.print(table)


def configure_mirror_interactive():
    """交互式配置镜像源"""
    console.print("\n[bold blue]Docker 镜像加速配置[/bold blue]")
    list_mirror_sources()
    
    # 显示当前配置
    current_config = get_docker_daemon_config()
    current_mirrors = current_config.get("registry-mirrors", [])
    if current_mirrors:
        console.print(f"\n当前已配置的镜像源: {current_mirrors}")
    else:
        console.print("\n[yellow]当前未配置镜像加速源[/yellow]")
    
    choice = Prompt.ask(
        "\n请选择镜像源",
        choices=list(MIRROR_SOURCES.keys()) + ["skip"],
        default="aliyun"
    )
    
    if choice != "skip":
        set_mirror_source(choice)


# ============ 环境检查入口 ============

def check_and_guide() -> bool:
    """
    检查 Docker 环境并引导用户配置
    
    这是主程序启动时调用的入口函数
    
    返回:
        True 如果环境就绪，False 如果需要用户操作
    """
    console.print("\n[bold]检查 Docker 环境...[/bold]")
    
    status = check_docker()
    
    if status.docker_installed and status.docker_running and status.compose_installed:
        print_docker_status(status)
        console.print("[green]✓ Docker 环境已就绪[/green]\n")
        return True
    
    print_docker_status(status)
    
    if not Confirm.ask("\nDocker 环境未就绪，是否进行配置？", default=True):
        console.print("[yellow]跳过 Docker 环境配置[/yellow]")
        console.print("[yellow]部分功能可能无法正常使用[/yellow]\n")
        return False
    
    result = guide_docker_setup()
    
    if result and Confirm.ask("\n是否配置镜像加速源（国内用户推荐）？", default=True):
        configure_mirror_interactive()
    
    return result
