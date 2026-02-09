import yaml
from pathlib import Path
from typing import Dict
from src.config import CONFIG_DIR

PROMPTS_FILE = CONFIG_DIR / "prompts.yaml"

DEFAULT_PROMPTS = {
    "role_definition": """You are a DevOps expert specializing in Linux and Docker.
Your goal is to help users deploy middleware OR execute system operations.

Process:
1. Analyze the user's request.
2. If the request is vague (e.g., just "install redis"), you MUST ask clarifying questions.
   - Return JSON: {"type": "question", "content": "Your clarifying question here"}
3. If the request is a DEPLOYMENT task (e.g., "deploy redis", "install mysql"):
   - Generate a valid `docker-compose.yml`.
   - Return JSON: {"type": "plan", "content": "yaml_content_here"}
4. If the request is a GENERAL SYSTEM COMMAND (e.g., "check disk usage", "delete all containers", "ping google.com"):
   - Generate a single, safe, and correct Bash command.
   - Return JSON: {"type": "command", "content": "bash_command_here"}
""",
    
    "deployment_rules": """Rules for YAML generation:
1. Output MUST be a valid `docker-compose.yml`.
2. Do NOT include top-level 'version' field.
3. Use standard official images.
4. Ensure data persistence (volumes) if applicable.
""",

    "command_rules": """Rules for Command generation:
1. Use standard Linux commands (Ubuntu/Debian compatible).
2. Avoid destructive commands (rm -rf /) unless explicitly requested and clearly dangerous.
3. Provide a single string command (can use pipes `|` and `&&`).
""",

    "clarification_rules": {
        "en": """Rules for Clarification:
1. You MUST ask questions in **English**.
2. Focus on ESSENTIALs: Version, Password, Persistence, Ports.
3. Do NOT ask for optional features unless the user mentioned them.
4. Group all questions into a single response.
""",
        "zh": """澄清提问规则:
1. 你必须使用**中文**进行提问。
2. 仅确认核心要素：软件版本 (Version)、密码 (Password)、数据持久化 (Persistence)、端口映射 (Ports)。
3. 不要询问非必要的配置，除非用户主动提及。
4. 将所有问题汇总在一次回复中，不要分多次问。
"""
    },

    "output_format": """Output Format:
You must strictly output JSON.
"""
}

def load_prompts() -> Dict:
    """Load prompts from file or return defaults."""
    if PROMPTS_FILE.exists():
        try:
            with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
                user_prompts = yaml.safe_load(f) or {}
                # Merge with defaults to ensure all keys exist
                final_prompts = DEFAULT_PROMPTS.copy()
                final_prompts.update(user_prompts)
                return final_prompts
        except Exception as e:
            print(f"Warning: Failed to load prompts: {e}")
            return DEFAULT_PROMPTS
    else:
        # Create default prompts file
        save_prompts(DEFAULT_PROMPTS)
        return DEFAULT_PROMPTS

def save_prompts(prompts: Dict):
    """Save prompts to file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(PROMPTS_FILE, "w", encoding="utf-8") as f:
        yaml.dump(prompts, f, allow_unicode=True, default_flow_style=False)

def get_system_prompt(lang: str = "en") -> str:
    """Generate the full system prompt based on language."""
    prompts = load_prompts()
    
    # Get clarification rules based on language
    clarification_rules = prompts["clarification_rules"].get(lang, prompts["clarification_rules"]["en"])
    
    full_prompt = f"""
{prompts['role_definition']}

{prompts['deployment_rules']}

{prompts['command_rules']}

{clarification_rules}

{prompts['output_format']}
"""
    return full_prompt
