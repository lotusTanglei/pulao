import openai
from rich.console import Console
from rich.syntax import Syntax
from rich.prompt import Confirm
import re
from src.docker_ops import deploy_compose
from src.i18n import t

console = Console()

SYSTEM_PROMPT = """
You are a DevOps expert specializing in Docker.
Your goal is to generate a production-ready `docker-compose.yml` file based on user requirements.

Rules:
1. Output MUST be a valid `docker-compose.yml` file.
2. Wrap the YAML content in a markdown code block: ```yaml ... ```.
3. If the user requests high availability (HA), ensure you define the necessary replicas, environment variables, and networking.
4. Use standard official images.
5. Do not include markdown preamble or postscript if not requested.
"""

def extract_yaml(text: str) -> str:
    """Extract YAML content from markdown code blocks."""
    pattern = r"```yaml\n(.*?)\n```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1)
    # Fallback: assume the whole text is YAML if no blocks found
    return text

def process_deployment(instruction: str, config: dict):
    base_url = config["base_url"]
    # Auto-fix common config error where user includes /chat/completions
    if base_url.endswith("/chat/completions"):
        base_url = base_url.replace("/chat/completions", "")
    
    client = openai.OpenAI(
        api_key=config["api_key"],
        base_url=base_url
    )
    
    console.print(f"[dim]{t('sending_request')}[/dim]")
    
    try:
        response = client.chat.completions.create(
            model=config["model"],
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": instruction}
            ],
            temperature=0.2
        )
        
        content = response.choices[0].message.content
        yaml_content = extract_yaml(content)
        
        # Display the plan
        console.print(f"[bold]{t('proposed_config')}[/bold]")
        syntax = Syntax(yaml_content, "yaml", theme="monokai", line_numbers=True)
        console.print(syntax)
        console.print("")
        
        if Confirm.ask(t("confirm_deploy")):
            deploy_compose(yaml_content)
        else:
            console.print(f"[yellow]{t('deploy_cancelled')}[/yellow]")
            
    except Exception as e:
        console.print(f"[bold red]{t('ai_error')}[/bold red] {e}")
        raise
