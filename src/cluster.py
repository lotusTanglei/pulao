"""
集群管理模块

本模块负责管理多节点集群配置，包括：
1. 集群的创建、切换、删除
2. 节点的添加、移除、查看
3. 集群配置的持久化存储

配置文件：~/.pulao/clusters.yaml

节点结构：
    - name: 节点名称
    - host: 主机地址 (IP/hostname)
    - user: SSH 用户名
    - role: 节点角色 (master/worker)
    - key_path: SSH 私钥路径
    - status: 连接状态 (Online/Auth Failed)
"""

# ============ 标准库导入 ============
import os
import yaml
from pathlib import Path
from typing import List, Dict, Optional

# ============ 第三方库导入 ============
from rich.console import Console
from rich.table import Table

# ============ 本地模块导入 ============
from src.remote_ops import RemoteExecutor  # SSH 连接检查
from src.i18n import t  # 国际化翻译函数
from src.config import CONFIG_DIR  # 配置目录

# 创建 Rich 控制台对象
console = Console()

# 集群配置文件路径
CLUSTERS_FILE = CONFIG_DIR / "clusters.yaml"


# ============ 默认配置 ============

DEFAULT_CLUSTERS_CONFIG = {
    "current_cluster": "default",  # 当前使用的集群名称
    "clusters": {
        "default": {
            "nodes": []  # 默认集群没有节点
        }
    }
}


# ============ 集群管理器类 ============

class ClusterManager:
    """
    集群管理器
    
    提供静态方法管理集群配置和节点。
    所有配置保存在 clusters.yaml 文件中。
    """
    
    # ============ 配置加载/保存方法 ============
    
    @staticmethod
    def load_config() -> Dict:
        """
        加载集群配置
        
        返回:
            集群配置字典
        """
        if not CLUSTERS_FILE.exists():
            return DEFAULT_CLUSTERS_CONFIG.copy()
        
        try:
            with open(CLUSTERS_FILE, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or DEFAULT_CLUSTERS_CONFIG.copy()
        except Exception as e:
            console.print(f"[bold red]Failed to load clusters config:[/bold red] {e}")
            return DEFAULT_CLUSTERS_CONFIG.copy()

    @staticmethod
    def save_config(config: Dict):
        """
        保存集群配置
        
        参数:
            config: 配置字典
        """
        CLUSTERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CLUSTERS_FILE, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False)

    # ============ 集群操作方法 ============
    
    @staticmethod
    def get_current_cluster_name() -> str:
        """
        获取当前集群名称
        
        返回:
            当前集群名称字符串
        """
        cfg = ClusterManager.load_config()
        return cfg.get("current_cluster", "default")

    @staticmethod
    def get_current_nodes() -> List[Dict]:
        """
        获取当前集群的节点列表
        
        返回:
            节点字典列表
        """
        cfg = ClusterManager.load_config()
        current = cfg.get("current_cluster", "default")
        clusters = cfg.get("clusters", {})
        return clusters.get(current, {}).get("nodes", [])

    @staticmethod
    def list_clusters() -> str:
        """
        列出所有集群
        
        返回:
            包含集群列表的格式化字符串
        """
        cfg = ClusterManager.load_config()
        current = cfg.get("current_cluster", "default")
        clusters = cfg.get("clusters", {})

        output = ["Available Clusters:"]
        for name, data in clusters.items():
            node_count = len(data.get("nodes", []))
            status = "* (current)" if name == current else ""
            output.append(f"- {name} (Nodes: {node_count}) {status}")

        result = "\n".join(output)
        console.print(result)
        return result

    @staticmethod
    def create_cluster(name: str) -> str:
        """
        创建新集群
        
        参数:
            name: 集群名称
            
        返回:
            操作结果消息
        """
        cfg = ClusterManager.load_config()
        if "clusters" not in cfg:
            cfg["clusters"] = {}
            
        if name in cfg["clusters"]:
            msg = f"Cluster '{name}' already exists."
            console.print(f"[yellow]{msg}[/yellow]")
            return msg

        cfg["clusters"][name] = {"nodes": []}
        ClusterManager.save_config(cfg)
        msg = f"Cluster '{name}' created successfully."
        console.print(f"[green]{msg}[/green]")
        return msg

    @staticmethod
    def switch_cluster(name: str) -> str:
        """
        切换当前使用的集群
        
        参数:
            name: 集群名称
            
        返回:
            操作结果消息
        """
        cfg = ClusterManager.load_config()
        if name not in cfg.get("clusters", {}):
            msg = f"Cluster '{name}' not found."
            console.print(f"[red]{msg}[/red]")
            return msg

        cfg["current_cluster"] = name
        ClusterManager.save_config(cfg)
        msg = f"Switched to cluster: {name}"
        console.print(f"[green]{msg}[/green]")
        return msg

    # ============ 节点操作方法 ============
    
    @staticmethod
    def add_node(name: str, host: str, user: str, role: str = "worker", key_path: str = "") -> str:
        """
        添加节点到当前集群
        
        参数:
            name: 节点名称
            host: 主机地址
            user: SSH 用户名
            role: 节点角色 (默认 "worker")
            key_path: SSH 私钥路径 (可选)
            
        返回:
            操作结果消息
        """
        cfg = ClusterManager.load_config()
        current = cfg.get("current_cluster", "default")
        
        # 确保结构存在
        if "clusters" not in cfg:
            cfg["clusters"] = {}
        if current not in cfg["clusters"]:
            cfg["clusters"][current] = {"nodes": []}
            
        nodes = cfg["clusters"][current].get("nodes", [])
        
        msg_parts = []
        
        # 检查节点名是否已存在，存在则更新
        for node in nodes:
            if node["name"] == name:
                msg_parts.append(f"Node '{name}' already exists in cluster '{current}'. Updating...")
                nodes.remove(node)
                break
        
        # 创建新节点配置
        new_node = {
            "name": name,
            "host": host,
            "user": user,
            "role": role,
            "key_path": key_path
        }
        
        # 尝试 SSH 连接检查
        if RemoteExecutor.check_connection(new_node):
            new_node["status"] = "Online"
            msg_parts.append(t("node_online"))
        else:
            new_node["status"] = "Auth Failed"
            msg_parts.append(t("node_auth_failed"))
            msg_parts.append(t("auth_failed_guide", name=name, user=user, host=host))
            
        # 添加节点
        nodes.append(new_node)
        cfg["clusters"][current]["nodes"] = nodes
        
        ClusterManager.save_config(cfg)
        msg_parts.append(f"Node '{name}' added to cluster '{current}'.")
        
        result = "\n".join(msg_parts)
        console.print(result)
        return result

    @staticmethod
    def remove_node(name: str) -> str:
        """
        从当前集群移除节点
        
        参数:
            name: 节点名称
            
        返回:
            操作结果消息
        """
        cfg = ClusterManager.load_config()
        current = cfg.get("current_cluster", "default")
        nodes = cfg.get("clusters", {}).get(current, {}).get("nodes", [])
        
        # 过滤掉要移除的节点
        new_nodes = [n for n in nodes if n["name"] != name]
        
        if len(new_nodes) == len(nodes):
            msg = f"Node '{name}' not found in cluster '{current}'."
            console.print(f"[yellow]{msg}[/yellow]")
            return msg

        cfg["clusters"][current]["nodes"] = new_nodes
        ClusterManager.save_config(cfg)
        msg = f"Node '{name}' removed from cluster '{current}'."
        console.print(f"[green]{msg}[/green]")
        return msg

    @staticmethod
    def list_nodes() -> str:
        """
        列出当前集群的所有节点
        
        返回:
            包含节点列表的格式化字符串
        """
        cfg = ClusterManager.load_config()
        current = cfg.get("current_cluster", "default")
        nodes = cfg.get("clusters", {}).get(current, {}).get("nodes", [])

        if not nodes:
            msg = f"No nodes in cluster '{current}'."
            console.print(f"[yellow]{msg}[/yellow]")
            return msg

        output = [f"Nodes in Cluster: {current}"]
        for node in nodes:
            status = node.get("status", "Unknown")
            output.append(f"- {node['name']} ({node['host']}) User: {node['user']} Role: {node.get('role', 'worker')} Status: {status}")
            
        result = "\n".join(output)
        console.print(result)
        return result
