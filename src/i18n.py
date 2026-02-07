from typing import Dict

# Translation dictionary
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
        "cli_desc": "AI-Ops: Natural Language Middleware Deployment Tool",
        "cli_config_help": "Configure AI API settings (Key, URL, Model).",
        "cli_deploy_help": "Deploy middleware using natural language.",
        "enter_instruction": "Please describe what you want to deploy",
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
        "cli_desc": "AI-Ops: 自然语言中间件部署工具",
        "cli_config_help": "配置 AI API 设置 (Key, URL, 模型)。",
        "cli_deploy_help": "使用自然语言部署中间件。",
        "enter_instruction": "请描述您想部署什么",
    }
}

# Global language setting (default to 'en')
_CURRENT_LANG = "en"

def set_language(lang: str):
    global _CURRENT_LANG
    if lang in TRANSLATIONS:
        _CURRENT_LANG = lang

def get_text(key: str, **kwargs) -> str:
    """Get translated text by key."""
    lang_dict = TRANSLATIONS.get(_CURRENT_LANG, TRANSLATIONS["en"])
    text = lang_dict.get(key, key)
    if kwargs:
        return text.format(**kwargs)
    return text

def t(key: str, **kwargs) -> str:
    """Alias for get_text"""
    return get_text(key, **kwargs)
