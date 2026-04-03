"""
安全框架集成测试

测试完整的安全执行流程。
"""

import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage, HumanMessage

from src.core.risk_guard import RiskGuard, RiskDecision, RiskLevel
from src.core.policy_store import PolicyStore
from src.core.dry_run import DryRunExecutor
from src.core.hitl import HITLController


@pytest.fixture
def risk_guard():
    return RiskGuard(PolicyStore())


@pytest.fixture
def dry_run_executor(risk_guard):
    return DryRunExecutor(risk_guard)


class TestSecurityFlow:
    """安全流程集成测试"""

    def test_allow_flow_direct_execution(self, risk_guard):
        """ALLOW 操作应直接执行"""
        assessment = risk_guard.assess("get_logs", {"container_name": "web"})
        assert assessment.decision == RiskDecision.ALLOW

    def test_confirm_flow_needs_preview(self, risk_guard, dry_run_executor):
        """CONFIRM 操作应生成预览"""
        tool_calls = [
            {"name": "restart_docker_container", "args": {"container_name": "web"}, "id": "call_1"}
        ]

        plan = dry_run_executor.generate_plan(tool_calls)

        assert len(plan.steps) == 1
        assert plan.steps[0].risk_assessment.decision == RiskDecision.CONFIRM

    def test_deny_flow_rejected(self, risk_guard):
        """DENY 操作应被拒绝"""
        assessment = risk_guard.assess("execute_command", {"command": "rm -rf /"})
        assert assessment.decision == RiskDecision.DENY

    def test_multi_step_plan_risk_aggregation(self, dry_run_executor):
        """多步计划应正确聚合风险"""
        tool_calls = [
            {"name": "get_logs", "args": {"container_name": "web"}, "id": "call_1"},
            {"name": "restart_docker_container", "args": {"container_name": "web"}, "id": "call_2"},
            {"name": "deploy_service", "args": {"project_name": "app"}, "id": "call_3"},
        ]

        plan = dry_run_executor.generate_plan(tool_calls)

        # 所有操作中风险最高的
        assert plan.total_risk == RiskLevel.MEDIUM

    @patch('builtins.input', return_value='y')
    def test_hitl_confirm_accepted(self, mock_input, dry_run_executor):
        """用户确认后应返回 True"""
        tool_calls = [
            {"name": "restart_docker_container", "args": {"container_name": "web"}, "id": "call_1"}
        ]

        plan = dry_run_executor.generate_plan(tool_calls)
        result = HITLController.confirm(plan)

        assert result is True

    @patch('builtins.input', return_value='n')
    def test_hitl_confirm_rejected(self, mock_input, dry_run_executor):
        """用户拒绝后应返回 False"""
        tool_calls = [
            {"name": "restart_docker_container", "args": {"container_name": "web"}, "id": "call_1"}
        ]

        plan = dry_run_executor.generate_plan(tool_calls)
        result = HITLController.confirm(plan)

        assert result is False

    def test_deny_step_blocks_execution(self, dry_run_executor):
        """DENY 步骤应阻止执行"""
        tool_calls = [
            {"name": "execute_command", "args": {"command": "rm -rf /"}, "id": "call_1"},
        ]

        plan = dry_run_executor.generate_plan(tool_calls)

        assert plan.steps[0].risk_assessment.decision == RiskDecision.DENY
        assert plan.steps[0].risk_assessment.risk_level == RiskLevel.CRITICAL

    def test_mixed_operations_plan(self, dry_run_executor):
        """混合操作应正确分类"""
        tool_calls = [
            {"name": "get_logs", "args": {"container_name": "web"}, "id": "call_1"},  # ALLOW
            {"name": "restart_docker_container", "args": {"container_name": "web"}, "id": "call_2"},  # CONFIRM
        ]

        plan = dry_run_executor.generate_plan(tool_calls)

        assert plan.steps[0].risk_assessment.decision == RiskDecision.ALLOW
        assert plan.steps[1].risk_assessment.decision == RiskDecision.CONFIRM
        assert plan.total_risk == RiskLevel.MEDIUM  # 取最高

    def test_production_context_elevates_risk(self, risk_guard):
        """生产环境上下文应提升风险等级"""
        # 普通部署
        normal = risk_guard.assess("deploy_service", {"project_name": "dev-app"})
        assert normal.risk_level == RiskLevel.MEDIUM

        # 生产部署
        prod = risk_guard.assess("deploy_service", {"project_name": "prod-app"})
        assert prod.risk_level == RiskLevel.HIGH


class TestRiskGuardEdgeCases:
    """RiskGuard 边界情况测试"""

    def test_empty_arguments(self, risk_guard):
        """空参数应正常处理"""
        assessment = risk_guard.assess("list_docker_containers", {})
        assert assessment.decision == RiskDecision.ALLOW

    def test_unknown_tool_defaults_to_confirm(self, risk_guard):
        """未知工具默认需要确认"""
        assessment = risk_guard.assess("unknown_tool_xyz", {})
        assert assessment.decision == RiskDecision.CONFIRM

    def test_partial_pattern_match(self, risk_guard):
        """部分模式匹配应正确"""
        # restart_docker_container 匹配 restart_*
        assessment = risk_guard.assess("restart_docker_container", {"container_name": "web"})
        assert assessment.decision == RiskDecision.CONFIRM

    def test_case_sensitivity_in_deny(self, risk_guard):
        """DENY 规则应大小写敏感"""
        # DROP DATABASE 应被拒绝
        assessment = risk_guard.assess("execute_command", {"command": "DROP DATABASE test;"})
        assert assessment.decision == RiskDecision.DENY


class TestDryRunExecutorEdgeCases:
    """DryRunExecutor 边界情况测试"""

    def test_empty_tool_calls(self, dry_run_executor):
        """空工具调用应生成空计划"""
        plan = dry_run_executor.generate_plan([])

        assert len(plan.steps) == 0
        assert plan.total_risk == RiskLevel.READONLY

    def test_preview_text_truncation(self, dry_run_executor):
        """预览文本应处理长命令"""
        long_command = "ls " + " ".join(["file" + str(i) for i in range(100)])
        tool_calls = [
            {"name": "execute_command", "args": {"command": long_command}, "id": "call_1"}
        ]

        plan = dry_run_executor.generate_plan(tool_calls)

        # 应该生成预览而不是崩溃
        assert plan.steps[0].preview_text is not None
