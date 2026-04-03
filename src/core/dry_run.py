"""
Dry-Run 执行计划模块

生成执行计划预览，展示将要执行的操作和风险评估。
"""

import uuid
from dataclasses import dataclass
from typing import List, Optional

from .risk_guard import RiskGuard, RiskAssessment, RiskLevel


@dataclass
class ExecutionStep:
    """执行步骤"""
    step_id: int
    tool_name: str
    arguments: dict
    risk_assessment: RiskAssessment
    preview_text: str


@dataclass
class ExecutionPlan:
    """执行计划"""
    plan_id: str
    steps: List[ExecutionStep]
    total_risk: RiskLevel
    summary: str
    rollback_hint: Optional[str]


class DryRunExecutor:
    """
    Dry-Run 执行器

    生成执行计划预览，不实际执行操作。
    """

    # 工具预览模板
    PREVIEW_TEMPLATES = {
        "deploy_service": "部署服务 '{project_name}'",
        "deploy_cluster_service": "集群部署 '{project_name}'",
        "restart_docker_container": "重启容器 '{container_name}'",
        "stop_docker_container": "停止容器 '{container_name}'",
        "rollback_deploy": "回滚服务 '{project_name}'",
        "execute_command": "执行命令: {command}",
        "push_changes": "推送变更: {message}",
        "get_logs": "获取容器日志 '{container_name}'",
        "list_docker_containers": "列出所有容器",
        "check_container": "检查容器状态 '{container_name}'",
        "diagnose": "诊断服务 '{service_name}'",
        "search_kb": "搜索知识库: {query}",
        "query_audit_logs": "查询审计日志",
        "git_status": "查看 Git 状态",
        "gitops_status": "查看 GitOps 状态",
    }

    def __init__(self, risk_guard: RiskGuard):
        self.risk_guard = risk_guard

    def generate_plan(self, tool_calls: List[dict]) -> ExecutionPlan:
        """
        生成执行计划

        Args:
            tool_calls: 工具调用列表，每个包含 name, args, id

        Returns:
            ExecutionPlan: 执行计划
        """
        steps = []
        highest_risk = RiskLevel.READONLY

        for i, tc in enumerate(tool_calls, 1):
            tool_name = tc.get("name", "unknown")
            args = tc.get("args", {})

            # 风险评估
            assessment = self.risk_guard.assess(tool_name, args)

            # 更新最高风险
            if self._risk_level_value(assessment.risk_level) > self._risk_level_value(highest_risk):
                highest_risk = assessment.risk_level

            # 生成预览
            preview = self._generate_preview(tool_name, args)

            steps.append(ExecutionStep(
                step_id=i,
                tool_name=tool_name,
                arguments=args,
                risk_assessment=assessment,
                preview_text=preview
            ))

        return ExecutionPlan(
            plan_id=f"plan_{uuid.uuid4().hex[:8]}",
            steps=steps,
            total_risk=highest_risk,
            summary=self._generate_summary(steps),
            rollback_hint=self._generate_rollback_hint(steps)
        )

    def _generate_preview(self, tool_name: str, args: dict) -> str:
        """生成操作预览"""
        template = self.PREVIEW_TEMPLATES.get(tool_name, f"执行 {tool_name}")

        try:
            return template.format(**args)
        except KeyError:
            # 参数不完整时返回模板
            return template

    def _generate_summary(self, steps: List[ExecutionStep]) -> str:
        """生成摘要"""
        total = len(steps)
        if total == 0:
            return "无操作"

        risk_counts = {}
        for step in steps:
            level = step.risk_assessment.risk_level.value
            risk_counts[level] = risk_counts.get(level, 0) + 1

        parts = [f"共 {total} 个操作"]
        for level, count in sorted(risk_counts.items()):
            parts.append(f"{level}: {count}")

        return ", ".join(parts)

    def _generate_rollback_hint(self, steps: List[ExecutionStep]) -> Optional[str]:
        """生成回滚提示"""
        if len(steps) == 0:
            return None

        rollbackable = [s for s in steps if s.risk_assessment.rollback_possible]

        if len(rollbackable) == len(steps):
            return "所有操作均可回滚"
        elif len(rollbackable) == 0:
            return "⚠️  部分操作不可逆，请谨慎确认"
        else:
            return f"部分操作可回滚 ({len(rollbackable)}/{len(steps)})"

    @staticmethod
    def _risk_level_value(level: RiskLevel) -> int:
        """风险等级数值化"""
        values = {
            RiskLevel.READONLY: 0,
            RiskLevel.LOW: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.HIGH: 3,
            RiskLevel.CRITICAL: 4,
        }
        return values.get(level, 0)
