import subprocess
import platform
import socket
from rich.console import Console
from src.i18n import t

console = Console()

def get_system_info() -> str:
    """Collect basic system information for AI context."""
    info = []
    
    # OS Info
    try:
        info.append(f"OS: {platform.system()} {platform.release()} ({platform.machine()})")
    except:
        pass

    # IP Address (Internal)
    try:
        hostname = socket.gethostname()
        ip_addr = socket.gethostbyname(hostname)
        info.append(f"Internal IP: {ip_addr}")
    except:
        pass

    # Docker Version and Containers
    try:
        docker_ver = subprocess.check_output(["docker", "--version"], text=True).strip()
        info.append(f"Docker: {docker_ver}")
        
        # Check running containers
        try:
            containers = subprocess.check_output(
                ["docker", "ps", "--format", "table {{.Names}}\t{{.Image}}\t{{.Ports}}"], 
                text=True
            ).strip()
            if containers:
                info.append("\n[Running Docker Containers]")
                # Limit to first 10 lines to save tokens
                lines = containers.split('\n')
                if len(lines) > 10:
                    info.append("\n".join(lines[:10]))
                    info.append(f"... ({len(lines)-10} more)")
                else:
                    info.append(containers)
        except:
            pass
    except:
        info.append("Docker: Not detected")
        
    # Listening Ports (Basic check for common services)
    try:
        # Use lsof if available, fallback to netstat, or skip
        # We try a safe lsof command
        ports_output = subprocess.check_output("lsof -i -P -n | grep LISTEN | head -n 10", shell=True, text=True).strip()
        if ports_output:
            info.append("\n[Listening Ports (Host)]")
            info.append(ports_output)
    except:
        pass
        
    return "\n".join(info)

def execute_shell_command(command: str):
    """
    Execute a shell command and print output.
    """
    console.print(f"[bold yellow]{t('executing_command')}:[/bold yellow] {command}")
    
    try:
        # Use shell=True to allow pipes and complex commands, but warn user first (done in ai.py confirm)
        process = subprocess.Popen(
            command, 
            shell=True,
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True,
            executable="/bin/bash"  # Prefer bash
        )
        
        # Stream output in real-time
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                console.print(output.strip())
                
        # Get remaining stderr
        stderr = process.stderr.read()
        if stderr:
            console.print(f"[red]{stderr}[/red]")
            
        if process.returncode == 0:
            console.print(f"[bold green]{t('command_success')}[/bold green]")
        else:
            console.print(f"[bold red]{t('command_failed')}[/bold red]")
            
    except Exception as e:
        console.print(f"[bold red]{t('error_executing_command')}[/bold red] {e}")
