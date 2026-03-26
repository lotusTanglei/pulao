"""
AI 工具注册与调用模块

本模块负责将 Python 函数注册为 AI 可调用的工具（Tools），实现 ReAct Agent 模式。

主要功能：
1. 工具注册表 (ToolRegistry): 管理和注册可调用函数
2. 工具模式生成: 将 Python 函数转换为 OpenAI 兼容的工具模式
3. 工具执行: 根据 AI 返回的函数调用执行相应操作

支持的工具：
- deploy_service: 单机 Docker Compose 部署
- deploy_cluster_service: 集群多节点部署
- execute_command: 执行 Shell 命令

工具调用流程：
1. AI 分析用户请求
2. AI 返回函数调用请求（包含函数名和参数）
3. 从注册表获取对应函数
4. 执行函数并获取结果
5. 将结果返回给 AI 继续处理
"""

# ============ 标准库导入 ============
import json
import inspect
from typing import Callable, Dict, List, Any, Optional
from functools import wraps

# ============ 本地模块导入 ============
from src.tools.docker.docker_ops import deploy_compose, deploy_cluster  # Docker 部署操作
from src.tools.cluster.cluster import ClusterManager  # 集群管理
from src.tools.utils.library_manager import LibraryManager  # 模板库管理
from src.tools.system.system_ops import execute_shell_command, check_port_available as sys_check_port_available  # Shell 命令执行
from src.core.logger import logger  # 日志记录


# ============ 工具注册表类 ============

class ToolRegistry:
    """
    AI 工具注册表
    
    负责管理所有暴露给 AI 模型的函数。
    提供工具注册、模式生成和函数调用功能。
    
    核心功能：
        - 装饰器注册：使用 @registry.register 注册函数
        - 模式生成：将 Python 函数转换为 OpenAI 函数调用格式
        - 函数获取：根据名称获取已注册的函数
    
    工作原理：
        1. 使用装饰器 @registry.register 注册函数
        2. 自动从函数签名和文档字符串生成工具模式
        3. AI 模型返回函数调用时，通过 get_tool 获取并执行函数
    """
    
    def __init__(self):
        """初始化空注册表"""
        self._tools: Dict[str, Callable] = {}  # 函数名 -> 函数对象
        self._schemas: List[Dict[str, Any]] = []  # 工具模式列表

    def register(self, func: Callable):
        """
        注册函数为 AI 可调用工具
        
        参数:
            func: 要注册的函数对象
        
        返回:
            装饰器包装器函数
        
        执行流程：
            1. 生成函数工具模式
            2. 将函数添加到注册表
            3. 将模式添加到列表
            4. 返回包装器
        """
        # 生成工具模式
        schema = self._generate_schema(func)
        
        # 注册函数
        self._tools[func.__name__] = func
        self._schemas.append(schema)
        
        # 装饰器包装器
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper

    def get_tool(self, name: str) -> Optional[Callable]:
        """
        根据名称获取已注册的函数
        
        参数:
            name: 函数名称
        
        返回:
            函数对象，如果不存在返回 None
        """
        return self._tools.get(name)

    @property
    def schemas(self) -> List[Dict[str, Any]]:
        """
        获取所有工具的模式列表
        
        返回:
            OpenAI 函数调用格式的模式列表
        """
        return self._schemas

    def _generate_schema(self, func: Callable) -> Dict[str, Any]:
        """
        从函数生成 OpenAI 兼容的工具模式
        
        模式生成规则：
        1. 提取文档字符串第一行作为函数描述
        2. 遍历函数参数，提取参数名、类型、默认值
        3. 必填参数（无默认值）添加到 required 列表
        4. 参数类型映射：int->integer, bool->boolean, dict->object, list->array
        
        参数:
            func: Python 函数对象
        
        返回:
            OpenAI 函数调用格式的模式字典
        """
        # 提取文档字符串第一行作为描述
        doc = func.__doc__ or ""
        description = doc.strip().split("\n")[0]
        
        # 获取函数签名
        sig = inspect.signature(func)
        
        # 构建参数模式
        parameters = {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        # 遍历参数
        for name, param in sig.parameters.items():
            if name == "self": 
                continue
            
            # 类型推断
            param_type = "string"  # 默认类型
            if param.annotation == int:
                param_type = "integer"
            elif param.annotation == bool:
                param_type = "boolean"
            elif param.annotation == dict:
                param_type = "object"
            elif param.annotation == list:
                param_type = "array"
            
            # 添加参数属性
            parameters["properties"][name] = {
                "type": param_type,
                "description": f"Parameter {name}"
            }
            
            # 如果没有默认值，标记为必填
            if param.default == inspect.Parameter.empty:
                parameters["required"].append(name)
                
        # 返回完整的工具模式
        return {
            "type": "function",
            "function": {
                "name": func.__name__,
                "description": description,
                "parameters": parameters
            }
        }


# ============ 全局工具注册表实例 ============

# 创建全局注册表实例，供装饰器使用
registry = ToolRegistry()


# ============ 工具函数定义 ============

@registry.register
def deploy_service(yaml_content: str, project_name: str) -> str:
    """
    部署单机 Docker Compose 服务
    
    参数:
        yaml_content: docker-compose.yml 的完整内容
        project_name: 项目名称（用于目录命名）
    
    返回:
        执行结果字符串（成功或失败信息）
    """
    try:
        result = deploy_compose(yaml_content, project_name)
        if result.success:
            return f"Success: {result.message}\n{result.stdout}"
        else:
            return f"Error: {result.message}\n{result.stderr}"
    except Exception as e:
        return f"Exception: {str(e)}"


# ============ GitOps 工具 ============

from src.tools.utils.gitops import (
    init_git_repo,
    clone_git_repo,
    pull_git_updates,
    push_git_changes,
    get_git_status,
    create_environment,
    switch_environment,
    load_environments,
    deploy_from_git,
    sync_environment,
    get_gitops_status,
    format_gitops_status,
    get_changelog,
    load_git_config,
    GITOPS_DIR
)


@registry.register
def init_gitops(repo_url: str, local_path: str = None) -> str:
    """
    初始化 GitOps 工作流
    
    初始化 Git 仓库并配置远程地址，用于配置版本控制。
    
    参数:
        repo_url: Git 仓库地址
        local_path: 本地存储路径（可选，默认使用 ~/.pulao/gitops/repo）
    
    返回:
        初始化结果
    """
    try:
        if not local_path:
            local_path = str(GITOPS_DIR / "repo")
        
        config = init_git_repo(repo_url, local_path)
        
        if config.initialized:
            return f"GitOps 初始化成功\n仓库: {repo_url}\n本地路径: {local_path}"
        else:
            return f"GitOps 初始化失败"
    except Exception as e:
        return f"Exception: {str(e)}"


@registry.register
def clone_repo(repo_url: str, branch: str = "main") -> str:
    """
    克隆 Git 仓库
    
    克隆远程仓库到本地，用于获取配置文件。
    
    参数:
        repo_url: Git 仓库地址
        branch: 分支名称（默认 main）
    
    返回:
        克隆结果
    """
    try:
        local_path = str(GITOPS_DIR / "repo")
        return clone_git_repo(repo_url, local_path, branch)
    except Exception as e:
        return f"Exception: {str(e)}"


@registry.register
def pull_updates() -> str:
    """
    拉取 Git 更新
    
    从远程仓库拉取最新配置更新。
    
    返回:
        拉取结果
    """
    try:
        config = load_git_config()
        if not config:
            return "Git 仓库未配置，请先初始化"
        
        return pull_git_updates(config.local_path, config.branch)
    except Exception as e:
        return f"Exception: {str(e)}"


@registry.register
def push_changes(message: str = "Update configuration") -> str:
    """
    推送 Git 变更
    
    将本地配置变更推送到远程仓库。
    
    参数:
        message: 提交信息
    
    返回:
        推送结果
    """
    try:
        config = load_git_config()
        if not config:
            return "Git 仓库未配置，请先初始化"
        
        return push_git_changes(config.local_path, config.branch, message)
    except Exception as e:
        return f"Exception: {str(e)}"


@registry.register
def git_status() -> str:
    """
    查看 Git 状态
    
    显示当前 Git 仓库的状态，包括分支、变更等。
    
    返回:
        Git 状态信息
    """
    try:
        config = load_git_config()
        if not config:
            return "Git 仓库未配置，请先初始化"
        
        status = get_git_status(config.local_path)
        
        lines = ["Git 状态:"]
        if "branch" in status:
            lines.append(f"  分支: {status['branch']}")
        if "ahead" in status:
            lines.append(f"  领先提交: {status['ahead']} 个")
        if "behind" in status:
            lines.append(f"  落后提交: {status['behind']} 个")
        if "modified" in status:
            lines.append(f"  未提交变更: {status['modified']} 个")
        if "untracked" in status:
            lines.append(f"  未跟踪文件: {status['untracked']} 个")
        
        return "\n".join(lines)
    except Exception as e:
        return f"Exception: {str(e)}"


@registry.register
def create_env(name: str, branch: str = "main", base_env: str = None) -> str:
    """
    创建新环境
    
    创建部署环境（如 dev/staging/prod），支持配置继承。
    
    参数:
        name: 环境名称
        branch: Git 分支名称
        base_env: 基础环境名称（可选，用于继承配置）
    
    返回:
        创建结果
    """
    try:
        env = create_environment(name, branch, base_env)
        if isinstance(env, str):
            return env
        return f"环境创建成功: {env.name}\n分支: {env.branch}\n配置路径: {env.config_path}"
    except Exception as e:
        return f"Exception: {str(e)}"


@registry.register
def switch_env(name: str) -> str:
    """
    切换环境
    
    切换当前操作的部署环境。
    
    参数:
        name: 环境名称
    
    返回:
        切换结果
    """
    try:
        env = switch_environment(name)
        if not env:
            return f"环境不存在: {name}"
        return f"已切换到环境: {env.name}"
    except Exception as e:
        return f"Exception: {str(e)}"


@registry.register
def list_envs() -> str:
    """
    列出所有环境
    
    显示所有已配置的部署环境。
    
    返回:
        环境列表
    """
    try:
        envs = load_environments()
        
        if not envs:
            return "暂无环境配置"
        
        lines = [f"环境列表 (共 {len(envs)} 个):\n"]
        
        for env in envs:
            lines.append(f"  - {env.name}")
            lines.append(f"      分支: {env.branch}")
            lines.append(f"      创建时间: {env.created_at}")
            if env.last_sync:
                lines.append(f"      最后同步: {env.last_sync}")
        
        return "\n".join(lines)
    except Exception as e:
        return f"Exception: {str(e)}"


@registry.register
def deploy_env(environment: str) -> str:
    """
    部署到环境
    
    从 Git 仓库部署配置到指定环境。
    
    参数:
        environment: 环境名称
    
    返回:
        部署结果
    """
    try:
        return deploy_from_git(environment)
    except Exception as e:
        return f"Exception: {str(e)}"


@registry.register
def sync_env(environment: str) -> str:
    """
    同步环境
    
    从 Git 拉取最新配置并部署到指定环境。
    
    参数:
        environment: 环境名称
    
    返回:
        同步结果
    """
    try:
        return sync_environment(environment)
    except Exception as e:
        return f"Exception: {str(e)}"


@registry.register
def gitops_status() -> str:
    """
    GitOps 状态
    
    显示 GitOps 工作流的完整状态信息。
    
    返回:
        GitOps 状态报告
    """
    try:
        status = get_gitops_status()
        return format_gitops_status(status)
    except Exception as e:
        return f"Exception: {str(e)}"


@registry.register
def view_changelog(limit: int = 20) -> str:
    """
    查看变更日志
    
    显示最近的配置变更记录。
    
    参数:
        limit: 显示数量限制（默认20条）
    
    返回:
        变更日志列表
    """
    try:
        changes = get_changelog(limit)
        
        if not changes:
            return "暂无变更记录"
        
        lines = [f"变更日志 (最近 {len(changes)} 条):\n"]
        
        for change in changes:
            lines.append(f"[{change.timestamp}] {change.action}")
            lines.append(f"  环境: {change.environment}")
            lines.append(f"  详情: {change.details}")
            lines.append("")
        
        return "\n".join(lines)
    except Exception as e:
        return f"Exception: {str(e)}"


# ============ 安全扫描工具 ============

from src.tools.security.security_scan import (
    scan_image_with_trivy,
    format_scan_result,
    check_docker_security_config,
    format_security_config_result,
    detect_sensitive_info,
    comprehensive_security_check,
    format_comprehensive_report,
    check_trivy_installed,
    install_trivy_guide,
    scan_docker_image as run_scan_docker_image
)


@registry.register
def scan_docker_image(image_name: str) -> str:
    """
    扫描 Docker 镜像获取高危和严重漏洞 (HIGH/CRITICAL)
    
    使用 Trivy 扫描镜像中的已知漏洞。
    
    参数:
        image_name: 镜像名称（如 nginx:latest）
    
    返回:
        漏洞扫描报告或错误信息
    """
    try:
        return run_scan_docker_image(image_name)
    except Exception as e:
        return f"Exception: {str(e)}"


@registry.register
def scan_image(image_name: str) -> str:
    """
    扫描 Docker 镜像漏洞
    
    使用 Trivy 扫描镜像中的已知漏洞，包括操作系统包和依赖库。
    
    参数:
        image_name: 镜像名称（如 nginx:latest）
    
    返回:
        漏洞扫描报告
    """
    try:
        if not check_trivy_installed():
            return f"Trivy 未安装，无法扫描镜像。\n\n安装指南:\n{install_trivy_guide()}"
        
        result = scan_image_with_trivy(image_name)
        return format_scan_result(result, show_details=True)
    except Exception as e:
        return f"Exception: {str(e)}"


@registry.register
def check_docker_security() -> str:
    """
    检查 Docker 安全配置
    
    检查 Docker 守护进程和运行时安全配置，包括：
    - 守护进程配置
    - 特权容器检测
    - 用户权限配置
    
    返回:
        安全配置检查报告
    """
    try:
        results = check_docker_security_config()
        return format_security_config_result(results)
    except Exception as e:
        return f"Exception: {str(e)}"


@registry.register
def detect_secrets(text: str) -> str:
    """
    检测文本中的敏感信息
    
    扫描文本内容，检测可能泄露的敏感信息，如密码、API Key 等。
    
    参数:
        text: 要检测的文本内容
    
    返回:
        检测结果
    """
    try:
        findings = detect_sensitive_info(text)
        if not findings:
            return "未检测到敏感信息"
        
        lines = [f"检测到 {len(findings)} 处敏感信息:\n"]
        for i, finding in enumerate(findings, 1):
            lines.append(f"  [{i}] 类型: {finding['type']}")
            lines.append(f"      匹配: {finding['match']}")
        
        return "\n".join(lines)
    except Exception as e:
        return f"Exception: {str(e)}"


@registry.register
def security_audit(image_name: str = None) -> str:
    """
    执行综合安全审计
    
    执行全面的安全检查，包括 Docker 配置和镜像漏洞扫描。
    
    参数:
        image_name: 可选的镜像名称，如果提供则进行镜像扫描
    
    返回:
        综合安全审计报告
    """
    try:
        report = comprehensive_security_check(image_name)
        return format_comprehensive_report(report)
    except Exception as e:
        return f"Exception: {str(e)}"


# ============ 知识库工具 ============

from src.tools.utils.knowledge_base import (
    save_deployment_experience,
    save_troubleshooting_case,
    search_knowledge,
    list_knowledge,
    get_knowledge_stats,
    export_knowledge,
    get_knowledge_base
)


@registry.register
def save_experience(title: str, content: str, category: str = "deployment") -> str:
    """
    保存运维经验到知识库
    
    将部署方案、故障排查经验等保存到知识库，方便后续查询和复用。
    
    参数:
        title: 经验标题
        content: 经验内容
        category: 分类（deployment/troubleshooting/configuration/best_practice/security/other）
    
    返回:
        保存结果
    """
    try:
        kb = get_knowledge_base()
        entry = kb.add_entry(
            title=title,
            content=content,
            category=category,
            source="user"
        )
        return f"经验已保存: {entry.title} (ID: {entry.id}, 分类: {entry.category})"
    except Exception as e:
        return f"Exception: {str(e)}"


@registry.register
def save_case(title: str, problem: str, solution: str) -> str:
    """
    保存故障排查案例
    
    记录故障现象和解决方案，形成知识沉淀。
    
    参数:
        title: 案例标题
        problem: 问题描述
        solution: 解决方案
    
    返回:
        保存结果
    """
    try:
        return save_troubleshooting_case(title, problem, solution)
    except Exception as e:
        return f"Exception: {str(e)}"


@registry.register
def search_kb(query: str) -> str:
    """
    搜索知识库
    
    根据关键词或语义搜索知识库中的相关内容。
    
    参数:
        query: 搜索关键词
    
    返回:
        搜索结果
    """
    try:
        return search_knowledge(query)
    except Exception as e:
        return f"Exception: {str(e)}"


@registry.register
def list_kb(category: str = None) -> str:
    """
    列出知识库条目
    
    显示知识库中的所有条目，可按分类过滤。
    
    参数:
        category: 分类过滤（可选）
    
    返回:
        条目列表
    """
    try:
        return list_knowledge(category)
    except Exception as e:
        return f"Exception: {str(e)}"


@registry.register
def kb_stats() -> str:
    """
    获取知识库统计信息
    
    显示知识库的条目数量、分类分布等统计信息。
    
    返回:
        统计信息
    """
    try:
        return get_knowledge_stats()
    except Exception as e:
        return f"Exception: {str(e)}"


@registry.register
def export_kb(output_path: str = None) -> str:
    """
    导出知识库
    
    将知识库导出为 Markdown 格式文件。
    
    参数:
        output_path: 输出文件路径（可选，默认保存到配置目录）
    
    返回:
        导出结果
    """
    try:
        return export_knowledge(output_path)
    except Exception as e:
        return f"Exception: {str(e)}"


# ============ 运维诊断工具 ============

from src.tools.system.ops_diagnostics import (
    get_container_logs,
    analyze_logs,
    check_container_status,
    list_containers,
    get_container_stats,
    check_port_status,
    check_network_connectivity,
    check_dns_resolution,
    get_system_resources,
    check_disk_space,
    restart_container,
    stop_container,
    rollback_service,
    diagnose_service,
    format_diagnostic_report
)


@registry.register
def get_logs(container_name: str, lines: int = 100) -> str:
    """
    获取容器日志
    
    用于查看 Docker 容器的运行日志，帮助排查问题。
    
    参数:
        container_name: 容器名称或ID
        lines: 显示的日志行数（默认100行）
    
    返回:
        日志内容字符串
    """
    try:
        return get_container_logs(container_name, tail=lines)
    except Exception as e:
        return f"Exception: {str(e)}"


@registry.register
def check_container(container_name: str) -> str:
    """
    检查容器状态
    
    检查 Docker 容器的运行状态、健康检查状态和退出码。
    
    参数:
        container_name: 容器名称或ID
    
    返回:
        容器状态信息
    """
    try:
        result = check_container_status(container_name)
        status_info = f"状态: {result.status}\n信息: {result.message}"
        if result.details:
            status_info += f"\n详情: {result.details}"
        if result.recommendations:
            status_info += f"\n建议: {', '.join(result.recommendations)}"
        return status_info
    except Exception as e:
        return f"Exception: {str(e)}"


@registry.register
def list_docker_containers(all: bool = False) -> str:
    """
    列出所有 Docker 容器
    
    显示容器列表，包括名称、状态、镜像等信息。
    
    参数:
        all: 是否显示所有容器（包括停止的），默认只显示运行中的
    
    返回:
        容器列表字符串
    """
    try:
        containers = list_containers(all=all)
        if not containers:
            return "没有找到任何容器"
        
        lines = ["容器列表:"]
        for c in containers:
            name = c.get("Names", ["unknown"])[0] if isinstance(c.get("Names"), list) else c.get("Names", "unknown")
            status = c.get("State", "unknown")
            image = c.get("Image", "unknown")
            lines.append(f"  - {name}: {status} (镜像: {image})")
        
        return "\n".join(lines)
    except Exception as e:
        return f"Exception: {str(e)}"


@registry.register
def check_port(port: int) -> str:
    """
    检查端口占用状态
    
    检查指定端口是否被占用，以及被哪个进程占用。
    
    参数:
        port: 端口号
    
    返回:
        端口状态信息
    """
    try:
        result = check_port_status(port)
        return f"{result.message}\n状态: {result.status}"
    except Exception as e:
        return f"Exception: {str(e)}"


@registry.register
def check_network(target: str, port: int = None) -> str:
    """
    检查网络连通性
    
    测试到目标地址的网络连通性，支持 ICMP ping 和 TCP 端口测试。
    
    参数:
        target: 目标地址（IP或域名）
        port: 目标端口（可选，用于TCP连通性测试）
    
    返回:
        网络连通性测试结果
    """
    try:
        result = check_network_connectivity(target, port=port)
        return f"{result.message}\n状态: {result.status}"
    except Exception as e:
        return f"Exception: {str(e)}"


@registry.register
def check_dns(domain: str) -> str:
    """
    检查 DNS 解析
    
    测试域名是否能正确解析为 IP 地址。
    
    参数:
        domain: 域名
    
    返回:
        DNS 解析结果
    """
    try:
        result = check_dns_resolution(domain)
        return result.message
    except Exception as e:
        return f"Exception: {str(e)}"


@registry.register
def system_status() -> str:
    """
    获取系统资源状态
    
    显示 CPU、内存、磁盘和系统负载的使用情况。
    
    返回:
        系统资源状态信息
    """
    try:
        resources = get_system_resources()
        
        lines = ["系统资源状态:"]
        
        if resources.get("cpu"):
            lines.append(f"  CPU: 已使用 {resources['cpu'].get('used', 0):.1f}%")
        
        if resources.get("memory"):
            mem = resources["memory"]
            lines.append(f"  内存: {mem.get('used_mb', 0)}MB / {mem.get('total_mb', 0)}MB ({mem.get('used_percent', 0)}%)")
        
        if resources.get("disk"):
            disk = resources["disk"]
            lines.append(f"  磁盘: 已使用 {disk.get('used_percent', 0)}% ({disk.get('used', 0)} / {disk.get('total', 0)})")
        
        if resources.get("load"):
            load = resources["load"]
            lines.append(f"  负载: 1min={load.get('1min', 0):.2f}, 5min={load.get('5min', 0):.2f}, 15min={load.get('15min', 0):.2f}")
        
        return "\n".join(lines)
    except Exception as e:
        return f"Exception: {str(e)}"


@registry.register
def check_disk(path: str = "/", threshold: int = 80) -> str:
    """
    检查磁盘空间
    
    检查指定路径的磁盘使用情况，超过阈值会发出警告。
    
    参数:
        path: 检查路径（默认为根目录 /）
        threshold: 告警阈值百分比（默认80%）
    
    返回:
        磁盘空间信息
    """
    try:
        result = check_disk_space(path, threshold=threshold)
        return f"{result.message}\n状态: {result.status}"
    except Exception as e:
        return f"Exception: {str(e)}"


@registry.register
def restart_docker_container(container_name: str) -> str:
    """
    重启 Docker 容器
    
    用于修复容器故障，重启后容器会重新启动。
    
    参数:
        container_name: 容器名称或ID
    
    返回:
        重启结果
    """
    try:
        return restart_container(container_name)
    except Exception as e:
        return f"Exception: {str(e)}"


@registry.register
def stop_docker_container(container_name: str) -> str:
    """
    停止 Docker 容器
    
    停止正在运行的容器。
    
    参数:
        container_name: 容器名称或ID
    
    返回:
        停止结果
    """
    try:
        return stop_container(container_name)
    except Exception as e:
        return f"Exception: {str(e)}"


@registry.register
def rollback_deploy(project_name: str) -> str:
    """
    回滚服务部署
    
    停止并删除指定项目的所有容器，用于紧急回滚。
    
    参数:
        project_name: 项目名称
    
    返回:
        回滚结果
    """
    try:
        return rollback_service(project_name)
    except Exception as e:
        return f"Exception: {str(e)}"


@registry.register
def diagnose(service_name: str) -> str:
    """
    综合诊断服务
    
    对服务进行全面的健康检查，包括容器状态、日志分析、资源使用等，
    并生成诊断报告和修复建议。
    
    参数:
        service_name: 服务名称（容器名或项目名）
    
    返回:
        诊断报告
    """
    try:
        report = diagnose_service(service_name)
        return format_diagnostic_report(report)
    except Exception as e:
        return f"Exception: {str(e)}"

@registry.register
def update_template_library() -> str:
    """
    更新 Docker Compose 模板库
    
    从 GitHub/Gitee 拉取最新的服务模板。
    
    返回:
        操作结果消息
    """
    try:
        return LibraryManager.update_library()
    except Exception as e:
        return f"Exception: {str(e)}"

# ============ 集群管理工具 ============

@registry.register
def create_cluster(name: str) -> str:
    """
    创建新的集群
    
    参数:
        name: 集群名称
        
    返回:
        操作结果消息
    """
    try:
        return ClusterManager.create_cluster(name)
    except Exception as e:
        return f"Exception: {str(e)}"

@registry.register
def list_clusters() -> str:
    """
    列出所有可用集群及其状态
    
    返回:
        集群列表字符串
    """
    try:
        return ClusterManager.list_clusters()
    except Exception as e:
        return f"Exception: {str(e)}"

@registry.register
def switch_cluster(name: str) -> str:
    """
    切换当前操作的集群
    
    参数:
        name: 目标集群名称
        
    返回:
        操作结果消息
    """
    try:
        return ClusterManager.switch_cluster(name)
    except Exception as e:
        return f"Exception: {str(e)}"

@registry.register
def add_node(name: str, host: str, user: str, role: str = "worker", key_path: str = "") -> str:
    """
    向当前集群添加节点
    
    参数:
        name: 节点名称
        host: 节点主机地址 (IP/hostname)
        user: SSH 用户名
        role: 节点角色 (默认为 'worker')
        key_path: SSH 私钥路径 (可选)
        
    返回:
        操作结果消息
    """
    try:
        return ClusterManager.add_node(name, host, user, role, key_path)
    except Exception as e:
        return f"Exception: {str(e)}"

@registry.register
def remove_node(name: str) -> str:
    """
    从当前集群移除节点
    
    参数:
        name: 节点名称
        
    返回:
        操作结果消息
    """
    try:
        return ClusterManager.remove_node(name)
    except Exception as e:
        return f"Exception: {str(e)}"

@registry.register
def list_nodes() -> str:
    """
    列出当前集群的所有节点状态
    
    返回:
        节点列表字符串
    """
    try:
        return ClusterManager.list_nodes()
    except Exception as e:
        return f"Exception: {str(e)}"


@registry.register
def deploy_cluster_service(plan_content: dict, project_name: str) -> str:
    """
    部署多节点集群服务
    
    参数:
        plan_content: 节点名称到 docker-compose.yml 内容的映射字典
        project_name: 项目名称
    
    返回:
        部署结果字符串（成功数、失败数、错误列表）
    """
    try:
        success, fail, errors = deploy_cluster(plan_content, project_name)
        if fail == 0:
            return f"Cluster deployment success! ({success} nodes)"
        else:
            return f"Cluster deployment partial failure. Success: {success}, Fail: {fail}. Errors: {'; '.join(errors)}"
    except Exception as e:
        return f"Exception: {str(e)}"


@registry.register
def execute_command(command: str) -> str:
    """
    执行本地 Shell 命令
    
    用于检查系统状态、读取文件等操作。
    
    参数:
        command: 要执行的 Shell 命令字符串
    
    返回:
        命令执行结果（stdout 或 stderr）
    """
    try:
        logger.info(f"Executing shell command: {command}")
        import subprocess
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return f"Stdout: {result.stdout}"
        else:
            return f"Stderr: {result.stderr}"
    except Exception as e:
        return f"Exception: {str(e)}"


@registry.register
def check_port_available(port: int) -> str:
    """
    检查本地机器上的端口是否可用
    
    使用 socket 模块检查指定的端口在本地是否可用（未被占用）。
    
    参数:
        port: 要检查的端口号
    
    返回:
        端口是否可用的状态信息（包含可用或被占用的明确信息）
    """
    return sys_check_port_available(port)

