import openai
from rich.console import Console
from rich.syntax import Syntax
from rich.prompt import Confirm, Prompt
import re
from src.docker_ops import deploy_compose
from src.i18n import t

console = Console()

SYSTEM_PROMPT = """
You are a DevOps expert specializing in Docker.
Your goal is to help users deploy middleware.

Process:
1. Analyze the user's request.
2. If the request is vague (e.g., just "install redis"), you MUST ask clarifying questions to gather requirements (e.g., version, password, persistence, port mapping).
   - Return a JSON object: {"type": "question", "content": "Your clarifying question here"}
3. If the request is detailed enough or the user insists on defaults, generate the `docker-compose.yml`.
   - Return a JSON object: {"type": "plan", "content": "yaml_content_here"}

Rules for YAML generation:
1. Output MUST be a valid `docker-compose.yml`.
2. Do NOT include top-level 'version' field.
3. Use standard official images.
4. Ensure data persistence (volumes) if applicable.

Output Format:
You must strictly output JSON.
"""

def process_deployment(instruction: str, config: dict):
    base_url = config["base_url"]
    if base_url.endswith("/chat/completions"):
        base_url = base_url.replace("/chat/completions", "")
    
    client = openai.OpenAI(
        api_key=config["api_key"],
        base_url=base_url
    )
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
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
                
            else:
                console.print(f"[red]Unknown response type: {result.get('type')}[/red]")
                break
                
        except Exception as e:
            console.print(f"[bold red]{t('ai_error')}[/bold red] {e}")
            raise
