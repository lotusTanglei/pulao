import openai
from rich.console import Console
from rich.syntax import Syntax
from rich.prompt import Confirm, Prompt
import re
from src.docker_ops import deploy_compose
from src.system_ops import execute_shell_command
from src.prompts import get_system_prompt
from src.i18n import t
from src.library_manager import LibraryManager

console = Console()

# Global chat history
_CHAT_HISTORY = []

def process_deployment(instruction: str, config: dict):
    global _CHAT_HISTORY
    
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
    
    # Initialize history if empty
    if not _CHAT_HISTORY:
        _CHAT_HISTORY = [{"role": "system", "content": system_prompt}]
    else:
        # Update system prompt in case system info changed
        _CHAT_HISTORY[0] = {"role": "system", "content": system_prompt}

    # Add current user instruction
    
    # Check for available templates based on user instruction
    # A simple keyword check to see if we should inject a template
    template_content = None
    # Heuristic: if user input contains a service name that we have in library
    for tpl_name in LibraryManager.list_templates():
        if tpl_name in instruction.lower():
            template_content = LibraryManager.get_template(tpl_name)
            if template_content:
                console.print(f"[dim]Using built-in template for: {tpl_name}[/dim]")
                break
    
    final_instruction = instruction
    if template_content:
        final_instruction += f"\n\n[Template Context]\nHere is a reference docker-compose.yml for {tpl_name}. Please adapt it:\n```yaml\n{template_content}\n```"
    
    _CHAT_HISTORY.append({"role": "user", "content": final_instruction})
    
    # Use a copy for current turn loop to avoid duplicating history on retry
    messages = _CHAT_HISTORY.copy()
    
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
                
                # Append to current loop messages AND global history
                assistant_msg = {"role": "assistant", "content": content}
                user_msg = {"role": "user", "content": user_response}
                
                messages.append(assistant_msg)
                messages.append(user_msg)
                
                _CHAT_HISTORY.append(assistant_msg)
                _CHAT_HISTORY.append(user_msg)
                
                console.print(f"[dim]{t('sending_request')}[/dim]")
                continue
                
            elif result.get("type") == "plan":
                # ... (existing plan logic)
                # Add successful result to history
                _CHAT_HISTORY.append({"role": "assistant", "content": content})
                
                yaml_content = result["content"]
                # Clean up if markdown blocks remain
                if "```yaml" in yaml_content:
                    pattern = r"```yaml\n(.*?)\n```"
                    match = re.search(pattern, yaml_content, re.DOTALL)
                    if match:
                        yaml_content = match.group(1)

                # Display the plan
                suggested_name = result.get("project_name", "default")
                console.print(f"[bold]{t('proposed_config')}[/bold]")
                syntax = Syntax(yaml_content, "yaml", theme="monokai", line_numbers=True)
                console.print(syntax)
                console.print("")
                
                # Ask user to confirm/modify project name
                project_name = Prompt.ask(
                    t("confirm_project_name", default=suggested_name), 
                    default=suggested_name
                )
                
                if Confirm.ask(t("confirm_deploy")):
                    deploy_compose(yaml_content, project_name=project_name)
                else:
                    console.print(f"[yellow]{t('deploy_cancelled')}[/yellow]")
                break

            elif result.get("type") == "command":
                # Add successful result to history
                _CHAT_HISTORY.append({"role": "assistant", "content": content})
                
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
                
        except KeyboardInterrupt:
            console.print(f"[yellow]{t('request_cancelled')}[/yellow]")
            return

        except Exception as e:
            console.print(f"[bold red]{t('ai_error')}[/bold red] {e}")
            raise
