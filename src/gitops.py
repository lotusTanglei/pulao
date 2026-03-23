"""
GitOps 模块

本模块负责 GitOps 工作流，包括：
1. Git 仓库集成
2. 配置版本控制
3. 环境管理
4. 自动同步机制

主要功能：
    - Git 仓库初始化和克隆
    - 配置文件版本管理
    - 多环境支持（dev/staging/prod）
    - 环境切换
    - 配置变更追踪
    - 自动同步和部署

依赖：
    - Git: 版本控制系统
    - Docker: 容器化部署
    - 配置管理：现有配置系统

使用场景：
    - 企业级配置管理
    - 多环境部署流程
    - 配置变更审计
    - 团队协作
"""

import subprocess
import json
import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src.config import CONFIG_DIR
from src.logger import logger
from src.docker_ops import deploy_compose

console = Console()

GITOPS_DIR = CONFIG_DIR / "gitops"
GITOPS_DIR.mkdir(parents=True, exist_ok=True)

ENVIRONMENTS = ["dev", "staging", "prod"]


@dataclass
class Environment:
    """环境配置数据类"""
    name: str
    branch: str
    config_path: str
    created_at: str
    last_sync: Optional[str] = None


@dataclass
class GitConfig:
    """Git 配置数据类"""
    repo_url: str
    branch: str
    local_path: str
    initialized: bool = False


@dataclass
class ChangeLog:
    """变更日志数据类"""
    id: str
    timestamp: str
    environment: str
    action: str  # init, clone, pull, push, deploy
    details: Dict
    user: str


# ============ Git 仓库管理 ============

def init_git_repo(repo_url: str, local_path: str) -> GitConfig:
    """
    初始化 Git 仓库
    
    参数:
        repo_url: Git 仓库地址
        local_path: 本地存储路径
    
    返回:
        Git 配置对象
    """
    try:
        if not os.path.exists(local_path):
            os.makedirs(local_path, parents=True, exist_ok=True)
        
        result = subprocess.run(
            ["git", "init"],
            cwd=local_path,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            return GitConfig(
                repo_url=repo_url,
                branch="main",
                local_path=local_path,
                initialized=False
            )
        
        # 添加远程仓库
        result = subprocess.run(
            ["git", "remote", "add", "origin", repo_url],
            cwd=local_path,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            # 保存配置
            config = GitConfig(
                repo_url=repo_url,
                branch="main",
                local_path=local_path,
                initialized=True
            )
            save_git_config(config)
            
            logger.info(f"Git repo initialized: {repo_url}")
            return config
        else:
            raise Exception(f"Failed to add remote: {result.stderr}")
            
    except Exception as e:
        raise Exception(f"Git initialization failed: {str(e)}")


def clone_git_repo(repo_url: str, local_path: str, branch: str = "main") -> str:
    """
    克隆 Git 仓库
    
    参数:
        repo_url: Git 仓库地址
        local_path: 本地存储路径
        branch: 分支名称
    
    返回:
        操作结果字符串
    """
    try:
        if os.path.exists(local_path):
            return f"本地路径已存在: {local_path}"
        
        result = subprocess.run(
            ["git", "clone", "-b", branch, repo_url, local_path],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0:
            # 更新配置
            config = GitConfig(
                repo_url=repo_url,
                branch=branch,
                local_path=local_path,
                initialized=True
            )
            save_git_config(config)
            
            # 记录变更
            log_change("clone", "main", f"Cloned repo: {repo_url}")
            
            return f"仓库克隆成功: {local_path}"
        else:
            return f"克隆失败: {result.stderr}"
            
    except subprocess.TimeoutExpired:
        return f"克隆超时，仓库可能过大或网络问题"
    except Exception as e:
        return f"克隆异常: {str(e)}"


def pull_git_updates(local_path: str, branch: str = "main") -> str:
    """
    拉取 Git 更新
    
    参数:
        local_path: 本地仓库路径
        branch: 分支名称
    
    返回:
        操作结果字符串
    """
    try:
        result = subprocess.run(
            ["git", "pull", "origin", branch],
            cwd=local_path,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0:
            # 记录变更
            log_change("pull", branch, f"Pulled updates from origin/{branch}")
            
            return f"更新拉取成功"
        else:
            return f"拉取失败: {result.stderr}"
            
    except Exception as e:
        return f"拉取异常: {str(e)}"


def push_git_changes(local_path: str, branch: str = "main", message: str = "Update") -> str:
    """
    推送 Git 变更
    
    参数:
        local_path: 本地仓库路径
        branch: 分支名称
        message: 提交信息
    
    返回:
        操作结果字符串
    """
    try:
        # 先提交变更
        subprocess.run(
            ["git", "add", "."],
            cwd=local_path,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=local_path,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        # 推送变更
        result = subprocess.run(
            ["git", "push", "origin", branch],
            cwd=local_path,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0:
            # 记录变更
            log_change("push", branch, f"Pushed changes: {message}")
            
            return f"推送成功"
        else:
            return f"推送失败: {result.stderr}"
            
    except Exception as e:
        return f"推送异常: {str(e)}"


def get_git_status(local_path: str) -> Dict:
    """
    获取 Git 状态
    
    参数:
        local_path: 本地仓库路径
    
    返回:
        Git 状态信息字典
    """
    try:
        result = subprocess.run(
            ["git", "status", "--short", "--branch"],
            cwd=local_path,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        status_info = {
            "branch": "",
            "ahead": 0,
            "behind": 0,
            "modified": 0,
            "untracked": 0
        }
        
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if line.startswith("## branch"):
                    status_info["branch"] = line.replace("## branch", "").strip()
                elif line.startswith("## ahead"):
                    status_info["ahead"] = int(line.split()[-1])
                elif line.startswith("## behind"):
                    status_info["behind"] = int(line.split()[-1])
                elif line.startswith("## modified"):
                    status_info["modified"] = int(line.split()[-1])
                elif line.startswith("## untracked"):
                    status_info["untracked"] = int(line.split()[-1])
        
        return status_info
        
    except Exception as e:
        return {"error": str(e)}


# ============ 配置管理 ============

def save_git_config(config: GitConfig):
    """
    保存 Git 配置
    
    参数:
        config: Git 配置对象
    """
    config_file = GITOPS_DIR / "git_config.json"
    
    try:
        data = {
            "repo_url": config.repo_url,
            "branch": config.branch,
            "local_path": config.local_path,
            "initialized": config.initialized
        }
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Git config saved: {config_file}")
        
    except Exception as e:
        logger.error(f"Failed to save Git config: {e}")


def load_git_config() -> Optional[GitConfig]:
    """
    加载 Git 配置
    
    返回:
        Git 配置对象，如果不存在返回 None
    """
    config_file = GITOPS_DIR / "git_config.json"
    
    if not config_file.exists():
        return None
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return GitConfig(**data)
    except Exception as e:
        logger.error(f"Failed to load Git config: {e}")
        return None


# ============ 环境管理 ============

def create_environment(name: str, branch: str = "main", base_env: str = None) -> Environment:
    """
    创建新环境
    
    参数:
        name: 环境名称（dev/staging/prod）
        branch: 分支名称
        base_env: 基础环境（可选）
    
    返回:
        环境配置对象
    """
    envs = load_environments()
    
    if name in [e.name for e in envs]:
        return f"环境名称已存在: {name}"
    
    # 创建环境目录
    env_path = GITOPS_DIR / "environments" / name
    
    try:
        os.makedirs(env_path, parents=True, exist_ok=True)
        
        # 如果有基础环境，复制配置
        config_content = {}
        if base_env and base_env in envs:
            base_env_path = GITOPS_DIR / "environments" / base_env
            if base_env_path.exists():
                base_config = base_env_path / "config.yaml"
                if base_config.exists():
                    with open(base_config, 'r', encoding='utf-8') as f:
                        config_content = json.load(f)
        
        # 保存环境配置
        config_file = env_path / "config.yaml"
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_content, f, ensure_ascii=False, indent=2)
        
        # 更新环境列表
        envs.append(Environment(
            name=name,
            branch=branch,
            config_path=str(config_file),
            created_at=datetime.now().isoformat(),
            last_sync=None
        ))
        
        save_environments(envs)
        
        logger.info(f"Environment created: {name}")
        return envs[-1]
        
    except Exception as e:
        raise Exception(f"Failed to create environment: {str(e)}")


def load_environments() -> List[Environment]:
    """
    加载所有环境配置
    
    返回:
        环境列表
    """
    envs_file = GITOPS_DIR / "environments.json"
    
    if not envs_file.exists():
        return []
    
    try:
        with open(envs_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return [Environment(**env_data) for env_data in data.get("environments", [])]
    except Exception as e:
        logger.error(f"Failed to load environments: {e}")
        return []


def save_environments(envs: List[Environment]):
    """
    保存环境列表
    
    参数:
        envs: 环境列表
    """
    envs_file = GITOPS_DIR / "environments.json"
    
    try:
        data = {"environments": [e.__dict__ for e in envs]}
        with open(envs_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Environments saved: {len(envs)}")
        
    except Exception as e:
        logger.error(f"Failed to save environments: {e}")


def switch_environment(name: str) -> Optional[Environment]:
    """
    切换环境
    
    参数:
        name: 环境名称
    
    返回:
        切换后的环境配置，如果不存在返回 None
    """
    envs = load_environments()
    target_env = next((e for e in envs if e.name == name), None)
    
    if not target_env:
        return None
    
    # 更新当前环境
    for env in envs:
        env.last_sync = datetime.now().isoformat() if env.name == name else env.last_sync
    
    save_environments(envs)
    
    logger.info(f"Switched to environment: {name}")
    return target_env


def get_current_environment() -> Optional[Environment]:
    """
    获取当前环境
    
    返回:
        当前环境对象，如果未设置返回 None
    """
    envs = load_environments()
    
    for env in envs:
        if env.last_sync and env.last_sync == max(e.last_sync or "" for e in envs):
            return env
    
    return None


# ============ 变更日志 ============

def log_change(action: str, environment: str, details: str, user: str = "system"):
    """
    记录变更日志
    
    参数:
        action: 操作类型
        environment: 环境名称
        details: 详细信息
        user: 操作用户
    
    返回:
        无
    """
    log_file = GITOPS_DIR / "changelog.json"
    
    try:
        if not log_file.exists():
            data = {"changes": []}
        else:
            with open(log_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        
        change = ChangeLog(
            id=str(len(data.get("changes", [])) + 1),
            timestamp=datetime.now().isoformat(),
            environment=environment,
            action=action,
            details=details,
            user=user
        )
        
        data["changes"].append(change.__dict__)
        
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Change logged: {action} - {details}")
        
    except Exception as e:
        logger.error(f"Failed to log change: {e}")


def get_changelog(limit: int = 50) -> List[ChangeLog]:
    """
    获取变更日志
    
    参数:
        limit: 返回数量限制
    
    返回:
        变更日志列表
    """
    log_file = GITOPS_DIR / "changelog.json"
    
    if not log_file.exists():
        return []
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            changes = data.get("changes", [])
            return [ChangeLog(**change) for change in changes[-limit:]]
    except Exception as e:
        logger.error(f"Failed to load changelog: {e}")
        return []


# ============ 自动部署 ============

def deploy_from_git(environment: str) -> str:
    """
    从 Git 仓库部署到指定环境
    
    参数:
        environment: 环境名称
    
    返回:
        部署结果
    """
    env = switch_environment(environment)
    
    if not env:
        return f"环境不存在: {environment}"
    
    git_config = load_git_config()
    
    if not git_config or not git_config.initialized:
        return f"Git 仓库未初始化"
    
    # 拉取最新代码
    pull_result = pull_git_updates(git_config.local_path, git_config.branch)
    
    if "失败" in pull_result:
        return pull_result
    
    # 部署
    env_config_path = Path(env.config_path)
    
    if env_config_path.exists():
        compose_file = env_config_path / "docker-compose.yml"
        
        if compose_file.exists():
            try:
                result = deploy_compose(str(compose_file), env.name)
                
                # 记录变更
                log_change("deploy", env.name, f"Deployed from Git: {git_config.repo_url}")
                
                return result
            except Exception as e:
                return f"部署失败: {str(e)}"
        else:
            return f"配置文件不存在: {compose_file}"
    
    return f"环境 {environment} 已部署"


def sync_environment(environment: str) -> str:
    """
    同步环境到 Git
    
    参数:
        environment: 环境名称
    
    返回:
        同步结果
    """
    env = switch_environment(environment)
    
    if not env:
        return f"环境不存在: {environment}"
    
    git_config = load_git_config()
    
    if not git_config or not git_config.initialized:
        return f"Git 仓库未初始化"
    
    # 拉取最新代码
    pull_result = pull_git_updates(git_config.local_path, git_config.branch)
    
    if "失败" in pull_result:
        return pull_result
    
    # 部署
    deploy_result = deploy_from_git(environment)
    
    if "成功" in deploy_result:
        return f"环境 {environment} 已同步并部署"
    else:
        return f"同步失败: {deploy_result}"


# ============ 便捷函数 ============

def get_gitops_status() -> Dict:
    """
    获取 GitOps 状态
    
    返回:
        GitOps 状态信息
    """
    git_config = load_git_config()
    envs = load_environments()
    current_env = get_current_environment()
    
    status = {
        "git_configured": git_config is not None,
        "git_repo": git_config.repo_url if git_config else None,
        "git_branch": git_config.branch if git_config else None,
        "git_initialized": git_config.initialized if git_config else False,
        "environments_count": len(envs),
        "current_environment": current_env.name if current_env else None,
        "environments": [e.name for e in envs]
    }
    
    if git_config and git_config.initialized:
        try:
            git_status = get_git_status(git_config.local_path)
            status.update(git_status)
        except Exception as e:
            status["git_status_error"] = str(e)
    
    return status


def format_gitops_status(status: Dict) -> str:
    """
    格式化 GitOps 状态
    
    参数:
        status: GitOps 状态信息字典
    
    返回:
        格式化的状态字符串
    """
    lines = []
    lines.append(f"\n{'='*60}")
    lines.append("GitOps 状态")
    lines.append(f"{'='*60}")
    
    # Git 配置
    if status["git_configured"]:
        lines.append(f"  仓库: {status['git_repo']}")
        lines.append(f"  分支: {status['git_branch']}")
        lines.append(f"  状态: {'已初始化' if status['git_initialized'] else '未初始化'}")
    else:
        lines.append("  仓库: 未配置")
    
    # 环境信息
    lines.append(f"\n  环境数量: {status['environments_count']}")
    
    if status["current_environment"]:
        lines.append(f"  当前环境: {status['current_environment']}")
    else:
        lines.append("  当前环境: 未设置")
    
    if status["environments"]:
        lines.append(f"\n  环境列表:")
        for env_name in status["environments"]:
            marker = " → " if env_name == status["current_environment"] else ""
            lines.append(f"  {marker}{env_name}")
    
    # Git 状态
    if status.get("git_status"):
        gs = status["git_status"]
        lines.append(f"\n  Git 状态:")
        if "branch" in gs:
            lines.append(f"    分支: {gs['branch']}")
        if "ahead" in gs:
            lines.append(f"    领先提交: {gs['ahead']} 个")
        if "behind" in gs:
            lines.append(f"    落后提交: {gs['behind']} 个")
        if "modified" in gs:
            lines.append(f"    未提交变更: {gs['modified']} 个")
        if "untracked" in gs:
            lines.append(f"    未跟踪文件: {gs['untracked']} 个")
    elif status.get("git_status_error"):
        lines.append(f"    错误: {status['git_status_error']}")
    
    lines.append(f"\n{'='*60}")
    
    return "\n".join(lines)
