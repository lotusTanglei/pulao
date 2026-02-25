
import yaml
import json
from pathlib import Path
from typing import Dict
from src.config import CONFIG_DIR

# Use language-specific prompt file (e.g., prompts_en.yaml, prompts_zh.yaml)
# This avoids overwriting prompts when switching languages.
def get_prompts_file(lang: str) -> Path:
    return CONFIG_DIR / f"prompts_{lang}.yaml"

# Prompt templates by language
PROMPT_TEMPLATES = {
    "en": {
        "role_definition": """You are a DevOps expert specializing in Linux, Docker, and Cluster Management.
Your goal is to help users deploy middleware (single-node or multi-node) OR execute system operations.

Process:
1. Analyze the user's request.
2. If the request is vague, ask clarifying questions using normal chat (no tool call).
3. **Use Tools**: You have access to tools like `deploy_service`, `deploy_cluster_service`, and `execute_command`.
   - To check system status, use `execute_command`.
   - To deploy, generate the YAML and call `deploy_service` or `deploy_cluster_service`.
   - ALWAYS verify prerequisites if possible (e.g. check ports) before deploying.
4. **Reasoning**: Explain your plan step-by-step before calling tools.
""",
        "deployment_rules": """Rules for YAML generation:
1. Output MUST be valid `docker-compose.yml` content passed as string argument to tools.
2. Do NOT include top-level 'version' field.
3. Use standard official images.
4. For multi-node setup, ensure network connectivity.
""",
        "command_rules": """Rules for Command generation:
1. Use standard Linux commands.
2. Avoid destructive commands unless explicitly requested.
""",
        "system_context_intro": """
System Context:
The following is the real-time information of the Local Server and Cluster Nodes.
""",
        "clarification_rules": {
            "en": """Rules for Clarification:
1. Ask in English.
2. Focus on ESSENTIALs.
"""
        },
        "output_format": """Output Format:
Use Function Calling (Tools) for actions. Do NOT output raw JSON blocks.
"""
    },
    
    "zh": {
        "role_definition": """你是一位精通 Linux、Docker 和集群管理的 DevOps 专家。
你的目标是帮助用户部署中间件（单机或多机集群）或执行系统运维操作。

处理流程:
1. 分析用户请求。
2. 如果请求模糊，请直接提问（不调用工具）。
3. **使用工具**: 你可以使用 `deploy_service`, `deploy_cluster_service`, `execute_command` 等工具。
   - 检查系统状态，使用 `execute_command`。
   - 部署服务，生成 YAML 并调用 `deploy_service` 或 `deploy_cluster_service`。
   - 尽可能在部署前验证先决条件（如检查端口）。
4. **推理**: 在调用工具前，逐步解释你的计划。
""",
        "deployment_rules": """YAML 生成规则:
1. 输出必须是有效的 `docker-compose.yml` 内容，作为字符串参数传递给工具。
2. 不要包含顶层的 'version' 字段。
3. 使用官方镜像。
4. 对于多机部署，确保网络连通性。
""",
        "command_rules": """命令生成规则:
1. 使用标准 Linux 命令。
2. 避免破坏性命令。
""",
        "system_context_intro": """
系统上下文 (System Context):
以下是本机和集群节点的实时信息。
""",
        "clarification_rules": {
            "zh": """澄清提问规则:
1. 必须使用**中文**提问。
2. 确认核心要素。
"""
        },
        "output_format": """输出格式:
请使用函数调用 (Tools) 执行操作。**不要**输出原始 JSON 代码块。
"""
    }
}

def load_prompts(lang: str = "en") -> Dict:
    """Load prompts from file or return defaults based on language."""
    if lang not in PROMPT_TEMPLATES:
        lang = "en"
        
    defaults = PROMPT_TEMPLATES[lang]
    prompts_file = get_prompts_file(lang)
    
    if prompts_file.exists():
        try:
            with open(prompts_file, "r", encoding="utf-8") as f:
                user_prompts = yaml.safe_load(f) or {}
                # Deep merge defaults with user prompts
                final_prompts = defaults.copy()
                final_prompts.update(user_prompts)
                return final_prompts
        except Exception as e:
            print(f"Warning: Failed to load prompts from {prompts_file}: {e}")
            return defaults
    else:
        # Create default prompts file
        save_prompts(defaults, lang)
        return defaults

def save_prompts(prompts: Dict, lang: str):
    """Save prompts to file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    prompts_file = get_prompts_file(lang)
    with open(prompts_file, "w", encoding="utf-8") as f:
        yaml.dump(prompts, f, allow_unicode=True, default_flow_style=False)

from src.system_ops import get_system_info
from src.cluster import ClusterManager

def get_system_prompt(lang: str = "en") -> str:
    """Generate the full system prompt based on language."""
    prompts = load_prompts(lang)
    
    clarification_rules_dict = prompts.get("clarification_rules", {})
    if isinstance(clarification_rules_dict, str):
         clarification_rules = clarification_rules_dict
    else:
         clarification_rules = clarification_rules_dict.get(lang, clarification_rules_dict.get("en", ""))
    
    # 1. Get Local System Info
    local_info = get_system_info()
    
    # 2. Get Cluster Nodes Info
    try:
        nodes = ClusterManager.get_current_nodes()
        if nodes:
            cluster_info = json.dumps(nodes, indent=2, ensure_ascii=False)
            cluster_context = f"\n[Cluster Nodes ({ClusterManager.get_current_cluster_name()})]\n{cluster_info}"
        else:
            cluster_context = "\n[Cluster Nodes]\nNo nodes configured in current cluster."
    except Exception as e:
        cluster_context = f"\n[Cluster Nodes]\nError loading nodes: {e}"
    
    # Get system context intro prompt
    system_context_intro = prompts.get("system_context_intro", "\nSystem Context:\n")
    
    system_context = f"{system_context_intro}\n{local_info}\n{cluster_context}\n"
    
    full_prompt = f"""
{prompts['role_definition']}

{system_context}

{prompts['deployment_rules']}

{prompts['command_rules']}

{clarification_rules}

{prompts['output_format']}
"""
    return full_prompt
