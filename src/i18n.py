"""
国际化 (i18n) 模块

本模块提供多语言支持功能，目前支持英文 (en) 和中文 (zh)。

主要功能：
1. 翻译字典管理：存储所有 UI 文本的翻译
2. 语言切换：动态切换当前语言
3. 翻译查询：根据 key 获取对应语言的文本
4. 格式化支持：支持占位符格式化

使用方式：
    from src.i18n import t
    print(t("deployment_success"))  # 输出: ✅ 部署成功!
    print(t("config_saved", path="/path/to/config"))  # 输出: ✅ 配置已保存至 /path/to/config

翻译覆盖范围：
    - CLI 界面文本
    - 错误提示信息
    - 确认提示信息
    - 安装向导文本
    - 部署状态消息
"""

# ============ 标准库导入 ============
from typing import Dict

# ============ 翻译字典定义 ============

TRANSLATIONS = {
    "en": {
        "config_title": "🔧 AI-Ops Configuration",
        "enter_api_key": "Enter API Key",
        "enter_base_url": "Enter Base URL",
        "enter_model": "Enter Model Name",
        "config_saved": "✅ Configuration saved to {path}",
        "api_key_missing": "❌ API Key is missing. Please run 'ai-ops config' first.",
        "analyzing_request": "🤖 Analyzing request:",
        "error_prefix": "❌ Error:",
        "ai_error": "AI Error:",
        "deployment_success": "✅ Deployment successful!",
        "deployment_failed": "❌ Deployment failed!",
        "written_compose": "📄 Written compose file to: {path}",
        "executing_compose": "🚀 Executing 'docker compose up -d' in {path}...",
        "compose_failed": "Docker compose failed",
        "error_executing_compose": "❌ Error executing docker compose:",
        "sending_request": "Sending request to AI model...",
        "proposed_config": "\n📋 Proposed Configuration:",
        "confirm_deploy": "🚀 Do you want to deploy this configuration?",
        "deploy_cancelled": "Deployment cancelled.",
        "install_start": "🚀 Starting installation of {app_name}...",
        "run_as_root": "Please run as root (sudo ./install.sh)",
        "updating_system": "📦 Updating system repositories...",
        "installing_docker": "🐳 Docker not found. Installing Docker...",
        "docker_installed": "✅ Docker installed.",
        "docker_already_installed": "✅ Docker is already installed.",
        "setup_dir": "📂 Setting up installation directory at {dir}...",
        "setup_venv": "🐍 Setting up Python virtual environment...",
        "installing_deps": "⬇️ Installing Python dependencies...",
        "creating_command": "🔗 Creating system command '{bin_name}'...",
        "install_complete": "🎉 Installation Complete!",
        "try_command": "👉 You can now use the command: {bin_name}",
        "try_help": "   Try: {bin_name} --help",
        "lang_select": "Please select language / 请选择语言:",
        "invalid_choice": "Invalid choice, defaulting to English. / 无效选择，默认使用英语。",
        "cli_desc": "Natural Language Middleware Deployment Tool",
        "cli_config_help": "Configure AI API settings (Key, URL, Model).",
        "cli_deploy_help": "Deploy middleware using natural language.",
        "enter_instruction": "Please describe what you want to deploy",
        "clarification_needed": "🤔 AI needs more details:",
        "clarification_prompt": "Please provide the details (or press Enter to skip): ",
        "executing_command": "Executing Shell Command",
        "command_success": "✅ Command executed successfully.",
        "command_failed": "❌ Command failed with non-zero exit code.",
        "error_executing_command": "❌ Error executing command:",
        "proposed_command": "\n💻 Proposed Command:",
        "confirm_execute": "🚀 Do you want to execute this command?",
        "request_cancelled": "\n⚠️ Request cancelled by user.",
        "confirm_project_name": "Project Name (Enter to use '{default}')",
        "node_online": "✅ Node is Online.",
        "node_auth_failed": "⚠️ Authentication Failed.",
        "auth_failed_guide": """
⚠️ Unable to connect to node '{name}'.
Please manually configure SSH trust on your control machine:
  ssh-copy-id -i ~/.ssh/id_rsa.pub {user}@{host}
""",
        "deploy_aborted_auth_fail": "❌ Deployment aborted: Authentication failed for some nodes.",
    },
    "zh": {
        "config_title": "🔧 AI-Ops 配置",
        "enter_api_key": "请输入 API Key",
        "enter_base_url": "请输入 Base URL",
        "enter_model": "请输入模型名称 (Model Name)",
        "config_saved": "✅ 配置已保存至 {path}",
        "api_key_missing": "❌ 缺少 API Key。请先运行 'ai-ops config'。",
        "analyzing_request": "🤖 正在分析需求:",
        "error_prefix": "❌ 错误:",
        "ai_error": "AI 错误:",
        "deployment_success": "✅ 部署成功!",
        "deployment_failed": "❌ 部署失败!",
        "written_compose": "📄 已写入 Compose 文件: {path}",
        "executing_compose": "🚀 正在 {path} 执行 'docker compose up -d'...",
        "compose_failed": "Docker compose 执行失败",
        "error_executing_compose": "❌ 执行 docker compose 时出错:",
        "sending_request": "正在向 AI 模型发送请求...",
        "proposed_config": "\n📋 建议的配置:",
        "confirm_deploy": "🚀 是否部署此配置?",
        "deploy_cancelled": "部署已取消。",
        "install_start": "🚀 开始安装 {app_name}...",
        "run_as_root": "请以 root 身份运行 (sudo ./install.sh)",
        "updating_system": "📦 正在更新系统软件源...",
        "installing_docker": "🐳 未找到 Docker。正在安装 Docker...",
        "docker_installed": "✅ Docker 安装完成。",
        "docker_already_installed": "✅ Docker 已安装。",
        "setup_dir": "📂 正在设置安装目录 {dir}...",
        "setup_venv": "🐍 正在配置 Python 虚拟环境...",
        "installing_deps": "⬇️ 正在安装 Python 依赖...",
        "creating_command": "🔗 正在创建系统命令 '{bin_name}'...",
        "install_complete": "🎉 安装完成!",
        "try_command": "👉 现在可以使用命令: {bin_name}",
        "try_help": "   尝试运行: {bin_name} --help",
        "lang_select": "Please select language / 请选择语言:",
        "invalid_choice": "Invalid choice, defaulting to English. / 无效选择，默认使用英语。",
        "cli_desc": "自然语言中间件部署工具",
        "cli_config_help": "配置 AI API 设置 (Key, URL, 模型)。",
        "cli_deploy_help": "使用自然语言部署中间件。",
        "enter_instruction": "请描述您想部署什么",
        "clarification_needed": "🤔 AI 需要更多细节:",
        "clarification_prompt": "请补充细节 (或按回车跳过): ",
        "executing_command": "执行 Shell 命令",
        "command_success": "✅ 命令执行成功。",
        "command_failed": "❌ 命令执行失败 (退出码非 0)。",
        "error_executing_command": "❌ 执行命令时出错:",
        "proposed_command": "\n💻 建议执行的命令:",
        "confirm_execute": "🚀 是否执行此命令?",
        "request_cancelled": "\n⚠️ 用户已取消请求。",
        "confirm_project_name": "确认项目名称 (回车使用 '{default}')",
        "node_online": "✅ 节点在线。",
        "node_auth_failed": "⚠️ 认证失败。",
        "auth_failed_guide": """
⚠️ 无法连接到节点 '{name}'。
请在控制端手动配置免密登录：
  ssh-copy-id -i ~/.ssh/id_rsa.pub {user}@{host}
""",
        "deploy_aborted_auth_fail": "❌ 部署已终止：部分节点认证失败。",
    }
}


# ============ 全局语言设置 ============

# 当前语言，默认为英文
_CURRENT_LANG = "en"


# ============ 语言切换函数 ============

def set_language(lang: str):
    """
    设置当前语言
    
    参数:
        lang: 语言代码 ("en" 或 "zh")
    
    注意:
        - 如果传入无效语言代码，不会切换
        - 语言设置保存在内存中，程序退出后重置
    """
    global _CURRENT_LANG
    if lang in TRANSLATIONS:
        _CURRENT_LANG = lang


# ============ 翻译查询函数 ============

def get_text(key: str, **kwargs) -> str:
    """
    根据 key 获取翻译文本
    
    参数:
        key: 翻译文本的 key
        **kwargs: 格式化参数，用于替换文本中的占位符
    
    返回:
        翻译后的文本字符串
    
    示例:
        t("config_saved", path="/home/user/config")  # 返回: ✅ 配置已保存至 /home/user/config
    """
    lang_dict = TRANSLATIONS.get(_CURRENT_LANG, TRANSLATIONS["en"])
    text = lang_dict.get(key, key)
    if kwargs:
        return text.format(**kwargs)
    return text


def t(key: str, **kwargs) -> str:
    """
    翻译函数的简写别名
    
    这是模块的主要导出接口，推荐使用此函数进行翻译查询。
    
    参数:
        key: 翻译文本的 key
        **kwargs: 格式化参数
    
    返回:
        翻译后的文本字符串
    """
    return get_text(key, **kwargs)
