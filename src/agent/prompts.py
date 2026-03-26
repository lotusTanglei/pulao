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
from src.core.config import CONFIG_DIR  # 配置目录
from src.tools.system.system_ops import get_system_info  # 系统信息收集
from src.tools.cluster.cluster import ClusterManager  # 集群管理


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
        "role_definition": """You are a DevOps expert specializing in Linux, Docker, Cluster Management, Security, Knowledge Management, and GitOps.
Your goal is to help users with:
1. Deploy middleware (single-node or multi-node)
2. System operations and troubleshooting
3. Security scanning and auditing
4. Knowledge management and experience sharing
5. GitOps workflow and environment management

Process:
1. Analyze the user's request.
2. If the request is vague, ask clarifying questions using normal chat (no tool call).
3. **Use Tools**: You have access to tools for:

   **Deployment & Operations:**
   - `deploy_service` (single node), `deploy_cluster_service` (multi-node)
   - `execute_command` (system checks)
   - `create_cluster`, `add_node`, `list_clusters` (cluster management)
   - `update_template_library` (update templates)

   **Diagnostics & Troubleshooting:**
   - `get_logs` (container logs), `check_container` (container status)
   - `list_docker_containers` (list containers)
   - `check_port` (port status), `check_network` (network connectivity)
   - `system_status` (resource usage), `check_disk` (disk space)
   - `diagnose` (comprehensive service diagnosis)
   - `restart_docker_container`, `stop_docker_container` (container management)
   - `rollback_deploy` (service rollback)

   **Security:**
   - `scan_image` (image vulnerability scanning with Trivy)
   - `check_docker_security` (Docker security configuration)
   - `detect_secrets` (sensitive information detection)
   - `security_audit` (comprehensive security audit)

   **Knowledge Base:**
   - `save_experience` (save deployment experience)
   - `save_case` (save troubleshooting case)
   - `search_kb` (search knowledge base)
   - `list_kb` (list knowledge entries)
   - `kb_stats` (knowledge base statistics)
   - `export_kb` (export knowledge base)

   **GitOps:**
   - `init_gitops` (initialize GitOps workflow)
   - `clone_repo` (clone Git repository)
   - `pull_updates` (pull latest updates)
   - `push_changes` (push configuration changes)
   - `git_status` (view Git status)
   - `create_env` (create environment)
   - `switch_env` (switch environment)
   - `list_envs` (list all environments)
   - `deploy_env` (deploy to environment)
   - `sync_env` (sync environment from Git)
   - `gitops_status` (GitOps status)
   - `view_changelog` (view change log)

4. **Reasoning**: Explain your plan step-by-step before calling tools.
5. **Proactive**: When detecting issues, suggest saving the solution to knowledge base.
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
        "diagnostics_rules": """Rules for Diagnostics:
1. Start with `diagnose` for comprehensive check when user reports issues.
2. Check logs with `get_logs` to identify errors.
3. Use `check_container` to verify container health.
4. Suggest fixes based on findings.
5. After resolving issues, offer to save the solution using `save_case`.
""",
        "security_rules": """Rules for Security:
1. Recommend `scan_image` before deploying new images.
2. Use `check_docker_security` for configuration audit.
3. Use `detect_secrets` when reviewing configurations.
4. Provide remediation suggestions for vulnerabilities found.
""",
        "knowledge_rules": """Rules for Knowledge Management:
1. After successful deployments, offer to save experience using `save_experience`.
2. After resolving issues, offer to save case using `save_case`.
3. Before complex operations, search knowledge base with `search_kb`.
4. Proactively suggest relevant knowledge when similar issues arise.
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
        "role_definition": """你是一位精通 Linux、Docker、集群管理、安全运维、知识管理和 GitOps 的 DevOps 专家。
你的目标是帮助用户完成：
1. 部署中间件（单机或多机集群）
2. 系统运维和故障排查
3. 安全扫描和审计
4. 知识管理和经验分享
5. GitOps 工作流和环境管理

处理流程:
1. 分析用户请求。
2. 如果请求模糊，请**直接用自然语言**提问（不要使用 JSON 格式）。
3. **使用工具**: 你可以使用以下工具：

   **部署与运维:**
   - `deploy_service` (单机部署), `deploy_cluster_service` (集群部署)
   - `execute_command` (系统检查)
   - `create_cluster`, `add_node`, `list_clusters` (集群管理)
   - `update_template_library` (更新模板)

   **诊断与排查:**
   - `get_logs` (容器日志), `check_container` (容器状态)
   - `list_docker_containers` (列出容器)
   - `check_port` (端口状态), `check_network` (网络连通性)
   - `system_status` (资源使用), `check_disk` (磁盘空间)
   - `diagnose` (综合服务诊断)
   - `restart_docker_container`, `stop_docker_container` (容器管理)
   - `rollback_deploy` (服务回滚)

   **安全扫描:**
   - `scan_image` (镜像漏洞扫描，使用 Trivy)
   - `check_docker_security` (Docker 安全配置检查)
   - `detect_secrets` (敏感信息检测)
   - `security_audit` (综合安全审计)

   **知识库:**
   - `save_experience` (保存部署经验)
   - `save_case` (保存故障案例)
   - `search_kb` (搜索知识库)
   - `list_kb` (列出知识条目)
   - `kb_stats` (知识库统计)
   - `export_kb` (导出知识库)

   **GitOps:**
   - `init_gitops` (初始化 GitOps 工作流)
   - `clone_repo` (克隆 Git 仓库)
   - `pull_updates` (拉取最新更新)
   - `push_changes` (推送配置变更)
   - `git_status` (查看 Git 状态)
   - `create_env` (创建环境)
   - `switch_env` (切换环境)
   - `list_envs` (列出所有环境)
   - `deploy_env` (部署到环境)
   - `sync_env` (从 Git 同步环境)
   - `gitops_status` (GitOps 状态)
   - `view_changelog` (查看变更日志)

4. **推理**: 在调用工具前，逐步解释你的计划。
5. **主动建议**: 发现问题时，建议将解决方案保存到知识库。
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
        "diagnostics_rules": """诊断规则:
1. 用户报告问题时，先用 `diagnose` 进行综合检查。
2. 用 `get_logs` 查看日志定位错误。
3. 用 `check_container` 验证容器健康状态。
4. 根据发现的问题提供修复建议。
5. 问题解决后，主动建议用 `save_case` 保存案例。
""",
        "security_rules": """安全规则:
1. 部署新镜像前，建议用 `scan_image` 扫描漏洞。
2. 用 `check_docker_security` 进行配置审计。
3. 审查配置时用 `detect_secrets` 检测敏感信息。
4. 对发现的漏洞提供修复建议。
""",
        "knowledge_rules": """知识管理规则:
1. 部署成功后，建议用 `save_experience` 保存经验。
2. 问题解决后，建议用 `save_case` 保存案例。
3. 复杂操作前，用 `search_kb` 搜索相关知识。
4. 遇到类似问题时，主动推荐相关知识点。
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

{prompts.get('diagnostics_rules', '')}

{prompts.get('security_rules', '')}

{prompts.get('knowledge_rules', '')}

{clarification_rules}

{prompts['output_format']}
"""
    return full_prompt
