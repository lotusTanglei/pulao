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


class RiskGuard:
    """
    风险评估引擎

    评估每个工具调用的风险等级，决定执行策略。

    优先级: DENY > ALLOW > CONFIRM > 默认CONFIRM
    """

    def __init__(self, policy_store):
        """
        初始化风险评估引擎

        Args:
            policy_store: PolicyStore 实例，提供规则
        """
        self.policy_store = policy_store

    def assess(self, tool_name: str, arguments: dict) -> RiskAssessment:
        """
        评估工具调用风险

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            RiskAssessment: 风险评估结果
        """
        rules = self.policy_store.get_rules()

        # 1. 检查 DENY 规则（最高优先级）
        for rule in rules.get("deny", []):
            if self._match_pattern(tool_name, arguments, rule["pattern"]):
                return RiskAssessment(
                    tool_name=tool_name,
                    risk_level=RiskLevel.CRITICAL,
                    decision=RiskDecision.DENY,
                    reason=rule["reason"],
                    matched_rule=rule["pattern"],
                    affected_resources=self._extract_resources(arguments),
                    rollback_possible=False
                )

        # 2. 检查 ALLOW 规则（只读操作可直接执行）
        for rule in rules.get("allow", []):
            if self._match_pattern(tool_name, arguments, rule["pattern"]):
                return RiskAssessment(
                    tool_name=tool_name,
                    risk_level=RiskLevel.LOW,
                    decision=RiskDecision.ALLOW,
                    reason=rule["reason"],
                    matched_rule=rule["pattern"],
                    affected_resources=[],
                    rollback_possible=True
                )

        # 3. 检查 CONFIRM 规则
        for rule in rules.get("confirm", []):
            if self._match_pattern(tool_name, arguments, rule["pattern"]):
                risk_level = self._determine_risk_level(tool_name, arguments)
                return RiskAssessment(
                    tool_name=tool_name,
                    risk_level=risk_level,
                    decision=RiskDecision.CONFIRM,
                    reason=rule["reason"],
                    matched_rule=rule["pattern"],
                    affected_resources=self._extract_resources(arguments),
                    rollback_possible=self._check_rollback_possible(tool_name)
                )

        # 4. 默认需要确认（安全优先）
        return RiskAssessment(
            tool_name=tool_name,
            risk_level=RiskLevel.MEDIUM,
            decision=RiskDecision.CONFIRM,
            reason="未匹配任何规则，默认需要确认",
            matched_rule=None,
            affected_resources=self._extract_resources(arguments),
            rollback_possible=True
        )

    def _match_pattern(self, tool_name: str, arguments: dict, pattern: str) -> bool:
        """
        匹配规则模式

        支持：
        1. 通配符: restart_* 匹配 restart_docker_container
        2. 参数内容: rm -rf 匹配 execute_command 的 command 参数
        """
        import fnmatch

        # 通配符匹配工具名
        if "*" in pattern:
            if fnmatch.fnmatch(tool_name, pattern):
                return True

        # 精确匹配工具名
        if tool_name == pattern:
            return True

        # 参数内容匹配（针对 execute_command）
        if "command" in arguments:
            if pattern in str(arguments["command"]):
                return True

        return False

    def _determine_risk_level(self, tool_name: str, arguments: dict) -> RiskLevel:
        """确定风险等级"""
        # 检查是否涉及生产环境关键词
        prod_keywords = ["prod", "production", "live", "master", "main"]
        args_str = str(arguments).lower()

        for keyword in prod_keywords:
            if keyword in args_str:
                return RiskLevel.HIGH

        return RiskLevel.MEDIUM

    def _extract_resources(self, arguments: dict) -> List[str]:
        """提取受影响的资源"""
        resources = []
        for key in ["container_name", "project_name", "name", "service_name"]:
            if key in arguments:
                resources.append(str(arguments[key]))
        return resources

    def _check_rollback_possible(self, tool_name: str) -> bool:
        """检查是否可回滚"""
        non_rollback_tools = {"execute_command", "push_changes"}
        return tool_name not in non_rollback_tools
