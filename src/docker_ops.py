import subprocess
import os
from pathlib import Path
from rich.console import Console
from src.i18n import t

console = Console()

DEPLOY_DIR = Path.home() / ".pulao" / "deployments"

def deploy_compose(yaml_content: str, project_name: str = "default"):
    """
    Write YAML to a file and run docker-compose up.
    """
    # Create project directory
    # Sanitize project name to be safe for directory usage
    safe_name = "".join([c for c in project_name if c.isalnum() or c in "-_"]).strip()
    if not safe_name:
        safe_name = "default"
        
    project_dir = DEPLOY_DIR / safe_name
    project_dir.mkdir(parents=True, exist_ok=True)
    
    compose_file = project_dir / "docker-compose.yml"
    
    # Write the file
    with open(compose_file, "w", encoding="utf-8") as f:
        f.write(yaml_content)
        
    console.print(f"[green]{t('written_compose', path=compose_file)}[/green]")
    
    # Run docker compose
    console.print(f"[bold yellow]{t('executing_compose', path=project_dir)}[/bold yellow]")
    
    try:
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
            console.print(f"[bold green]{t('deployment_success')}[/bold green]")
            if stdout:
                console.print(stdout)
        else:
            console.print(f"[bold red]{t('deployment_failed')}[/bold red]")
            console.print(stderr)
            raise Exception(t("compose_failed"))
            
    except Exception as e:
        console.print(f"[bold red]{t('error_executing_compose')}[/bold red] {e}")
        raise
