"""
审计日志模块

记录所有工具调用的审计事件，存储为 JSON Lines 格式。
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any
import uuid


class AuditLogger:
    """
    审计日志管理器

    存储格式: JSON Lines (~/.pulao/audit.log)
    每行一条记录，便于追加和解析
    """

    AUDIT_FILE = Path.home() / ".pulao" / "audit.log"

    @classmethod
    def log(
        cls,
        trace_id: str,
        session_id: str,
        tool_name: str,
        arguments: dict,
        risk_level: str,
        decision: str,
        confirm_state: str,
        result: str,
        error_message: Optional[str] = None,
        plan_id: Optional[str] = None
    ) -> str:
        """
        写入审计日志

        Args:
            trace_id: 全链路追踪 ID
            session_id: 会话 ID
            tool_name: 工具名称
            arguments: 工具参数
            risk_level: 风险等级
            decision: 风险决策
            confirm_state: 确认状态
            result: 执行结果
            error_message: 错误信息（可选）
            plan_id: 执行计划 ID（可选）

        Returns:
            event_id: 事件唯一标识
        """
        event_id = f"evt_{uuid.uuid4().hex[:12]}"

        event = {
            "event_id": event_id,
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "tool_name": tool_name,
            "arguments": cls._sanitize(arguments),
            "risk_level": risk_level,
            "decision": decision,
            "confirm_state": confirm_state,
            "result": result,
            "error_message": error_message,
            "plan_id": plan_id
        }

        # 确保目录存在
        cls.AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)

        # 追加写入
        with open(cls.AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

        return event_id

    @staticmethod
    def _sanitize(args: dict) -> dict:
        """
        敏感参数脱敏

        规则：
        - api_key, password, secret, token, key, credential → "***REDACTED***"
        - 其他字段保留
        - 支持嵌套字典
        """
        SENSITIVE_KEYS = {"api_key", "password", "secret", "token", "key", "credential"}

        result = {}
        for k, v in args.items():
            if any(sensitive in k.lower() for sensitive in SENSITIVE_KEYS):
                result[k] = "***REDACTED***"
            elif isinstance(v, dict):
                result[k] = AuditLogger._sanitize(v)
            else:
                result[k] = v
        return result
