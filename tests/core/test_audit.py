"""
AuditLogger 单元测试
"""

import pytest
from pathlib import Path
import json
from src.core.audit import AuditLogger


class TestAuditLogger:
    """审计日志测试"""

    def test_log_creates_event(self, tmp_path, monkeypatch):
        """写入审计日志应创建事件"""
        monkeypatch.setattr(AuditLogger, "AUDIT_FILE", tmp_path / "audit.log")

        event_id = AuditLogger.log(
            trace_id="trace_123",
            session_id="sess_456",
            tool_name="deploy_service",
            arguments={"project_name": "web-app"},
            risk_level="medium",
            decision="confirm",
            confirm_state="confirmed",
            result="success"
        )

        assert event_id.startswith("evt_")

        # 验证文件写入
        content = (tmp_path / "audit.log").read_text()
        event = json.loads(content.strip())
        assert event["tool_name"] == "deploy_service"
        assert event["result"] == "success"

    def test_sanitize_sensitive_data(self, tmp_path, monkeypatch):
        """敏感参数应被脱敏"""
        monkeypatch.setattr(AuditLogger, "AUDIT_FILE", tmp_path / "audit.log")

        AuditLogger.log(
            trace_id="trace_123",
            session_id="sess_456",
            tool_name="test_tool",
            arguments={"api_key": "secret123", "password": "pass456", "normal": "value"},
            risk_level="low",
            decision="allow",
            confirm_state="skipped",
            result="success"
        )

        content = (tmp_path / "audit.log").read_text()
        event = json.loads(content.strip())

        assert event["arguments"]["api_key"] == "***REDACTED***"
        assert event["arguments"]["password"] == "***REDACTED***"
        assert event["arguments"]["normal"] == "value"

    def test_append_multiple_events(self, tmp_path, monkeypatch):
        """多次写入应追加到同一文件"""
        monkeypatch.setattr(AuditLogger, "AUDIT_FILE", tmp_path / "audit.log")

        AuditLogger.log("t1", "s1", "tool1", {}, "low", "allow", "skipped", "success")
        AuditLogger.log("t2", "s2", "tool2", {}, "medium", "confirm", "confirmed", "success")

        lines = (tmp_path / "audit.log").read_text().strip().split("\n")
        assert len(lines) == 2

    def test_event_has_required_fields(self, tmp_path, monkeypatch):
        """事件应包含所有必需字段"""
        monkeypatch.setattr(AuditLogger, "AUDIT_FILE", tmp_path / "audit.log")

        AuditLogger.log(
            trace_id="trace_123",
            session_id="sess_456",
            tool_name="test_tool",
            arguments={"arg1": "value1"},
            risk_level="medium",
            decision="confirm",
            confirm_state="confirmed",
            result="success",
            error_message=None,
            plan_id="plan_abc"
        )

        content = (tmp_path / "audit.log").read_text()
        event = json.loads(content.strip())

        required_fields = [
            "event_id", "trace_id", "timestamp", "session_id",
            "tool_name", "arguments", "risk_level", "decision",
            "confirm_state", "result"
        ]

        for field in required_fields:
            assert field in event, f"Missing field: {field}"

    def test_sanitize_nested_dict(self, tmp_path, monkeypatch):
        """嵌套字典中的敏感参数应被脱敏"""
        monkeypatch.setattr(AuditLogger, "AUDIT_FILE", tmp_path / "audit.log")

        AuditLogger.log(
            trace_id="trace_123",
            session_id="sess_456",
            tool_name="test_tool",
            arguments={
                "config": {
                    "api_key": "nested_secret",
                    "normal": "value"
                }
            },
            risk_level="low",
            decision="allow",
            confirm_state="skipped",
            result="success"
        )

        content = (tmp_path / "audit.log").read_text()
        event = json.loads(content.strip())

        assert event["arguments"]["config"]["api_key"] == "***REDACTED***"
        assert event["arguments"]["config"]["normal"] == "value"
