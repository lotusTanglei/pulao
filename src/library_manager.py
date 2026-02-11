import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, List
from rich.console import Console

console = Console()

# Define library root
# We prefer user home directory for updates, fallback to package dir for built-ins
USER_LIBRARY_DIR = Path.home() / ".pulao" / "library"
BUILTIN_LIBRARY_DIR = Path(__file__).parent / "library"

AWESOME_COMPOSE_REPO = "https://github.com/docker/awesome-compose.git"

class LibraryManager:
    """Manages the Docker Compose template library (Built-in + User updated)."""
    
    @staticmethod
    def _get_library_dir() -> Path:
        """Return the active library directory (User's if exists, else Built-in)."""
        if USER_LIBRARY_DIR.exists():
            return USER_LIBRARY_DIR
        return BUILTIN_LIBRARY_DIR

    @staticmethod
    def update_library():
        """Clone or pull the awesome-compose repository."""
        console.print(f"[bold cyan]Updating template library from {AWESOME_COMPOSE_REPO}...[/bold cyan]")
        
        try:
            if USER_LIBRARY_DIR.exists():
                # If it's a git repo, pull
                if (USER_LIBRARY_DIR / ".git").exists():
                    console.print("[dim]Pulling latest changes...[/dim]")
                    subprocess.run(["git", "pull"], cwd=USER_LIBRARY_DIR, check=True)
                else:
                    console.print("[yellow]Library directory exists but is not a git repo. Backing up and re-cloning...[/yellow]")
                    shutil.move(str(USER_LIBRARY_DIR), str(USER_LIBRARY_DIR) + ".bak")
                    subprocess.run(["git", "clone", "--depth", "1", AWESOME_COMPOSE_REPO, str(USER_LIBRARY_DIR)], check=True)
            else:
                # Clone fresh
                USER_LIBRARY_DIR.parent.mkdir(parents=True, exist_ok=True)
                console.print("[dim]Cloning repository...[/dim]")
                subprocess.run(["git", "clone", "--depth", "1", AWESOME_COMPOSE_REPO, str(USER_LIBRARY_DIR)], check=True)
                
            console.print("[bold green]Library updated successfully![/bold green]")
            console.print(f"[dim]Templates stored in: {USER_LIBRARY_DIR}[/dim]")
            
        except subprocess.CalledProcessError as e:
            console.print(f"[bold red]Failed to update library:[/bold red] {e}")
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")

    @staticmethod
    def list_templates() -> List[str]:
        """List all available templates in the library."""
        lib_dir = LibraryManager._get_library_dir()
        if not lib_dir.exists():
            return []
            
        templates = []
        # Walk through directory to find folders containing docker-compose.yaml or .yml
        # awesome-compose structure is usually: root/project/docker-compose.yaml
        for item in lib_dir.iterdir():
            if item.is_dir():
                if (item / "docker-compose.yaml").exists() or (item / "docker-compose.yml").exists():
                    templates.append(item.name)
        return sorted(templates)

    @staticmethod
    def get_template(service_name: str) -> Optional[str]:
        """
        Retrieve the content of a docker-compose.yml for a given service.
        Returns None if not found.
        """
        lib_dir = LibraryManager._get_library_dir()
        
        # Search strategy:
        # 1. Exact match folder name
        # 2. Fuzzy match folder name
        
        target_dir = lib_dir / service_name
        
        def try_read(d: Path) -> Optional[str]:
            for name in ["docker-compose.yaml", "docker-compose.yml"]:
                f = d / name
                if f.exists():
                    return f.read_text(encoding="utf-8")
            return None

        # 1. Exact match
        if target_dir.exists():
            content = try_read(target_dir)
            if content: return content
            
        # 2. Fuzzy match
        available = LibraryManager.list_templates()
        for tpl in available:
            if tpl in service_name.lower() or service_name.lower() in tpl:
                # Found a potential match
                candidate_dir = lib_dir / tpl
                content = try_read(candidate_dir)
                if content:
                    console.print(f"[dim]Found matching template: {tpl}[/dim]")
                    return content
                    
        return None
