"""
Docker Compose 模板库管理器

本模块负责管理 Docker Compose 模板库，包括：
1. 内置模板库（随项目发布）
2. 用户模板库（从远程仓库更新）
3. 模板搜索和匹配

模板来源：
- 内置模板：位于 src/library 目录（打包在项目中）
- 用户模板：从 GitHub/Gitee 仓库克隆到 ~/.pulao/library

模板搜索策略：
1. 精确匹配：文件夹名称与请求的服务名完全一致
2. 模糊匹配：服务名包含在模板名中，或模板名包含在服务名中

仓库地址：
- GitHub: https://github.com/lotusTanglei/posehub.git
- Gitee: https://gitee.com/LOTUStudio/posehub.git
"""

# ============ 标准库导入 ============
import os
import shutil
import subprocess
import locale
from pathlib import Path
from typing import Optional, List

# ============ 第三方库导入 ============
from rich.console import Console

# 创建 Rich 控制台对象
console = Console()

# ============ 路径常量定义 ============

# 用户模板库目录：优先使用用户目录，失败时回退到内置
USER_LIBRARY_DIR = Path.home() / ".pulao" / "library"

# 内置模板库目录：随项目打包的模板
BUILTIN_LIBRARY_DIR = Path(__file__).parent / "library"

# Git 仓库地址
REPO_ZH = "https://gitee.com/LOTUStudio/posehub.git"  # Gitee（国内加速）
REPO_EN = "https://github.com/lotusTanglei/posehub.git"  # GitHub

# ============ 本地模块导入 ============
from src.config import load_config, CONFIG_DIR  # 配置加载


# ============ 模板库管理器类 ============

class LibraryManager:
    """
    Docker Compose 模板库管理器
    
    管理内置模板和用户模板的统一接口。
    模板库可以从远程 Git 仓库更新。
    
    核心功能：
        - 模板更新：从远程仓库克隆/拉取最新模板
        - 模板列表：列出所有可用的模板
        - 模板获取：根据服务名获取对应的 docker-compose.yml 内容
    
    搜索策略：
        1. 精确匹配：查找与服务名完全一致的文件夹
        2. 模糊匹配：查找名称相近的文件夹
    """
    
    # ============ 路径获取方法 ============
    
    @staticmethod
    def _get_library_dir() -> Path:
        """
        获取当前活跃的模板库目录
        
        优先级：
        1. 用户目录 (~/.pulao/library) 存在则使用
        2. 否则使用内置目录 (src/library)
        
        返回:
            模板库目录路径
        """
        USER_LIBRARY_DIR = CONFIG_DIR / "library"
        if USER_LIBRARY_DIR.exists():
            return USER_LIBRARY_DIR
        return BUILTIN_LIBRARY_DIR

    # ============ 仓库地址获取方法 ============
    
    @staticmethod
    def _get_repo_url() -> str:
        """
        根据配置或系统语言获取 Git 仓库地址
        
        获取优先级：
        1. 配置文件中的 language 设置
        2. 环境变量 LANG
        3. 系统默认语言
        
        如果语言包含 "zh" 或 "cn"，返回 Gitee 地址，否则返回 GitHub 地址。
        
        返回:
            Git 仓库 URL
        """
        try:
            # 步骤1: 检查配置文件
            cfg = load_config()
            lang = cfg.get("language", "")
            
            # 步骤2: 回退到环境变量
            if not lang:
                lang = os.environ.get('LANG', '')
            
            # 步骤3: 回退到系统语言
            if not lang:
                lang_code, _ = locale.getdefaultlocale()
                if lang_code:
                    lang = lang_code
            
            # 根据语言选择仓库
            if lang and ('zh' in lang.lower() or 'cn' in lang.lower()):
                return REPO_ZH
        except Exception:
            pass
        return REPO_EN

    # ============ 模板更新方法 ============
    
    @staticmethod
    def update_library() -> str:
        """
        更新模板库
        
        执行流程：
        1. 获取仓库 URL（根据语言设置）
        2. 检查用户目录是否存在
        3a. 如果存在：
            - 如果是 git 仓库且 URL 匹配，执行 git pull
            - 如果 URL 不匹配，备份旧目录并重新克隆
            - 如果不是 git 仓库，备份并重新克隆
        3b. 如果不存在，直接克隆
        
        失败处理：
        - 如果 GitHub 克隆失败，自动尝试 Gitee 镜像
        
        注意:
            - 使用 --depth=1 浅克隆，减少下载量
            - 克隆失败会保留备份
            
        返回:
            操作结果消息
        """
        USER_LIBRARY_DIR = CONFIG_DIR / "library"
        repo_url = LibraryManager._get_repo_url()
        console.print(f"[bold cyan]Updating template library from {repo_url}...[/bold cyan]")
        
        try:
            if USER_LIBRARY_DIR.exists():
                # 情况1: 目录存在且是 git 仓库
                if (USER_LIBRARY_DIR / ".git").exists():
                    # 检查远程 URL 是否匹配
                    try:
                        current_remote = subprocess.check_output(
                            ["git", "remote", "get-url", "origin"], 
                            cwd=USER_LIBRARY_DIR, 
                            text=True
                        ).strip()
                    except subprocess.CalledProcessError:
                        current_remote = ""

                    if current_remote == repo_url:
                        # URL 匹配，执行 pull 更新
                        console.print("[dim]Pulling latest changes...[/dim]")
                        subprocess.run(["git", "pull"], cwd=USER_LIBRARY_DIR, check=True)
                    else:
                        # URL 不匹配，备份并重新克隆
                        console.print(f"[yellow]Repository URL changed (Current: {current_remote}). Re-cloning...[/yellow]")
                        backup_path = str(USER_LIBRARY_DIR) + ".old"
                        if os.path.exists(backup_path):
                            if os.path.isdir(backup_path):
                                shutil.rmtree(backup_path)
                            else:
                                os.remove(backup_path)
                        shutil.move(str(USER_LIBRARY_DIR), backup_path)
                        console.print(f"[dim]Backed up old library to {backup_path}[/dim]")
                        subprocess.run(["git", "clone", "--depth", "1", repo_url, str(USER_LIBRARY_DIR)], check=True)
                else:
                    # 情况2: 目录存在但不是 git 仓库
                    console.print("[yellow]Library directory exists but is not a git repo. Backing up and re-cloning...[/yellow]")
                    shutil.move(str(USER_LIBRARY_DIR), str(USER_LIBRARY_DIR) + ".bak")
                    subprocess.run(["git", "clone", "--depth", "1", repo_url, str(USER_LIBRARY_DIR)], check=True)
            else:
                # 情况3: 目录不存在，直接克隆
                USER_LIBRARY_DIR.parent.mkdir(parents=True, exist_ok=True)
                console.print("[dim]Cloning repository...[/dim]")
                subprocess.run(["git", "clone", "--depth", "1", repo_url, str(USER_LIBRARY_DIR)], check=True)
                
            msg = f"Library updated successfully! Templates stored in: {USER_LIBRARY_DIR}"
            console.print(f"[bold green]{msg}[/bold green]")
            return msg
            
        except subprocess.CalledProcessError as e:
            # GitHub 失败时尝试 Gitee 镜像
            if repo_url == REPO_EN:
                console.print(f"[bold red]Failed to update from GitHub. Trying Gitee fallback...[/bold red]")
                try:
                    # 清理部分克隆的残留
                    if USER_LIBRARY_DIR.exists() and not (USER_LIBRARY_DIR / ".git").exists():
                         shutil.rmtree(str(USER_LIBRARY_DIR))
                    
                    # 如果目录存在但为空，删除它
                    if USER_LIBRARY_DIR.exists():
                        if not os.listdir(str(USER_LIBRARY_DIR)):
                            os.rmdir(str(USER_LIBRARY_DIR))
                    
                    # 尝试从 Gitee 克隆
                    console.print(f"[dim]Cloning from {REPO_ZH}...[/dim]")
                    subprocess.run(["git", "clone", "--depth", "1", REPO_ZH, str(USER_LIBRARY_DIR)], check=True)
                    msg = "Library updated successfully (using Gitee mirror)!"
                    console.print(f"[bold green]{msg}[/bold green]")
                    return msg
                except Exception as e2:
                    console.print(f"[bold red]Fallback failed:[/bold red] {e2}")

            msg = f"Failed to update library: {e}"
            console.print(f"[bold red]{msg}[/bold red]")
            return msg
        except Exception as e:
            msg = f"Error updating library: {e}"
            console.print(f"[bold red]{msg}[/bold red]")
            return msg

    # ============ 模板列表方法 ============
    
    @staticmethod
    def list_templates() -> List[str]:
        """
        列出所有可用的模板
        
        遍历模板库目录，查找包含 docker-compose.yaml 或 docker-compose.yml 的文件夹。
        
        返回:
            模板名称列表（按字母顺序排序）
        
        注意:
            - 只返回文件夹名称，不返回完整路径
            - 如果模板库不存在，返回空列表
        """
        lib_dir = LibraryManager._get_library_dir()
        if not lib_dir.exists():
            return []
            
        templates = []
        # 遍历目录查找包含 docker-compose 文件的文件夹
        for item in lib_dir.iterdir():
            if item.is_dir():
                if (item / "docker-compose.yaml").exists() or (item / "docker-compose.yml").exists():
                    templates.append(item.name)
        return sorted(templates)

    # ============ 模板获取方法 ============
    
    @staticmethod
    def get_template(service_name: str) -> Optional[str]:
        """
        获取指定服务的 docker-compose.yml 内容
        
        搜索策略：
        1. 精确匹配：查找与 service_name 完全一致的文件夹
        2. 模糊匹配：在所有模板中查找名称包含 service_name 的
        
        参数:
            service_name: 服务名称（如 "redis", "mysql", "nginx"）
        
        返回:
            docker-compose.yml 的内容字符串
            如果未找到返回 None
        
        注意:
            - 同时支持 .yaml 和 .yml 扩展名
            - 模糊匹配时会在控制台显示匹配的模板名
        """
        lib_dir = LibraryManager._get_library_dir()
        
        def try_read(d: Path) -> Optional[str]:
            """尝试读取目录中的 docker-compose 文件"""
            for name in ["docker-compose.yaml", "docker-compose.yml"]:
                f = d / name
                if f.exists():
                    return f.read_text(encoding="utf-8")
            return None

        # 策略1: 精确匹配
        target_dir = lib_dir / service_name
        if target_dir.exists():
            content = try_read(target_dir)
            if content: 
                return content
            
        # 策略2: 模糊匹配
        available = LibraryManager.list_templates()
        for tpl in available:
            if tpl in service_name.lower() or service_name.lower() in tpl:
                # 找到潜在匹配
                candidate_dir = lib_dir / tpl
                content = try_read(candidate_dir)
                if content:
                    console.print(f"[dim]Found matching template: {tpl}[/dim]")
                    return content
                    
        return None
