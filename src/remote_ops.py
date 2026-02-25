
import subprocess
import os
import tempfile
from typing import Dict, List
from rich.console import Console
from src.logger import logger

console = Console()

class SSHError(Exception):
    """Base exception for SSH related errors."""
    pass

class SSHConnectionError(SSHError):
    """Raised when connection cannot be established."""
    pass

class SSHAuthError(SSHError):
    """Raised when authentication fails."""
    pass

class SSHCommandError(SSHError):
    """Raised when remote command returns non-zero exit code."""
    pass

class RemoteExecutor:
    """Handles remote execution via SSH."""

    @staticmethod
    def _build_ssh_cmd(node: Dict, cmd: str) -> List[str]:
        """Build SSH command list."""
        ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes", "-o", "ConnectTimeout=3"]
        
        if node.get("key_path"):
            ssh_cmd.extend(["-i", node["key_path"]])
            
        target = f"{node['user']}@{node['host']}"
        ssh_cmd.append(target)
        ssh_cmd.append(cmd)
        
        return ssh_cmd

    @staticmethod
    def _build_scp_cmd(node: Dict, local_path: str, remote_path: str) -> List[str]:
        """Build SCP command list."""
        scp_cmd = ["scp", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes", "-o", "ConnectTimeout=3"]
        
        if node.get("key_path"):
            scp_cmd.extend(["-i", node["key_path"]])
            
        target = f"{node['user']}@{node['host']}:{remote_path}"
        scp_cmd.extend([local_path, target])
        
        return scp_cmd

    @staticmethod
    def check_connection(node: Dict) -> bool:
        """Check SSH connectivity to the node."""
        cmd_list = RemoteExecutor._build_ssh_cmd(node, "exit")
        # console.print(f"[dim]Checking connectivity to {node['name']} ({node['host']})...[/dim]")
        logger.debug(f"Checking connectivity to {node['name']}: {' '.join(cmd_list)}")
        
        try:
            # Run with a timeout to prevent hanging indefinitely
            result = subprocess.run(cmd_list, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                # console.print(f"[green]✔ {node['name']}: Online[/green]")
                logger.info(f"Node {node['name']} is online")
                return True
            else:
                error_msg = result.stderr.strip()
                logger.warning(f"Node {node['name']} connection failed: {error_msg}")
                if "Permission denied" in error_msg or "Authentication failed" in error_msg:
                    # console.print(f"[red]✘ {node['name']}: Authentication Failed[/red]")
                    raise SSHAuthError(f"Authentication failed for {node['name']}")
                elif "timed out" in error_msg or "ConnectTimeout" in error_msg:
                    # console.print(f"[red]✘ {node['name']}: Connection Timed Out[/red]")
                    raise SSHConnectionError(f"Connection timed out for {node['name']}")
                elif "Could not resolve hostname" in error_msg:
                    # console.print(f"[red]✘ {node['name']}: Hostname Resolution Failed[/red]")
                    raise SSHConnectionError(f"Could not resolve hostname for {node['name']}")
                elif "Connection refused" in error_msg:
                    # console.print(f"[red]✘ {node['name']}: Connection Refused[/red]")
                    raise SSHConnectionError(f"Connection refused for {node['name']}")
                else:
                    # console.print(f"[red]✘ {node['name']}: Connection Failed ({error_msg})[/red]")
                    raise SSHConnectionError(f"Connection failed for {node['name']}: {error_msg}")
                    
        except subprocess.TimeoutExpired:
            logger.error(f"Node {node['name']} connection check timed out")
            raise SSHConnectionError(f"Connection timed out for {node['name']}")
        except Exception as e:
            if isinstance(e, SSHError):
                raise
            logger.error(f"Error connecting to {node['name']}: {e}")
            raise SSHConnectionError(f"Unexpected error for {node['name']}: {e}")

    @staticmethod
    def execute(node: Dict, command: str) -> str:
        """
        Execute command on remote node.
        Returns stdout on success.
        Raises SSHCommandError on failure.
        """
        cmd_list = RemoteExecutor._build_ssh_cmd(node, command)
        # console.print(f"[dim]Running on {node['name']}: {command}[/dim]")
        logger.debug(f"Executing on {node['name']}: {command}")
        
        try:
            result = subprocess.run(cmd_list, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                # console.print(f"[green]✔ {node['name']}: Success[/green]")
                # if result.stdout:
                #     console.print(f"[dim]{result.stdout.strip()}[/dim]")
                logger.info(f"Command success on {node['name']}")
                return result.stdout.strip()
            else:
                # console.print(f"[red]✘ {node['name']}: Failed[/red]")
                # console.print(f"[red]{result.stderr.strip()}[/red]")
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

    @staticmethod
    def copy_file(node: Dict, local_path: str, remote_path: str) -> None:
        """
        Copy file to remote node.
        Raises SSHError on failure.
        """
        cmd_list = RemoteExecutor._build_scp_cmd(node, local_path, remote_path)
        # console.print(f"[dim]Copying to {node['name']}: {local_path} -> {remote_path}[/dim]")
        logger.debug(f"Copying to {node['name']}: {local_path} -> {remote_path}")
        
        try:
            result = subprocess.run(cmd_list, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                logger.info(f"Copy success to {node['name']}")
                return
            else:
                error_msg = result.stderr.strip()
                # console.print(f"[red]Failed to copy to {node['name']}: {error_msg}[/red]")
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

    @staticmethod
    def deploy_compose(node: Dict, yaml_content: str, project_name: str) -> None:
        """
        Deploy docker-compose content to a remote node.
        Raises SSHError on failure.
        """
        # console.print(f"[bold cyan]Deploying to {node['name']} ({node['host']})...[/bold cyan]")
        logger.info(f"Deploying project '{project_name}' to {node['name']}")
        
        # 1. Prepare remote directory
        remote_dir = f"~/.pulao/deployments/{project_name}"
        # Use -p to create parent dirs
        RemoteExecutor.execute(node, f"mkdir -p {remote_dir}")

        # 2. Write content to temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".yml") as tmp:
            tmp.write(yaml_content)
            tmp_path = tmp.name

        try:
            # 3. SCP file to remote
            remote_file = f"{remote_dir}/docker-compose.yml"
            RemoteExecutor.copy_file(node, tmp_path, remote_file)
            
            # 4. Execute docker compose up
            # Check if docker compose or docker-compose is available
            # We assume 'docker compose' (v2)
            up_cmd = f"cd {remote_dir} && docker compose up -d --remove-orphans"
            RemoteExecutor.execute(node, up_cmd)
            
            logger.info(f"Deployment successful on {node['name']}")
            
        finally:
            # Clean up local temp file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
