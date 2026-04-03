"""
核心模块

提供配置、日志、国际化、安全框架等核心功能。
"""

from .config import load_config, add_provider, switch_provider
from .logger import logger
from .i18n import t, set_language

# 安全框架
from .risk_guard import RiskGuard, RiskLevel, RiskDecision, RiskAssessment
from .policy_store import PolicyStore, BUILTIN_RULES
from .dry_run import DryRunExecutor, ExecutionPlan, ExecutionStep
from .hitl import HITLController
from .audit import AuditLogger

__all__ = [
    # 配置
    "load_config",
    "add_provider",
    "switch_provider",
    # 日志
    "logger",
    # 国际化
    "t",
    "set_language",
    # 安全框架
    "RiskGuard",
    "RiskLevel",
    "RiskDecision",
    "RiskAssessment",
    "PolicyStore",
    "BUILTIN_RULES",
    "DryRunExecutor",
    "ExecutionPlan",
    "ExecutionStep",
    "HITLController",
    "AuditLogger",
]
