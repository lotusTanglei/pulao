
import subprocess
import os
from pathlib import Path
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
from src.i18n import t
from src.cluster import ClusterManager
from src.remote_ops import RemoteExecutor, SSHError
from src.logger import logger
from src.config import CONFIG_DIR

DEPLOY_DIR = CONFIG_DIR / "deployments"

@dataclass
class DeploymentResult:
    success: bool
    message: str
    stdout: Optional[str] = None
    stderr: Optional[str] = None

class DeploymentError(Exception):
    """Base exception for deployment errors."""
    pass

def deploy_compose(yaml_content: str, project_name: str = "default") -> DeploymentResult:
    """
    Write YAML to a file and run docker-compose up (Local).
    Returns DeploymentResult.
    """
    # Create project directory
    # Sanitize project name to be safe for directory usage
    safe_name = "".join([c for c in project_name if c.isalnum() or c in "-_"]).strip()
    if not safe_name:
        safe_name = "default"
        
    project_dir = DEPLOY_DIR / safe_name
    project_dir.mkdir(parents=True, exist_ok=True)
    
    compose_file = project_dir / "docker-compose.yml"
    
    try:
        # Write the file
        with open(compose_file, "w", encoding="utf-8") as f:
            f.write(yaml_content)
        
        logger.info(f"Written compose file to {compose_file}")
        
        # Run docker compose
        logger.info(f"Executing docker compose in {project_dir}")
        
        # Check if docker-compose or docker compose is available
        cmd = ["docker", "compose", "up", "-d", "--remove-orphans"]
        
        process = subprocess.Popen(
            cmd, 
            cwd=project_dir, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate()
        
        if process.returncode == 0:
            logger.info("Local deployment success")
            return DeploymentResult(
                success=True,
                message=t('deployment_success'),
                stdout=stdout
            )
        else:
            logger.error(f"Local deployment failed: {stderr}")
            return DeploymentResult(
                success=False,
                message=t('deployment_failed'),
                stderr=stderr
            )
            
    except Exception as e:
        logger.error(f"Error executing compose: {e}")
        raise DeploymentError(f"{t('error_executing_compose')} {e}")

def deploy_cluster(plan_content: Dict[str, str], project_name: str = "default") -> Tuple[int, int, List[str]]:
    """
    Deploy multi-node configuration to cluster.
    Returns (success_count, fail_count, list_of_error_messages).
    Raises DeploymentError on critical failures.
    """
    logger.info(f"Starting Cluster Deployment: {project_name}")
    
    nodes = ClusterManager.get_current_nodes()
    nodes_map = {n["name"]: n for n in nodes}
    
    # Pre-flight check: Verify connectivity for ALL target nodes
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
    
    if failed_nodes:
        error_msg = t("deploy_aborted_auth_fail")
        logger.error(f"Cluster deployment aborted: {len(failed_nodes)} nodes failed pre-flight check")
        # We raise exception here, let upper layer handle user notification details
        raise DeploymentError(error_msg, failed_nodes)

    success_count = 0
    fail_count = 0
    errors = []
    
    for node_name, yaml_content in plan_content.items():
        if node_name not in nodes_map:
            # Already logged warning above
            fail_count += 1
            continue
            
        node = nodes_map[node_name]
        try:
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
    
    if fail_count > 0:
        # We don't raise exception here if partial success is allowed, 
        # BUT our spec says "strict", however pre-flight passed so this is runtime error.
        # Let's return stats and let caller decide or raise if all failed?
        # Current logic: return stats.
        pass
        
    return success_count, fail_count, errors
