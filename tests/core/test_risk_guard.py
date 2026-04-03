"""
RiskGuard 单元测试
"""

import pytest
from src.core.risk_guard import RiskGuard, RiskLevel, RiskDecision
from src.core.policy_store import PolicyStore


@pytest.fixture
def risk_guard():
    return RiskGuard(PolicyStore())


class TestRiskGuardDenyRules:
    """DENY 规则测试"""

    def test_deny_rm_rf_root(self, risk_guard):
        """rm -rf / 应该被拒绝"""
        assessment = risk_guard.assess("execute_command", {"command": "rm -rf /"})
        assert assessment.decision == RiskDecision.DENY
        assert assessment.risk_level == RiskLevel.CRITICAL

    def test_deny_rm_rf_wildcard(self, risk_guard):
        """rm -rf /* 应该被拒绝"""
        assessment = risk_guard.assess("execute_command", {"command": "rm -rf /*"})
        assert assessment.decision == RiskDecision.DENY

    def test_deny_mkfs(self, risk_guard):
        """mkfs 应该被拒绝"""
        assessment = risk_guard.assess("execute_command", {"command": "mkfs.ext4 /dev/sda1"})
        assert assessment.decision == RiskDecision.DENY

    def test_deny_drop_database(self, risk_guard):
        """DROP DATABASE 应该被拒绝"""
        assessment = risk_guard.assess("execute_command", {"command": "DROP DATABASE prod;"})
        assert assessment.decision == RiskDecision.DENY

    def test_deny_chmod_777(self, risk_guard):
        """chmod -R 777 应该被拒绝"""
        assessment = risk_guard.assess("execute_command", {"command": "chmod -R 777 /var/www"})
        assert assessment.decision == RiskDecision.DENY


class TestRiskGuardConfirmRules:
    """CONFIRM 规则测试"""

    def test_confirm_restart_container(self, risk_guard):
        """重启容器需要确认"""
        assessment = risk_guard.assess("restart_docker_container", {"container_name": "web"})
        assert assessment.decision == RiskDecision.CONFIRM
        assert assessment.risk_level in [RiskLevel.MEDIUM, RiskLevel.HIGH]

    def test_confirm_stop_container(self, risk_guard):
        """停止容器需要确认"""
        assessment = risk_guard.assess("stop_docker_container", {"container_name": "web"})
        assert assessment.decision == RiskDecision.CONFIRM

    def test_confirm_deploy_service(self, risk_guard):
        """部署服务需要确认"""
        assessment = risk_guard.assess("deploy_service", {"project_name": "web-app"})
        assert assessment.decision == RiskDecision.CONFIRM

    def test_confirm_rollback(self, risk_guard):
        """回滚需要确认"""
        assessment = risk_guard.assess("rollback_deploy", {"project_name": "web-app"})
        assert assessment.decision == RiskDecision.CONFIRM

    def test_confirm_execute_command(self, risk_guard):
        """执行命令需要确认"""
        assessment = risk_guard.assess("execute_command", {"command": "ls -la"})
        assert assessment.decision == RiskDecision.CONFIRM


class TestRiskGuardAllowRules:
    """ALLOW 规则测试"""

    def test_allow_get_logs(self, risk_guard):
        """获取日志直接执行"""
        assessment = risk_guard.assess("get_logs", {"container_name": "web"})
        assert assessment.decision == RiskDecision.ALLOW
        assert assessment.risk_level == RiskLevel.LOW

    def test_allow_list_containers(self, risk_guard):
        """列出容器直接执行"""
        assessment = risk_guard.assess("list_docker_containers", {})
        assert assessment.decision == RiskDecision.ALLOW

    def test_allow_check_container(self, risk_guard):
        """检查容器直接执行"""
        assessment = risk_guard.assess("check_container", {"container_name": "web"})
        assert assessment.decision == RiskDecision.ALLOW

    def test_allow_diagnose(self, risk_guard):
        """诊断操作直接执行"""
        assessment = risk_guard.assess("diagnose", {"service_name": "web"})
        assert assessment.decision == RiskDecision.ALLOW

    def test_allow_search_kb(self, risk_guard):
        """搜索知识库直接执行"""
        assessment = risk_guard.assess("search_kb", {"query": "deploy"})
        assert assessment.decision == RiskDecision.ALLOW

    def test_allow_git_status(self, risk_guard):
        """git 状态直接执行"""
        assessment = risk_guard.assess("git_status", {})
        assert assessment.decision == RiskDecision.ALLOW


class TestRiskGuardUnknownTool:
    """未知工具测试"""

    def test_unknown_tool_defaults_to_confirm(self, risk_guard):
        """未知工具默认需要确认"""
        assessment = risk_guard.assess("some_unknown_tool", {})
        # 未匹配任何规则的默认行为是 CONFIRM（安全优先）
        assert assessment.decision == RiskDecision.CONFIRM


class TestRiskGuardHighRiskDetection:
    """高风险检测测试"""

    def test_production_keyword_elevates_risk(self, risk_guard):
        """生产环境关键词提升风险等级"""
        assessment = risk_guard.assess(
            "deploy_service",
            {"project_name": "prod-web-app"}
        )
        assert assessment.decision == RiskDecision.CONFIRM
        # 包含 prod 关键词应该提升为 HIGH
        assert assessment.risk_level == RiskLevel.HIGH
