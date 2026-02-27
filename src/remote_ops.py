"""
远程 SSH 操作模块

本模块负责通过 SSH 在远程服务器上执行操作，是集群部署的基础。

主要功能：
1. SSH 连接检查
2. 远程命令执行
3. 文件上传（SCP）
4. 远程 Docker 部署

异常类：
- SSHError: SSH 相关错误基类
- SSHConnectionError: 连接失败
- SSHAuthError: 认证失败
- SSHCommandError: 命令执行失败
"""

# ============ 标准库导入 ============
import subprocess
import os
import tempfile
from typing import Dict, List

# ============ 第三方库导入 ============
from rich.console import Console

# ============ 本地模块导入 ============
from src.logger import logger  # 日志记录

# 创建 Rich 控制台对象
console = Console()


# ============ SSH 异常类定义 ============

class SSHError(Exception):
    """SSH 相关错误的基类"""
    pass

class SSHConnectionError(SSHError):
    """SSH 连接失败异常"""
    pass

class SSHAuthError(SSHError):
    """SSH 认证失败异常"""
    pass

class SSHCommandError(SSHError):
    """SSH 命令执行失败异常"""
    pass


# ============ SSH 远程执行器类 ============

class RemoteExecutor:
    """
    SSH 远程执行器
    
    提供静态方法用于远程服务器的 SSH 操作。
    所有方法都是静态的，无需创建实例。
    
    主要功能：
        - 检查 SSH 连接
        - 执行远程命令
        - 上传文件
        - 远程部署 Docker
    """
    
    # ============ SSH 命令构建方法 ============
    
    @staticmethod
    def _build_ssh_cmd(node: Dict, cmd: str) -> List[str]:
        """
        构建 SSH 命令列表
        
        参数:
            node: 节点配置字典，包含 host, user, key_path 等
            cmd: 要执行的远程命令
        
        返回:
            SSH 命令列表（用于 subprocess）
        
        SSH 选项说明：
            - StrictHostKeyChecking=no: 自动信任主机密钥
            - BatchMode=yes: 禁止交互式密码提示
            - ConnectTimeout=3: 连接超时 3 秒
        """
        ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes", "-o", "ConnectTimeout=3"]
        
        # 如果指定了 SSH 密钥，添加到命令
        if node.get("key_path"):
            ssh_cmd.extend(["-i", node["key_path"]])
            
        # 构建目标主机字符串
        target = f"{node['user']}@{node['host']}"
        ssh_cmd.append(target)
        ssh_cmd.append(cmd)
        
        return ssh_cmd

    @staticmethod
    def _build_scp_cmd(node: Dict, local_path: str, remote_path: str) -> List[str]:
        """
        构建 SCP 命令列表
        
        参数:
            node: 节点配置字典
            local_path: 本地文件路径
            remote_path: 远程文件路径
        
        返回:
            SCP 命令列表
        """
        scp_cmd = ["scp", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes", "-o", "ConnectTimeout=3"]
        
        # SSH 密钥
        if node.get("key_path"):
            scp_cmd.extend(["-i", node["key_path"]])
            
        # 目标路径
        target = f"{node['user']}@{node['host']}:{remote_path}"
        scp_cmd.extend([local_path, target])
        
        return scp_cmd
    
    # ============ SSH 连接检查方法 ============
    
    @staticmethod
    def check_connection(node: Dict) -> bool:
        """
        检查 SSH 连接到节点是否正常
        
        发送一个简单的 "exit" 命令测试连接。
        
        参数:
            node: 节点配置字典，必须包含 host 和 user
        
        返回:
            True 表示连接成功
        
        异常:
            SSHConnectionError: 连接失败
            SSHAuthError: 认证失败
        """
        cmd_list = RemoteExecutor._build_ssh_cmd(node, "exit")
        logger.debug(f"Checking connectivity to {node['name']}: {' '.join(cmd_list)}")
        
        try:
            # 执行命令，10 秒超时
            result = subprocess.run(cmd_list, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                logger.info(f"Node {node['name']} is online")
                return True
            else:
                # 解析错误信息，抛出对应异常
                error_msg = result.stderr.strip()
                logger.warning(f"Node {node['name']} connection failed: {error_msg}")
                
                if "Permission denied" in error_msg or "Authentication failed" in error_msg:
                    raise SSHAuthError(f"Authentication failed for {node['name']}")
                elif "timed out" in error_msg or "ConnectTimeout" in error_msg:
                    raise SSHConnectionError(f"Connection timed out for {node['name']}")
                elif "Could not resolve hostname" in error_msg:
                    raise SSHConnectionError(f"Could not resolve hostname for {node['name']}")
                elif "Connection refused" in error_msg:
                    raise SSHConnectionError(f"Connection refused for {node['name']}")
                else:
                    raise SSHConnectionError(f"Connection failed for {node['name']}: {error_msg}")
                    
        except subprocess.TimeoutExpired:
            logger.error(f"Node {node['name']} connection check timed out")
            raise SSHConnectionError(f"Connection timed out for {node['name']}")
        except Exception as e:
            if isinstance(e, SSHError):
                raise
            logger.error(f"Error connecting to {node['name']}: {e}")
            raise SSHConnectionError(f"Unexpected error for {node['name']}: {e}")

    # ============ 远程命令执行方法 ============
    
    @staticmethod
    def execute(node: Dict, command: str) -> str:
        """
        在远程节点上执行命令
        
        参数:
            node: 节点配置字典
            command: 要执行的命令
        
        返回:
            命令的标准输出
        
        异常:
            SSHCommandError: 命令执行失败
        """
        cmd_list = RemoteExecutor._build_ssh_cmd(node, command)
        logger.debug(f"Executing on {node['name']}: {command}")
        
        try:
            # 5 分钟超时
            result = subprocess.run(cmd_list, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                logger.info(f"Command success on {node['name']}")
                return result.stdout.strip()
            else:
                # 命令执行失败
                error_msg = result.stderr.strip()
                logger.error(f"Command failed on {node['name']}: {error_msg}")
                raise SSHCommandError(f"Command failed on {node['name']}: {error_msg}")
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out on {node['name']}")
            raise SSHCommandError(f"Command timed out on {node['name']}")
        except Exception as e:
            if isinstance(e, SSHError):
                raise
            logger.error(f"Error executing on {node['name']}: {e}")
            raise SSHConnectionError(f"Execution error on {node['name']}: {e}")

    # ============ 文件上传方法 ============
    
    @staticmethod
    def copy_file(node: Dict, local_path: str, remote_path: str) -> None:
        """
        上传文件到远程节点
        
        参数:
            node: 节点配置字典
            local_path: 本地文件路径
            remote_path: 远程目标路径
        
        异常:
            SSHCommandError: 上传失败
        """
        cmd_list = RemoteExecutor._build_scp_cmd(node, local_path, remote_path)
        logger.debug(f"Copying to {node['name']}: {local_path} -> {remote_path}")
        
        try:
            result = subprocess.run(cmd_list, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                logger.info(f"Copy success to {node['name']}")
                return
            else:
                error_msg = result.stderr.strip()
                logger.error(f"Copy failed to {node['name']}: {error_msg}")
                raise SSHCommandError(f"SCP failed to {node['name']}: {error_msg}")
        except subprocess.TimeoutExpired:
            logger.error(f"SCP timed out to {node['name']}")
            raise SSHConnectionError(f"SCP timed out to {node['name']}")
        except Exception as e:
            if isinstance(e, SSHError):
                raise
            logger.error(f"Error copying to {node['name']}: {e}")
            raise SSHConnectionError(f"SCP error to {node['name']}: {e}")

    # ============ 远程 Docker 部署方法 ============
    
    @staticmethod
    def deploy_compose(node: Dict, yaml_content: str, project_name: str) -> None:
        """
        在远程节点上部署 Docker Compose 服务
        
        执行流程：
            1. 创建远程目录
            2. 将 YAML 内容写入临时文件
            3. SCP 上传到远程节点
            4. 执行 docker compose up -d
        
        参数:
            node: 节点配置字典
            yaml_content: docker-compose.yml 内容
            project_name: 项目名称（用于目录命名）
        
        异常:
            SSHError: 任何 SSH 相关错误
        """
        logger.info(f"Deploying project '{project_name}' to {node['name']}")
        
        # 1. 创建远程目录
        remote_dir = f"~/.pulao/deployments/{project_name}"
        RemoteExecutor.execute(node, f"mkdir -p {remote_dir}")

        # 2. 写入本地临时文件
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".yml") as tmp:
            tmp.write(yaml_content)
            tmp_path = tmp.name

        try:
            # 3. SCP 上传文件
            remote_file = f"{remote_dir}/docker-compose.yml"
            RemoteExecutor.copy_file(node, tmp_path, remote_file)
            
            # 4. 执行 docker compose up
            up_cmd = f"cd {remote_dir} && docker compose up -d --remove-orphans"
            RemoteExecutor.execute(node, up_cmd)
            
            logger.info(f"Deployment successful on {node['name']}")
            
        finally:
            # 清理本地临时文件
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
