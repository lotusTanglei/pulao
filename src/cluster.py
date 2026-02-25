
import os
import yaml
from pathlib import Path
from typing import List, Dict, Optional
from rich.console import Console
from rich.table import Table
from src.remote_ops import RemoteExecutor
from src.i18n import t
from src.config import CONFIG_DIR

console = Console()

CLUSTERS_FILE = CONFIG_DIR / "clusters.yaml"

DEFAULT_CLUSTERS_CONFIG = {
    "current_cluster": "default",
    "clusters": {
        "default": {
            "nodes": []
        }
    }
}

class ClusterManager:
    """Manages multi-cluster configuration and nodes."""

    @staticmethod
    def load_config() -> Dict:
        """Load clusters configuration from file."""
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
        """Save clusters configuration to file."""
        CLUSTERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CLUSTERS_FILE, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False)

    @staticmethod
    def get_current_cluster_name() -> str:
        """Get the name of the currently active cluster."""
        cfg = ClusterManager.load_config()
        return cfg.get("current_cluster", "default")

    @staticmethod
    def get_current_nodes() -> List[Dict]:
        """Get nodes for the current cluster."""
        cfg = ClusterManager.load_config()
        current = cfg.get("current_cluster", "default")
        clusters = cfg.get("clusters", {})
        return clusters.get(current, {}).get("nodes", [])

    @staticmethod
    def list_clusters():
        """List all available clusters."""
        cfg = ClusterManager.load_config()
        current = cfg.get("current_cluster", "default")
        clusters = cfg.get("clusters", {})

        table = Table(title="Available Clusters")
        table.add_column("Name", style="cyan")
        table.add_column("Nodes", justify="right")
        table.add_column("Status", justify="center")

        for name, data in clusters.items():
            node_count = len(data.get("nodes", []))
            status = "[green]* (current)[/green]" if name == current else ""
            table.add_row(name, str(node_count), status)

        console.print(table)

    @staticmethod
    def create_cluster(name: str):
        """Create a new cluster."""
        cfg = ClusterManager.load_config()
        if "clusters" not in cfg:
            cfg["clusters"] = {}
            
        if name in cfg["clusters"]:
            console.print(f"[yellow]Cluster '{name}' already exists.[/yellow]")
            return

        cfg["clusters"][name] = {"nodes": []}
        ClusterManager.save_config(cfg)
        console.print(f"[green]Cluster '{name}' created.[/green]")

    @staticmethod
    def switch_cluster(name: str):
        """Switch current cluster context."""
        cfg = ClusterManager.load_config()
        if name not in cfg.get("clusters", {}):
            console.print(f"[red]Cluster '{name}' not found.[/red]")
            return

        cfg["current_cluster"] = name
        ClusterManager.save_config(cfg)
        console.print(f"[green]Switched to cluster: {name}[/green]")

    @staticmethod
    def add_node(name: str, host: str, user: str, role: str = "worker", key_path: str = ""):
        """Add a node to the CURRENT cluster."""
        cfg = ClusterManager.load_config()
        current = cfg.get("current_cluster", "default")
        
        # Ensure cluster structure exists
        if "clusters" not in cfg:
            cfg["clusters"] = {}
        if current not in cfg["clusters"]:
            cfg["clusters"][current] = {"nodes": []}
            
        nodes = cfg["clusters"][current].get("nodes", [])
        
        # Check if node name exists
        for node in nodes:
            if node["name"] == name:
                console.print(f"[yellow]Node '{name}' already exists in cluster '{current}'. Updating...[/yellow]")
                nodes.remove(node)
                break
        
        new_node = {
            "name": name,
            "host": host,
            "user": user,
            "role": role,
            "key_path": key_path
        }
        
        # Check connectivity
        if RemoteExecutor.check_connection(new_node):
            new_node["status"] = "Online"
            console.print(t("node_online"))
        else:
            new_node["status"] = "Auth Failed"
            console.print(t("node_auth_failed"))
            console.print(t("auth_failed_guide", name=name, user=user, host=host))
            
        nodes.append(new_node)
        cfg["clusters"][current]["nodes"] = nodes
        
        ClusterManager.save_config(cfg)
        console.print(f"[green]Node '{name}' added to cluster '{current}'.[/green]")

    @staticmethod
    def remove_node(name: str):
        """Remove a node from the CURRENT cluster."""
        cfg = ClusterManager.load_config()
        current = cfg.get("current_cluster", "default")
        nodes = cfg.get("clusters", {}).get(current, {}).get("nodes", [])
        
        new_nodes = [n for n in nodes if n["name"] != name]
        
        if len(new_nodes) == len(nodes):
            console.print(f"[yellow]Node '{name}' not found in cluster '{current}'.[/yellow]")
            return

        cfg["clusters"][current]["nodes"] = new_nodes
        ClusterManager.save_config(cfg)
        console.print(f"[green]Node '{name}' removed from cluster '{current}'.[/green]")

    @staticmethod
    def list_nodes():
        """List nodes in the CURRENT cluster."""
        cfg = ClusterManager.load_config()
        current = cfg.get("current_cluster", "default")
        nodes = cfg.get("clusters", {}).get(current, {}).get("nodes", [])

        if not nodes:
            console.print(f"[yellow]No nodes in cluster '{current}'.[/yellow]")
            return

        table = Table(title=f"Nodes in Cluster: {current}")
        table.add_column("Name", style="cyan")
        table.add_column("Host", style="magenta")
        table.add_column("User", style="blue")
        table.add_column("Role", style="green")
        table.add_column("Status", style="bold")

        for node in nodes:
            status = node.get("status", "Unknown")
            status_style = "green" if status == "Online" else "red" if status == "Auth Failed" else "yellow"

            table.add_row(
                node["name"],
                node["host"],
                node["user"],
                node.get("role", "worker"),
                f"[{status_style}]{status}[/{status_style}]"
            )

        console.print(table)
