"""
日志系统模块

本模块负责应用程序的日志记录功能，提供统一的日志接口。

主要功能：
1. 日志目录和文件管理
2. 日志轮转（防止日志文件过大）
3. 分级日志记录（DEBUG, INFO, WARNING, ERROR, CRITICAL）
4. 双输出：文件（完整日志）+ 控制台（仅严重错误）

日志配置：
- 日志文件位置：~/.pulao/pulao.log
- 单文件大小限制：1MB
- 备份文件数量：5 个
- 控制台输出：仅 CRITICAL 级别（保持 stdout 干净给 Rich 使用）

异常处理：
- 如果用户目录不可写，回退到临时目录
- 如果日志文件创建失败，回退到临时目录
"""

# ============ 标准库导入 ============
import logging
import logging.handlers
from pathlib import Path
import sys

# ============ 本地模块导入 ============
from src.config import CONFIG_DIR  # 配置目录


# ============ 日志路径定义 ============

# 日志目录：使用配置目录
LOG_DIR = CONFIG_DIR

# 日志文件路径
LOG_FILE = LOG_DIR / "pulao.log"


# ============ 日志初始化函数 ============

def setup_logging():
    """
    初始化日志系统
    
    配置流程：
    1. 确保日志目录存在
    2. 如果目录不可写，回退到临时目录
    3. 配置日志记录器
    4. 添加文件处理器（轮转）
    5. 添加控制台处理器（仅 CRITICAL）
    
    日志级别：
    - 文件记录：DEBUG 及以上（完整日志）
    - 控制台输出：CRITICAL 及以上（仅严重错误）
    
    返回:
        配置好的 logger 对象
    
    异常处理：
        - PermissionError: 目录不可写时回退到临时目录
    """
    global LOG_FILE
    
    # 步骤1: 确保日志目录存在
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        # 目录不可写，回退到临时目录
        import tempfile
        global LOG_DIR_TEMP
        LOG_DIR_TEMP = Path(tempfile.gettempdir()) / "pulao"
        LOG_DIR_TEMP.mkdir(parents=True, exist_ok=True)
        LOG_FILE = LOG_DIR_TEMP / "pulao.log"

    # 步骤2: 创建日志记录器
    logger = logging.getLogger("pulao")
    logger.setLevel(logging.DEBUG)
    
    # 避免重复添加处理器
    if logger.handlers:
        return logger

    # 步骤3: 文件处理器（带轮转）
    # maxBytes=1024*1024: 单文件最大 1MB
    # backupCount=5: 保留 5 个备份文件
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=1024*1024, backupCount=5, encoding="utf-8"
        )
    except PermissionError:
        # 文件创建失败，再次回退到临时目录
        import tempfile
        LOG_FILE = Path(tempfile.gettempdir()) / "pulao" / "pulao.log"
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=1024*1024, backupCount=5, encoding="utf-8"
        )

    # 文件日志格式：完整格式，包含时间、名称、级别、消息
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    
    # 步骤4: 控制台处理器
    # 仅输出 CRITICAL 级别，保持 stdout 干净给 Rich 使用
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.CRITICAL)
    
    # 步骤5: 添加处理器到记录器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


# ============ 全局日志实例 ============

# 创建默认日志实例，供其他模块导入使用
logger = setup_logging()
