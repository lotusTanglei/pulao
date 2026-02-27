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
from src.docker_ops import deploy_compose, deploy_cluster  # Docker 部署操作
from src.cluster import ClusterManager  # 集群管理
from src.library_manager import LibraryManager  # 模板库管理
from src.system_ops import execute_shell_command  # Shell 命令执行
from src.logger import logger  # 日志记录


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
