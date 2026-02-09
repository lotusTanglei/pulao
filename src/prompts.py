import yaml
from pathlib import Path
from typing import Dict
from src.config import CONFIG_DIR

PROMPTS_FILE = CONFIG_DIR / "prompts.yaml"

# Prompt templates by language
PROMPT_TEMPLATES = {
    "en": {
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
"""
        },
        "output_format": """Output Format:
You must strictly output JSON.
"""
    },
    
    "zh": {
        "role_definition": """你是一位精通 Linux 和 Docker 的 DevOps 专家。
你的目标是帮助用户部署中间件或执行系统运维操作。

处理流程:
1. 分析用户请求。
2. 如果请求模糊（例如仅说“安装 redis”），你必须提出澄清问题。
   - 返回 JSON: {"type": "question", "content": "你的澄清问题"}
3. 如果是部署任务（例如“部署 redis”，“安装 mysql”）：
   - 生成有效的 `docker-compose.yml`。
   - 返回 JSON: {"type": "plan", "content": "yaml_content_here"}
4. 如果是通用系统命令（例如“查看磁盘使用率”，“删除所有容器”，“ping google.com”）：
   - 生成一个安全且正确的 Bash 命令。
   - 返回 JSON: {"type": "command", "content": "bash_command_here"}
""",
        "deployment_rules": """YAML 生成规则:
1. 输出必须是有效的 `docker-compose.yml`。
2. 不要包含顶层的 'version' 字段。
3. 使用标准的官方镜像。
4. 如果适用，确保数据持久化（volumes）。
""",
        "command_rules": """命令生成规则:
1. 使用标准的 Linux 命令（兼容 Ubuntu/Debian）。
2. 避免破坏性命令（如 rm -rf /），除非用户明确要求且知晓风险。
3. 提供单行命令（可以使用管道 `|` 和 `&&`）。
""",
        "clarification_rules": {
            "zh": """澄清提问规则:
1. 你必须使用**中文**进行提问。
2. 仅确认核心要素：软件版本 (Version)、密码 (Password)、数据持久化 (Persistence)、端口映射 (Ports)。
3. 不要询问非必要的配置，除非用户主动提及。
4. 将所有问题汇总在一次回复中，不要分多次问。
"""
        },
        "output_format": """输出格式:
你必须严格输出 JSON 格式。
"""
    }
}

def load_prompts(lang: str = "en") -> Dict:
    """Load prompts from file or return defaults based on language."""
    # Ensure lang is supported, fallback to en
    if lang not in PROMPT_TEMPLATES:
        lang = "en"
        
    defaults = PROMPT_TEMPLATES[lang]
    
    if PROMPTS_FILE.exists():
        try:
            with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
                user_prompts = yaml.safe_load(f) or {}
                # Check if user prompts match current language structure (simple heuristic)
                # If user manually edited prompts.yaml, we prioritize their file content
                # regardless of language setting, to respect user customization.
                # However, if prompts.yaml was auto-generated for a different language, 
                # we might want to regenerate it? 
                # For simplicity: If prompts.yaml exists, use it. 
                # If keys are missing, fill from defaults of current language.
                final_prompts = defaults.copy()
                final_prompts.update(user_prompts)
                return final_prompts
        except Exception as e:
            print(f"Warning: Failed to load prompts: {e}")
            return defaults
    else:
        # Create default prompts file for the specific language
        save_prompts(defaults)
        return defaults

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
