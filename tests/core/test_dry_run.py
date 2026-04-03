"""
DryRunExecutor 单元测试
"""

import pytest
from src.core.dry_run import DryRunExecutor, ExecutionPlan, ExecutionStep
from src.core.risk_guard import RiskGuard, RiskLevel, RiskDecision
from src.core.policy_store import PolicyStore


@pytest.fixture
def dry_run_executor():
    return DryRunExecutor(RiskGuard(PolicyStore()))


class TestDryRunExecutor:
    """DryRunExecutor 测试"""

    def test_generate_single_step_plan(self, dry_run_executor):
        """生成单步执行计划"""
        tool_calls = [
            {"name": "restart_docker_container", "args": {"container_name": "web"}, "id": "call_1"}
        ]

        plan = dry_run_executor.generate_plan(tool_calls)

        assert plan.plan_id.startswith("plan_")
        assert len(plan.steps) == 1
        assert plan.steps[0].tool_name == "restart_docker_container"

    def test_generate_multi_step_plan(self, dry_run_executor):
        """生成多步执行计划"""
        tool_calls = [
            {"name": "get_logs", "args": {"container_name": "web"}, "id": "call_1"},
            {"name": "restart_docker_container", "args": {"container_name": "web"}, "id": "call_2"},
        ]

        plan = dry_run_executor.generate_plan(tool_calls)

        assert len(plan.steps) == 2
        assert plan.steps[0].tool_name == "get_logs"
        assert plan.steps[1].tool_name == "restart_docker_container"

    def test_total_risk_is_highest(self, dry_run_executor):
        """整体风险应取最高"""
        tool_calls = [
            {"name": "get_logs", "args": {"container_name": "web"}, "id": "call_1"},
            {"name": "restart_docker_container", "args": {"container_name": "web"}, "id": "call_2"},
        ]

        plan = dry_run_executor.generate_plan(tool_calls)

        # restart 是 MEDIUM，get_logs 是 LOW
        assert plan.total_risk == RiskLevel.MEDIUM

    def test_preview_text_generation(self, dry_run_executor):
        """预览文本应正确生成"""
        tool_calls = [
            {"name": "deploy_service", "args": {"project_name": "my-app"}, "id": "call_1"},
        ]

        plan = dry_run_executor.generate_plan(tool_calls)

        assert "my-app" in plan.steps[0].preview_text

    def test_deny_in_plan(self, dry_run_executor):
        """DENY 操作应标记为 CRITICAL"""
        tool_calls = [
            {"name": "execute_command", "args": {"command": "rm -rf /"}, "id": "call_1"},
        ]

        plan = dry_run_executor.generate_plan(tool_calls)

        assert plan.steps[0].risk_assessment.decision == RiskDecision.DENY
        assert plan.steps[0].risk_assessment.risk_level == RiskLevel.CRITICAL

    def test_summary_generation(self, dry_run_executor):
        """摘要应正确生成"""
        tool_calls = [
            {"name": "get_logs", "args": {"container_name": "web"}, "id": "call_1"},
            {"name": "restart_docker_container", "args": {"container_name": "web"}, "id": "call_2"},
        ]

        plan = dry_run_executor.generate_plan(tool_calls)

        assert "2 个操作" in plan.summary

    def test_rollback_hint(self, dry_run_executor):
        """回滚提示应正确生成"""
        tool_calls = [
            {"name": "restart_docker_container", "args": {"container_name": "web"}, "id": "call_1"},
        ]

        plan = dry_run_executor.generate_plan(tool_calls)

        assert plan.rollback_hint is not None

    def test_no_rollback_hint_for_irreversible(self, dry_run_executor):
        """不可逆操作应有警告"""
        tool_calls = [
            {"name": "execute_command", "args": {"command": "ls -la"}, "id": "call_1"},
        ]

        plan = dry_run_executor.generate_plan(tool_calls)

        # execute_command 不可回滚
        assert "不可逆" in plan.rollback_hint or "不可" in plan.rollback_hint

    def test_empty_tool_calls(self, dry_run_executor):
        """空工具调用应生成空计划"""
        tool_calls = []

        plan = dry_run_executor.generate_plan(tool_calls)

        assert len(plan.steps) == 0
        assert plan.total_risk == RiskLevel.READONLY
