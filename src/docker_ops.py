"""
Docker 部署操作模块

本模块负责实际的 Docker 部署操作，包括：
1. 本机 Docker Compose 部署
2. 远程集群部署（通过 SSH）
3. 冲突检测（端口、容器名等）

主要功能：
    - 将 AI 生成的 YAML 配置写入文件
    - 执行 docker compose up -d 启动服务
    - 支持多节点集群部署
    - 部署前检查端口冲突

依赖模块：
    - remote_ops: SSH 远程操作
    - cluster: 集群管理
"""

# ============ 标准库导入 ============
import subprocess
import os
from pathlib import Path
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass

# ============ 本地模块导入 ============
from src.i18n import t  # 国际化翻译函数
from src.cluster import ClusterManager  # 集群管理
from src.remote_ops import RemoteExecutor, SSHError  # SSH 远程操作
from src.logger import logger  # 日志记录
from src.config import CONFIG_DIR  # 配置目录

# 部署目录：所有部署的 docker-compose 文件保存在此目录下
DEPLOY_DIR = CONFIG_DIR / "deployments"


# ============ 数据类定义 ============

@dataclass
class DeploymentResult:
    """
    部署结果数据类
    
    用于封装部署操作的结果信息，包括成功/失败状态、消息和输出。
    
    属性:
        success: 部署是否成功
        message: 结果描述信息
        stdout: 标准输出（可选）
        stderr: 标准错误输出（可选）
    """
    success: bool
    message: str
    stdout: Optional[str] = None
    stderr: Optional[str] = None


class DeploymentError(Exception):
    """部署错误异常基类"""
    pass


# ============ 本机部署函数 ============

def deploy_compose(yaml_content: str, project_name: str = "default") -> DeploymentResult:
    """
    本机 Docker Compose 部署
    
    将 AI 生成的 docker-compose.yml 内容写入文件，并在本机执行部署。
    
    执行流程：
        1. 清理项目名称（只保留安全字符）
        2. 创建项目目录
        3. 写入 docker-compose.yml 文件
        4. 执行 docker compose up -d 启动服务
    
    参数:
        yaml_content: docker-compose.yml 的内容字符串
        project_name: 项目名称，用于目录命名（默认 "default"）
    
    返回:
        DeploymentResult 对象，包含部署结果信息
    
    异常:
        DeploymentError: 部署过程中的错误
    """
    # 清理项目名称，只保留字母、数字、连字符和下划线
    # 避免目录名安全问题
    safe_name = "".join([c for c in project_name if c.isalnum() or c in "-_"]).strip()
    if not safe_name:
        safe_name = "default"
        
    # 构建项目目录路径
    project_dir = DEPLOY_DIR / safe_name
    project_dir.mkdir(parents=True, exist_ok=True)
    
    # docker-compose 文件路径
    compose_file = project_dir / "docker-compose.yml"
    
    try:
        # 步骤1: 写入 docker-compose.yml 文件
        with open(compose_file, "w", encoding="utf-8") as f:
            f.write(yaml_content)
        
        logger.info(f"Written compose file to {compose_file}")
        
        # 步骤2: 执行 docker compose up
        logger.info(f"Executing docker compose in {project_dir}")
        
        # 使用 docker compose 命令（新版本 Docker）
        cmd = ["docker", "compose", "up", "-d", "--remove-orphans"]
        
        # 执行命令
        process = subprocess.Popen(
            cmd, 
            cwd=project_dir, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        
        # 等待命令执行完成，获取输出
        stdout, stderr = process.communicate()
        
        if process.returncode == 0:
            # 部署成功
            logger.info("Local deployment success")
            return DeploymentResult(
                success=True,
                message=t('deployment_success'),
                stdout=stdout
            )
        else:
            # 部署失败
            logger.error(f"Local deployment failed: {stderr}")
            return DeploymentResult(
                success=False,
                message=t('deployment_failed'),
                stderr=stderr
            )
            
    except Exception as e:
        logger.error(f"Error executing compose: {e}")
        raise DeploymentError(f"{t('error_executing_compose')} {e}")


# ============ 集群部署函数 ============

def deploy_cluster(plan_content: Dict[str, str], project_name: str = "default") -> Tuple[int, int, List[str]]:
    """
    集群多节点部署
    
    将服务部署到多个远程节点。每个节点对应一个 docker-compose.yml 配置。
    
    执行流程：
        1. 加载当前集群节点列表
        2. 对所有目标节点进行预检查（SSH 连接测试）
        3. 遍历每个节点的配置，通过 SSH 远程部署
        4. 返回部署统计（成功数、失败数、错误列表）
    
    参数:
        plan_content: 节点名称到 YAML 配置的映射字典
                     格式: {"node_name1": "yaml_content1", "node_name2": "yaml_content2"}
        project_name: 项目名称（用于远程目录命名）
    
    返回:
        元组 (成功节点数, 失败节点数, 错误消息列表)
    
    异常:
        DeploymentError: 预检查失败（所有节点不可达）
    """
    logger.info(f"Starting Cluster Deployment: {project_name}")
    
    # 加载当前集群的节点列表
    nodes = ClusterManager.get_current_nodes()
    nodes_map = {n["name"]: n for n in nodes}
    
    # 步骤1: 预检查 - 验证所有目标节点的 SSH 连接
    failed_nodes = []
    for node_name in plan_content.keys():
        if node_name not in nodes_map:
            logger.warning(f"Node '{node_name}' not found in cluster")
            continue
        
        node = nodes_map[node_name]
        try:
            RemoteExecutor.check_connection(node)
        except SSHError as e:
            logger.warning(f"Pre-flight check failed for {node_name}: {e}")
            failed_nodes.append(node)
    
    # 如果有节点连接失败，中止部署
    if failed_nodes:
        error_msg = t("deploy_aborted_auth_fail")
        logger.error(f"Cluster deployment aborted: {len(failed_nodes)} nodes failed pre-flight check")
        raise DeploymentError(error_msg, failed_nodes)

    # 步骤2: 遍历部署
    success_count = 0
    fail_count = 0
    errors = []
    
    for node_name, yaml_content in plan_content.items():
        if node_name not in nodes_map:
            fail_count += 1
            continue
            
        node = nodes_map[node_name]
        try:
            # 调用远程部署函数
            RemoteExecutor.deploy_compose(node, yaml_content, project_name)
            success_count += 1
        except SSHError as e:
            logger.error(f"Deployment failed for {node_name}: {e}")
            errors.append(f"Node '{node_name}': {e}")
            fail_count += 1
        except Exception as e:
            logger.error(f"Unexpected error for {node_name}: {e}")
            errors.append(f"Node '{node_name}': {e}")
            fail_count += 1
            
    logger.info(f"Cluster deployment finished: {success_count} success, {fail_count} failed")
    
    # 返回部署统计结果
    return success_count, fail_count, errors
