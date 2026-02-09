import subprocess
from rich.console import Console
from src.i18n import t

console = Console()

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
