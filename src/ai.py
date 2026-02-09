import openai
from rich.console import Console
from rich.syntax import Syntax
from rich.prompt import Confirm, Prompt
import re
from src.docker_ops import deploy_compose
from src.system_ops import execute_shell_command
from src.prompts import get_system_prompt
from src.i18n import t

console = Console()

def process_deployment(instruction: str, config: dict):
    base_url = config["base_url"]
    if base_url.endswith("/chat/completions"):
        base_url = base_url.replace("/chat/completions", "")
    
    client = openai.OpenAI(
        api_key=config["api_key"],
        base_url=base_url
    )
    
    # Get current language from config, default to en
    current_lang = config.get("language", "en")
    system_prompt = get_system_prompt(current_lang)
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": instruction}
    ]
    
    console.print(f"[dim]{t('sending_request')}[/dim]")
    
    while True:
        try:
            response = client.chat.completions.create(
                model=config["model"],
                messages=messages,
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            
            # Simple JSON parsing (assuming the model follows instructions)
            import json
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                # Fallback if model didn't return JSON
                console.print(f"[yellow]AI response format error, assuming it's a plan...[/yellow]")
                result = {"type": "plan", "content": content}

            if result.get("type") == "question":
                console.print(f"\n[bold yellow]{t('clarification_needed')}[/bold yellow]")
                console.print(result["content"])
                
                # Ask user for input
                user_response = Prompt.ask(f"\n[cyan]{t('clarification_prompt')}[/cyan]")
                
                if not user_response.strip():
                    user_response = "Please decide the best defaults for me."
                
                # Append to history
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": user_response})
                console.print(f"[dim]{t('sending_request')}[/dim]")
                continue
                
            elif result.get("type") == "plan":
                yaml_content = result["content"]
                # Clean up if markdown blocks remain
                if "```yaml" in yaml_content:
                    pattern = r"```yaml\n(.*?)\n```"
                    match = re.search(pattern, yaml_content, re.DOTALL)
                    if match:
                        yaml_content = match.group(1)

                # Display the plan
                console.print(f"[bold]{t('proposed_config')}[/bold]")
                syntax = Syntax(yaml_content, "yaml", theme="monokai", line_numbers=True)
                console.print(syntax)
                console.print("")
                
                if Confirm.ask(t("confirm_deploy")):
                    deploy_compose(yaml_content)
                else:
                    console.print(f"[yellow]{t('deploy_cancelled')}[/yellow]")
                break

            elif result.get("type") == "command":
                cmd_content = result["content"]
                
                # Display the command
                console.print(f"[bold]{t('proposed_command')}[/bold]")
                syntax = Syntax(cmd_content, "bash", theme="monokai")
                console.print(syntax)
                console.print("")
                
                if Confirm.ask(t("confirm_execute")):
                    execute_shell_command(cmd_content)
                else:
                    console.print(f"[yellow]{t('deploy_cancelled')}[/yellow]")
                break
                
            else:
                console.print(f"[red]Unknown response type: {result.get('type')}[/red]")
                break
                
        except Exception as e:
            console.print(f"[bold red]{t('ai_error')}[/bold red] {e}")
            raise
