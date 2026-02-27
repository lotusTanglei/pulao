"""
配置管理模块

本模块负责 Pulao 应用的配置管理，包括：
1. 加载和保存用户配置
2. 管理多个 AI 提供商配置
3. 支持全局配置（系统级）和用户配置（个人级）
4. 配置版本迁移（兼容旧版本格式）

配置文件位置：
    - 用户配置: ~/.pulao/config.yaml
    - 全局配置: /opt/pulao/global_config.yaml

配置结构：
    - current_provider: 当前使用的 AI 提供商名称
    - providers: 提供商字典，每个提供商包含 api_key、base_url、model
    - language: 界面语言 (en/zh)
"""

# ============ 标准库导入 ============
import os
from pathlib import Path
from typing import Optional, Dict

# ============ 第三方库导入 ============
import yaml

# ============ 本地模块导入 ============
from src.i18n import set_language  # 设置界面语言


# ============ 配置目录和文件路径 ============

# 配置目录：优先使用用户主目录下的 .pulao 文件夹
# 如果没有写权限（如沙盒环境），则使用临时目录
try:
    CONFIG_DIR = Path.home() / ".pulao"
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
except PermissionError:
    # 回退到临时目录
    import tempfile
    CONFIG_DIR = Path(tempfile.gettempdir()) / "pulao"
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

# 用户配置文件路径
CONFIG_FILE = CONFIG_DIR / "config.yaml"

# 全局配置文件路径（系统级配置，多用户共享）
GLOBAL_CONFIG_FILE = Path("/opt/pulao/global_config.yaml")


# ============ 默认配置 ============

# 默认配置模板
# 包含一个默认的 "default" 提供商配置
DEFAULT_CONFIG = {
    "current_provider": "default",  # 当前使用的提供商名称
    "providers": {
        "default": {
            "api_key": "",  # API 密钥（用户需要填入）
            "base_url": "https://api.deepseek.com",  # DeepSeek API 端点
            "model": "deepseek-reasoner",  # 默认模型
        }
    },
    "language": "en"  # 默认语言为英文
}


# ============ 配置加载函数 ============

def load_config() -> Dict:
    """
    加载配置文件
    
    加载顺序（优先级从低到高）：
    1. 默认配置（最低优先级）
    2. 全局配置文件 (/opt/pulao/global_config.yaml)
    3. 用户配置文件 (~/.pulao/config.yaml)（最高优先级）
    
    配置合并规则：
    - 全局配置和用户配置的 providers 字典会合并
    - 同名配置项用户配置会覆盖全局配置
    
    返回:
        包含所有配置项的字典
    
    特殊处理：
    - 自动迁移旧版本的扁平配置结构到新的嵌套结构
    - 将当前提供商的配置展平到根层级（向后兼容）
    """
    # 从默认配置开始
    final_config = DEFAULT_CONFIG.copy()
    
    # 内部函数：迁移旧版扁平配置到新版嵌套结构
    # 旧版格式：{api_key: "...", base_url: "...", model: "..."}
    # 新版格式：{providers: {default: {api_key: "...", ...}}}
    def migrate_flat_config(cfg):
        # 如果配置中有 api_key 但没有 providers，说明是旧格式
        if "api_key" in cfg and "providers" not in cfg:
            return {
                "current_provider": "default",
                "providers": {
                    "default": {
                        "api_key": cfg.get("api_key", ""),
                        "base_url": cfg.get("base_url", ""),
                        "model": cfg.get("model", "")
                    }
                },
                "language": cfg.get("language", "en")
            }
        return cfg

    # ====== 步骤 1: 加载全局配置 ======
    if GLOBAL_CONFIG_FILE.exists():
        try:
            with open(GLOBAL_CONFIG_FILE, "r", encoding="utf-8") as f:
                global_config = yaml.safe_load(f) or {}
                # 处理旧格式迁移
                global_config = migrate_flat_config(global_config)
                
                # 合并 providers 字典
                if "providers" in global_config:
                    final_config["providers"].update(global_config["providers"])
                
                # 更新其他配置项（providers 除外）
                final_config.update({k: v for k, v in global_config.items() if k != "providers"})
        except Exception:
            pass  # 忽略全局配置加载错误

    # ====== 步骤 2: 加载用户配置 ======
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                user_config = yaml.safe_load(f) or {}
                # 处理旧格式迁移
                user_config = migrate_flat_config(user_config)
                
                # 合并 providers 字典
                if "providers" in user_config:
                    if "providers" not in final_config:
                        final_config["providers"] = {}
                    final_config["providers"].update(user_config["providers"])
                
                # 更新其他配置项
                final_config.update({k: v for k, v in user_config.items() if k != "providers"})
        except Exception as e:
            print(f"Warning: Failed to load config: {e}")
    
    # ====== 步骤 3: 向后兼容处理 ======
    # 将当前提供商的配置展平到根层级，方便旧代码访问
    # 新代码应该从 final_config["providers"][provider_name] 获取配置
    current_provider_name = final_config.get("current_provider", "default")
    provider_config = final_config.get("providers", {}).get(current_provider_name, {})
    
    final_config["api_key"] = provider_config.get("api_key", "")
    final_config["base_url"] = provider_config.get("base_url", "")
    final_config["model"] = provider_config.get("model", "")

    # ====== 步骤 4: 设置语言 ======
    # 加载完成后立即设置界面语言
    set_language(final_config.get("language", "en"))
            
    return final_config


def save_config(config_data: Dict):
    """
    保存配置到文件
    
    参数:
        config_data: 配置字典，会被保存到用户配置文件
    
    注意:
        - 会移除展平的配置项（api_key, base_url, model），只保存嵌套结构
        - 如果用户目录无写权限，会回退到临时目录
    
    返回:
        保存的配置文件路径
    """
    global CONFIG_FILE
    
    # 确保目录存在
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    # 复制配置，移除展平项（保持结构整洁）
    to_save = config_data.copy()
    to_save.pop("api_key", None)
    to_save.pop("base_url", None)
    to_save.pop("model", None)
    
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            yaml.dump(to_save, f)
    except PermissionError:
        # 权限错误，回退到临时文件
        import tempfile
        CONFIG_FILE = Path(tempfile.gettempdir()) / "pulao" / "config.yaml"
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            yaml.dump(to_save, f)
    
    # 更新运行时语言设置
    set_language(to_save.get("language", "en"))
    
    return CONFIG_FILE


# ============ 提供商管理函数 ============

def add_provider(name: str, api_key: str, base_url: str, model: str):
    """
    添加或更新 AI 提供商配置
    
    参数:
        name: 提供商名称（如 "deepseek", "openai", "azure"）
        api_key: API 密钥
        base_url: API 端点地址
        model: 模型名称
    
    逻辑:
        - 如果是第一个添加的自定义提供商（且 default 为空），自动切换到该提供商
        - 保存配置到文件
    
    返回:
        配置文件路径
    """
    # 加载当前配置
    cfg = load_config()
    
    # 确保 providers 字典存在
    if "providers" not in cfg:
        cfg["providers"] = {}
    
    # 设置或更新提供商配置
    cfg["providers"][name] = {
        "api_key": api_key,
        "base_url": base_url,
        "model": model
    }
    
    # 智能切换：如果 default 提供商还未配置，且添加的是其他提供商，自动切换
    if name != "default" and cfg["providers"].get("default", {}).get("api_key") == "":
        cfg["current_provider"] = name
        
    # 保存配置
    save_config(cfg)
    return CONFIG_FILE


def switch_provider(name: str):
    """
    切换当前使用的 AI 提供商
    
    参数:
        name: 提供商名称
    
    异常:
        ValueError: 如果提供商不存在
    
    注意:
        - 只修改 current_provider 字段
        - 会保存配置到文件
    """
    cfg = load_config()
    
    # 检查提供商是否存在
    if name not in cfg.get("providers", {}):
        raise ValueError(f"Provider '{name}' not found.")
    
    # 切换当前提供商
    cfg["current_provider"] = name
    
    # 保存配置
    save_config(cfg)
