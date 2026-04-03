"""
风险评估引擎

本模块负责评估每个工具调用的风险等级，决定是否需要人工确认或直接拒绝。
"""

from enum import Enum
from typing import List, Optional
from dataclasses import dataclass


class RiskLevel(Enum):
    """风险等级"""
    READONLY = "readonly"      # 只读，无需确认
    LOW = "low"                # 低风险，直接执行
    MEDIUM = "medium"          # 中风险，需确认
    HIGH = "high"              # 高风险，需确认 + 详细说明
    CRITICAL = "critical"      # 危险，直接拒绝


class RiskDecision(Enum):
    """风险决策"""
    ALLOW = "allow"            # 直接执行
    CONFIRM = "confirm"        # 需要确认
    DENY = "deny"              # 拒绝执行


@dataclass
class RiskAssessment:
    """风险评估结果"""
    tool_name: str
    risk_level: RiskLevel
    decision: RiskDecision
    reason: str                          # 风险原因
    matched_rule: Optional[str]          # 匹配的规则
    affected_resources: List[str]        # 影响的资源
    rollback_possible: bool              # 是否可回滚
