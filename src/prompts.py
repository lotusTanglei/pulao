"""
AI 提示词管理模块

本模块负责管理 AI 对话系统的提示词（Prompts），包括：
1. 预定义提示词模板（中文和英文）
2. 提示词文件加载和保存
3. 动态生成系统提示词（包含实时系统信息）

提示词类型：
- role_definition: AI 角色定义
- deployment_rules: 部署规则
- command_rules: 命令生成规则
- system_context_intro: 系统上下文介绍
- clarification_rules: 澄清提问规则
- output_format: 输出格式说明

配置文件：~/.pulao/prompts_en.yaml, ~/.pulao/prompts_zh.yaml
"""

# ============ 标准库导入 ============
import yaml
import json
from pathlib import Path
from typing import Dict

# ============ 本地模块导入 ============
from src.config import CONFIG_DIR  # 配置目录
from src.system_ops import get_system_info  # 系统信息收集
from src.cluster import ClusterManager  # 集群管理


# ============ 提示词文件路径函数 ============

def get_prompts_file(lang: str) -> Path:
    """
    获取指定语言的提示词文件路径
    
    参数:
        lang: 语言代码（如 "en", "zh"）
    
    返回:
        提示词文件路径
    
    注意:
        - 英文: prompts_en.yaml
        - 中文: prompts_zh.yaml
    """
    return CONFIG_DIR / f"prompts_{lang}.yaml"


# ============ 提示词模板定义 ============

PROMPT_TEMPLATES = {
    "en": {
        "role_definition": """You are a DevOps expert specializing in Linux, Docker, and Cluster Management.
Your goal is to help users deploy middleware (single-node or multi-node) OR execute system operations.

Process:
1. Analyze the user's request.
2. If the request is vague, ask clarifying questions using normal chat (no tool call).
3. **Use Tools**: You have access to tools like:
   - `deploy_service` (single node), `deploy_cluster_service` (multi-node)
   - `execute_command` (system checks)
   - `create_cluster`, `add_node`, `list_clusters` (cluster management)
   - `update_template_library` (update templates)
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
Use Function Calling (Tools) for actions. 
If you need to ask a question to the user, just output the question as plain text. 
**Do NOT output JSON blocks like {"type": "question"}.**
"""
    },
    
    "zh": {
        "role_definition": """你是一位精通 Linux、Docker 和集群管理的 DevOps 专家。
你的目标是帮助用户部署中间件（单机或多机集群）或执行系统运维操作。

处理流程:
1. 分析用户请求。
2. 如果请求模糊，请**直接用自然语言**提问（不要使用 JSON 格式）。
3. **使用工具**: 你可以使用以下工具：
   - `deploy_service` (单机部署), `deploy_cluster_service` (集群部署)
   - `execute_command` (系统检查)
   - `create_cluster`, `add_node`, `list_clusters` (集群管理)
   - `update_template_library` (更新模板)
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
请使用函数调用 (Tools) 执行操作。
如果需要向用户提问，请直接输出纯文本问题。
**严禁输出 {"type": "question", ...} 这种 JSON 格式！**
"""
    }
}


# ============ 提示词加载/保存函数 ============

def load_prompts(lang: str = "en") -> Dict:
    """
    加载提示词配置
    
    加载顺序：
    1. 尝试从用户配置文件加载 (prompts_en.yaml 或 prompts_zh.yaml)
    2. 如果文件不存在，使用默认模板并创建配置文件
    3. 如果加载失败，使用内存中的默认模板
    
    参数:
        lang: 语言代码（默认 "en"）
    
    返回:
        提示词字典
    """
    if lang not in PROMPT_TEMPLATES:
        lang = "en"
        
    defaults = PROMPT_TEMPLATES[lang]
    prompts_file = get_prompts_file(lang)
    
    if prompts_file.exists():
        try:
            with open(prompts_file, "r", encoding="utf-8") as f:
                user_prompts = yaml.safe_load(f) or {}
                # 深度合并用户配置和默认配置
                final_prompts = defaults.copy()
                final_prompts.update(user_prompts)
                return final_prompts
        except Exception as e:
            print(f"Warning: Failed to load prompts from {prompts_file}: {e}")
            return defaults
    else:
        # 创建默认提示词文件
        save_prompts(defaults, lang)
        return defaults


def save_prompts(prompts: Dict, lang: str):
    """
    保存提示词到配置文件
    
    参数:
        prompts: 提示词字典
        lang: 语言代码
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    prompts_file = get_prompts_file(lang)
    with open(prompts_file, "w", encoding="utf-8") as f:
        yaml.dump(prompts, f, allow_unicode=True, default_flow_style=False)


# ============ 系统提示词生成函数 ============

def get_system_prompt(lang: str = "en") -> str:
    """
    生成完整的系统提示词
    
    动态生成包含以下内容的系统提示词：
    1. AI 角色定义
    2. 系统上下文（本地信息和集群节点信息）
    3. 部署规则
    4. 命令生成规则
    5. 澄清提问规则
    6. 输出格式要求
    
    参数:
        lang: 语言代码（默认 "en"）
    
    返回:
        完整的系统提示字符串
    
    系统上下文包含：
    - 本地系统信息：OS版本、IP、Docker版本、运行中的容器、监听端口
    - 集群节点信息：节点名称、主机、用户、角色、状态
    """
    prompts = load_prompts(lang)
    
    # 获取澄清规则（处理不同格式）
    clarification_rules_dict = prompts.get("clarification_rules", {})
    if isinstance(clarification_rules_dict, str):
         clarification_rules = clarification_rules_dict
    else:
         clarification_rules = clarification_rules_dict.get(lang, clarification_rules_dict.get("en", ""))
    
    # 步骤1: 获取本机系统信息
    local_info = get_system_info()
    
    # 步骤2: 获取集群节点信息
    try:
        nodes = ClusterManager.get_current_nodes()
        if nodes:
            cluster_info = json.dumps(nodes, indent=2, ensure_ascii=False)
            cluster_context = f"\n[Cluster Nodes ({ClusterManager.get_current_cluster_name()})]\n{cluster_info}"
        else:
            cluster_context = "\n[Cluster Nodes]\nNo nodes configured in current cluster."
    except Exception as e:
        cluster_context = f"\n[Cluster Nodes]\nError loading nodes: {e}"
    
    # 步骤3: 获取系统上下文介绍
    system_context_intro = prompts.get("system_context_intro", "\nSystem Context:\n")
    
    # 步骤4: 组合完整上下文
    system_context = f"{system_context_intro}\n{local_info}\n{cluster_context}\n"
    
    # 步骤5: 拼接完整提示词
    full_prompt = f"""
{prompts['role_definition']}

{system_context}

{prompts['deployment_rules']}

{prompts['command_rules']}

{clarification_rules}

{prompts['output_format']}
"""
    return full_prompt
