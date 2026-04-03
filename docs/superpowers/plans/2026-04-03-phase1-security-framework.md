# Phase 1 安全框架实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Pulao 添加安全执行框架，实现危险操作拦截、人工确认、执行预览和审计日志。

**Architecture:** 在 LangGraph 状态机中插入安全节点（route → preview → hitl → tools → audit），通过 RiskGuard 评估每个工具调用的风险等级，根据风险等级决定直接执行、需要确认或拒绝。

**Tech Stack:** Python 3.10+, LangGraph, Rich (终端交互), dataclasses

---

## 文件结构

```
src/
├── core/
│   ├── risk_guard.py      # 风险评估引擎 [新建]
│   ├── policy_store.py    # 规则存储 [新建]
│   ├── hitl.py            # 人工确认交互 [新建]
│   ├── dry_run.py         # 执行计划生成 [新建]
│   └── audit.py           # 审计日志 [新建]
└── agent/
    └── graph.py           # 状态机改造 [修改]

tests/
└── core/
    ├── test_risk_guard.py # [新建]
    ├── test_dry_run.py    # [新建]
    └── test_audit.py      # [新建]
```

---

## Task 1: 风险等级与决策枚举

**Files:**
- Create: `src/core/risk_guard.py`

- [ ] **Step 1: 创建风险等级枚举**

```python
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
```

- [ ] **Step 2: 创建风险评估结果数据类**

```python
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
```

- [ ] **Step 3: 提交**

```bash
git add src/core/risk_guard.py
git commit -m "feat(core): add RiskLevel and RiskDecision enums"
```

---

## Task 2: 规则存储 (PolicyStore)

**Files:**
- Create: `src/core/policy_store.py`

- [ ] **Step 1: 创建 PolicyStore 类**

```python
"""
规则存储模块

管理风险评估规则，支持内置规则和用户自定义规则的合并。
"""

from typing import Dict, List
from pathlib import Path
import yaml


# 内置规则
BUILTIN_RULES = {
    "deny": [
        {"pattern": "rm -rf /", "reason": "禁止删除根目录"},
        {"pattern": "rm -rf /*", "reason": "禁止删除根目录"},
        {"pattern": "mkfs", "reason": "禁止格式化磁盘"},
        {"pattern": "dd if=", "reason": "禁止裸设备写入"},
        {"pattern": ":(){ :|:& };:", "reason": "禁止 Fork 炸弹"},
        {"pattern": "chmod -R 777", "reason": "禁止全开放权限"},
        {"pattern": "DROP DATABASE", "reason": "禁止删除数据库"},
        {"pattern": "DROP TABLE", "reason": "禁止删除表"},
    ],
    "confirm": [
        {"pattern": "restart_*", "reason": "重启服务会导致短暂不可用"},
        {"pattern": "stop_*", "reason": "停止服务会影响可用性"},
        {"pattern": "deploy_*", "reason": "部署会改变服务状态"},
        {"pattern": "rollback_*", "reason": "回滚操作影响较大"},
        {"pattern": "execute_command", "reason": "Shell 命令需要确认"},
        {"pattern": "push_changes", "reason": "推送变更到远程仓库"},
    ],
    "allow": [
        {"pattern": "get_*", "reason": "只读操作"},
        {"pattern": "list_*", "reason": "只读操作"},
        {"pattern": "check_*", "reason": "只读操作"},
        {"pattern": "search_*", "reason": "只读操作"},
        {"pattern": "query_*", "reason": "只读操作"},
        {"pattern": "diagnose", "reason": "诊断操作"},
        {"pattern": "system_status", "reason": "只读操作"},
        {"pattern": "kb_stats", "reason": "只读操作"},
        {"pattern": "git_status", "reason": "只读操作"},
        {"pattern": "gitops_status", "reason": "只读操作"},
        {"pattern": "view_changelog", "reason": "只读操作"},
    ],
}


class PolicyStore:
    """
    规则存储
    
    管理风险评估规则，支持：
    - 内置规则
    - 用户自定义规则（覆盖内置规则）
    """
    
    POLICY_FILE = Path.home() / ".pulao" / "policies.yaml"
    
    def __init__(self):
        self._user_rules: Dict[str, List[dict]] = {}
        self._load_user_rules()
    
    def _load_user_rules(self):
        """加载用户自定义规则"""
        if self.POLICY_FILE.exists():
            try:
                with open(self.POLICY_FILE, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    self._user_rules = data.get("rules", {})
            except Exception:
                self._user_rules = {}
    
    def get_rules(self) -> Dict[str, List[dict]]:
        """
        获取合并后的规则
        
        合并顺序：用户规则覆盖内置规则的同名 pattern
        """
        merged = {
            "deny": list(BUILTIN_RULES.get("deny", [])),
            "confirm": list(BUILTIN_RULES.get("confirm", [])),
            "allow": list(BUILTIN_RULES.get("allow", [])),
        }
        
        # 用户规则覆盖
        for category, rules in self._user_rules.items():
            if category not in merged:
                merged[category] = []
            
            for rule in rules:
                # 移除同 pattern 的内置规则
                pattern = rule.get("pattern", "")
                merged[category] = [r for r in merged[category] if r.get("pattern") != pattern]
                # 添加用户规则
                merged[category].append(rule)
        
        return merged
```

- [ ] **Step 2: 提交**

```bash
git add src/core/policy_store.py
git commit -m "feat(core): add PolicyStore for rule management"
```

---

## Task 3: 风险评估引擎 (RiskGuard)

**Files:**
- Modify: `src/core/risk_guard.py`

- [ ] **Step 1: 编写 RiskGuard 测试**

```python
# tests/core/test_risk_guard.py

import pytest
from src.core.risk_guard import RiskGuard, RiskLevel, RiskDecision
from src.core.policy_store import PolicyStore


@pytest.fixture
def risk_guard():
    return RiskGuard(PolicyStore())


class TestRiskGuard:
    
    def test_deny_rm_rf_root(self, risk_guard):
        """rm -rf / 应该被拒绝"""
        assessment = risk_guard.assess("execute_command", {"command": "rm -rf /"})
        assert assessment.decision == RiskDecision.DENY
        assert assessment.risk_level == RiskLevel.CRITICAL
    
    def test_deny_drop_database(self, risk_guard):
        """DROP DATABASE 应该被拒绝"""
        assessment = risk_guard.assess("execute_command", {"command": "DROP DATABASE prod;"})
        assert assessment.decision == RiskDecision.DENY
    
    def test_confirm_restart_container(self, risk_guard):
        """重启容器需要确认"""
        assessment = risk_guard.assess("restart_docker_container", {"container_name": "web"})
        assert assessment.decision == RiskDecision.CONFIRM
        assert assessment.risk_level in [RiskLevel.MEDIUM, RiskLevel.HIGH]
    
    def test_confirm_deploy_service(self, risk_guard):
        """部署服务需要确认"""
        assessment = risk_guard.assess("deploy_service", {"project_name": "web-app"})
        assert assessment.decision == RiskDecision.CONFIRM
    
    def test_confirm_execute_command(self, risk_guard):
        """执行命令需要确认"""
        assessment = risk_guard.assess("execute_command", {"command": "ls -la"})
        assert assessment.decision == RiskDecision.CONFIRM
    
    def test_allow_get_logs(self, risk_guard):
        """获取日志直接执行"""
        assessment = risk_guard.assess("get_logs", {"container_name": "web"})
        assert assessment.decision == RiskDecision.ALLOW
        assert assessment.risk_level == RiskLevel.LOW
    
    def test_allow_list_containers(self, risk_guard):
        """列出容器直接执行"""
        assessment = risk_guard.assess("list_docker_containers", {})
        assert assessment.decision == RiskDecision.ALLOW
    
    def test_allow_diagnose(self, risk_guard):
        """诊断操作直接执行"""
        assessment = risk_guard.assess("diagnose", {"service_name": "web"})
        assert assessment.decision == RiskDecision.ALLOW
    
    def test_unknown_tool_defaults_to_confirm(self, risk_guard):
        """未知工具默认需要确认"""
        assessment = risk_guard.assess("some_unknown_tool", {})
        # 未匹配任何规则的默认行为
        assert assessment.decision in [RiskDecision.ALLOW, RiskDecision.CONFIRM]
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/core/test_risk_guard.py -v
# Expected: FAIL (RiskGuard not implemented)
```

- [ ] **Step 3: 实现 RiskGuard 类**

添加到 `src/core/risk_guard.py`:

```python
import fnmatch
from .policy_store import PolicyStore


class RiskGuard:
    """
    风险评估引擎
    
    评估每个工具调用的风险等级，决定执行策略。
    
    优先级: DENY > CONFIRM > ALLOW
    """
    
    def __init__(self, policy_store: PolicyStore):
        self.policy_store = policy_store
    
    def assess(self, tool_name: str, arguments: dict) -> RiskAssessment:
        """
        评估工具调用风险
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
                resources.append(arguments[key])
        return resources
    
    def _check_rollback_possible(self, tool_name: str) -> bool:
        """检查是否可回滚"""
        non_rollback_tools = {"execute_command", "push_changes"}
        return tool_name not in non_rollback_tools
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/core/test_risk_guard.py -v
# Expected: PASS
```

- [ ] **Step 5: 提交**

```bash
git add src/core/risk_guard.py tests/core/test_risk_guard.py
git commit -m "feat(core): implement RiskGuard with pattern matching"
```

---

## Task 4: 审计日志 (AuditLogger)

**Files:**
- Create: `src/core/audit.py`
- Create: `tests/core/test_audit.py`

- [ ] **Step 1: 编写审计日志测试**

```python
# tests/core/test_audit.py

import pytest
from pathlib import Path
import json
from src.core.audit import AuditLogger


class TestAuditLogger:
    
    def test_log_creates_event(self, tmp_path, monkeypatch):
        """写入审计日志应创建事件"""
        # 临时目录
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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/core/test_audit.py -v
# Expected: FAIL
```

- [ ] **Step 3: 实现 AuditLogger**

```python
# src/core/audit.py

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
        """敏感参数脱敏"""
        SENSITIVE_KEYS = {"api_key", "password", "secret", "token", "key", "credential"}
        
        result = {}
        for k, v in args.items():
            if any(s in k.lower() for s in SENSITIVE_KEYS):
                result[k] = "***REDACTED***"
            elif isinstance(v, dict):
                result[k] = AuditLogger._sanitize(v)
            else:
                result[k] = v
        return result
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/core/test_audit.py -v
# Expected: PASS
```

- [ ] **Step 5: 提交**

```bash
git add src/core/audit.py tests/core/test_audit.py
git commit -m "feat(core): add AuditLogger with sensitive data sanitization"
```

---

## Task 5: 执行计划生成 (DryRunExecutor)

**Files:**
- Create: `src/core/dry_run.py`
- Create: `tests/core/test_dry_run.py`

- [ ] **Step 1: 编写执行计划测试**

```python
# tests/core/test_dry_run.py

import pytest
from src.core.dry_run import DryRunExecutor, ExecutionPlan, ExecutionStep
from src.core.risk_guard import RiskGuard, RiskLevel, RiskDecision
from src.core.policy_store import PolicyStore


@pytest.fixture
def dry_run_executor():
    return DryRunExecutor(RiskGuard(PolicyStore()))


class TestDryRunExecutor:
    
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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/core/test_dry_run.py -v
# Expected: FAIL
```

- [ ] **Step 3: 实现 DryRunExecutor**

```python
# src/core/dry_run.py

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
    """Dry-Run 执行器"""
    
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
    }
    
    def __init__(self, risk_guard: RiskGuard):
        self.risk_guard = risk_guard
    
    def generate_plan(self, tool_calls: List[dict]) -> ExecutionPlan:
        """生成执行计划"""
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
        rollbackable = [s for s in steps if s.risk_assessment.rollback_possible]
        
        if len(steps) == 0:
            return None
        
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
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/core/test_dry_run.py -v
# Expected: PASS
```

- [ ] **Step 5: 提交**

```bash
git add src/core/dry_run.py tests/core/test_dry_run.py
git commit -m "feat(core): add DryRunExecutor for execution plan generation"
```

---

## Task 6: 人工确认交互 (HITLController)

**Files:**
- Create: `src/core/hitl.py`

- [ ] **Step 1: 实现 HITLController**

```python
# src/core/hitl.py

"""
人工确认交互模块

提供终端交互式确认界面。
"""

from rich.console import Console
from typing import Optional

from .dry_run import ExecutionPlan
from .risk_guard import RiskLevel, RiskDecision


console = Console()


class HITLController:
    """人工确认控制器"""
    
    # 风险等级图标和颜色
    RISK_ICONS = {
        RiskLevel.READONLY: ("📖", "green"),
        RiskLevel.LOW: ("🟢", "green"),
        RiskLevel.MEDIUM: ("🟡", "yellow"),
        RiskLevel.HIGH: ("🔴", "red"),
        RiskLevel.CRITICAL: ("⛔", "red bold"),
    }
    
    @classmethod
    def confirm(cls, plan: ExecutionPlan) -> bool:
        """
        展示执行计划并等待用户确认
        
        Returns:
            True: 用户确认执行
            False: 用户拒绝
        """
        console.print(f"\n[bold]📋 执行计划预览[/bold]")
        console.print(f"[dim]计划 ID: {plan.plan_id}[/dim]")
        
        # 整体风险
        icon, color = cls.RISK_ICONS.get(plan.total_risk, ("⚪", "white"))
        console.print(f"整体风险: [{color}]{icon} {plan.total_risk.value.upper()}[/{color}]")
        console.print(f"摘要: {plan.summary}\n")
        
        # 检查是否有 DENY 的步骤
        denied_steps = [s for s in plan.steps if s.risk_assessment.decision == RiskDecision.DENY]
        if denied_steps:
            console.print("[red bold]⛔ 以下操作被拒绝:[/red bold]")
            for step in denied_steps:
                console.print(f"  ⛔ {step.preview_text}")
                console.print(f"     [dim]{step.risk_assessment.reason}[/dim]")
            console.print("\n[yellow]请修改操作后重试[/yellow]")
            return False
        
        # 步骤列表
        console.print("[bold]操作步骤:[/bold]")
        for step in plan.steps:
            icon, color = cls.RISK_ICONS.get(step.risk_assessment.risk_level, ("⚪", "white"))
            console.print(f"  {icon} [{color}]{step.preview_text}[/{color}]")
            
            # 高风险显示原因
            if step.risk_assessment.risk_level in [RiskLevel.HIGH]:
                console.print(f"     [dim]⚠️  {step.risk_assessment.reason}[/dim]")
        
        # 回滚提示
        if plan.rollback_hint:
            console.print(f"\n[dim]{plan.rollback_hint}[/dim]")
        
        # 等待确认
        console.print(f"\n[bold]是否执行以上 {len(plan.steps)} 个操作?[/bold] [y/N]: ", end="")
        
        try:
            choice = input().strip().lower()
            return choice in ('y', 'yes')
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]已取消[/yellow]")
            return False
    
    @classmethod
    def confirm_single(cls, tool_name: str, reason: str) -> bool:
        """
        单操作确认（简化版）
        """
        console.print(f"\n[yellow]⚠️  操作需要确认[/yellow]")
        console.print(f"操作: {tool_name}")
        console.print(f"原因: {reason}")
        console.print(f"\n是否执行? [y/N]: ", end="")
        
        try:
            choice = input().strip().lower()
            return choice in ('y', 'yes')
        except (EOFError, KeyboardInterrupt):
            return False
```

- [ ] **Step 2: 提交**

```bash
git add src/core/hitl.py
git commit -m "feat(core): add HITLController for interactive confirmation"
```

---

## Task 7: 更新 \_\_init\_\_.py 导出

**Files:**
- Modify: `src/core/__init__.py`

- [ ] **Step 1: 添加新模块导出**

```python
# src/core/__init__.py

"""
核心模块

提供配置、日志、国际化、安全框架等核心功能。
"""

from .config import ConfigManager, load_config, get_config_dir
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
    "ConfigManager",
    "load_config",
    "get_config_dir",
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
```

- [ ] **Step 2: 验证导入**

```bash
python -c "from src.core import RiskGuard, DryRunExecutor, HITLController, AuditLogger; print('OK')"
# Expected: OK
```

- [ ] **Step 3: 提交**

```bash
git add src/core/__init__.py
git commit -m "feat(core): export security framework modules"
```

---

## Task 8: 改造 LangGraph 状态机

**Files:**
- Modify: `src/agent/graph.py`

- [ ] **Step 1: 更新状态定义**

```python
# src/agent/graph.py

from typing import Annotated, TypedDict, List, Dict, Any, Optional
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.tools import StructuredTool
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from src.tools.registry import registry

# 导入安全框架
from src.core.risk_guard import RiskGuard, RiskDecision, RiskLevel
from src.core.policy_store import PolicyStore
from src.core.dry_run import DryRunExecutor, ExecutionPlan
from src.core.hitl import HITLController
from src.core.audit import AuditLogger
import uuid


class AgentState(TypedDict):
    """Agent 状态"""
    messages: Annotated[List[BaseMessage], add_messages]
    
    # 安全框架新增
    trace_id: str
    execution_plan: Optional[ExecutionPlan]
    confirmed: bool
    denied_reason: Optional[str]
    audit_events: List[str]
    session_id: str
```

- [ ] **Step 2: 添加全局安全组件**

```python
# 初始化安全组件
_risk_guard = RiskGuard(PolicyStore())
_dry_run_executor = DryRunExecutor(_risk_guard)


def _generate_trace_id() -> str:
    """生成追踪 ID"""
    return f"trace_{uuid.uuid4().hex[:12]}"


def _generate_session_id() -> str:
    """生成会话 ID"""
    return f"sess_{uuid.uuid4().hex[:8]}"
```

- [ ] **Step 3: 添加路由节点**

```python
def route_node(state: AgentState) -> str:
    """
    路由决策
    
    根据风险评估决定执行路径:
    - end: 无工具调用
    - execute: 所有操作都是 ALLOW
    - preview: 有操作需要 CONFIRM
    - deny: 有操作被 DENY
    """
    last_message = state["messages"][-1]
    
    if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
        return "end"
    
    # 评估所有工具调用
    has_confirm = False
    
    for tc in last_message.tool_calls:
        assessment = _risk_guard.assess(tc["name"], tc.get("args", {}))
        
        if assessment.decision == RiskDecision.DENY:
            return "deny"
        
        if assessment.decision == RiskDecision.CONFIRM:
            has_confirm = True
    
    if has_confirm:
        return "preview"
    
    return "execute"
```

- [ ] **Step 4: 添加 preview 节点**

```python
def preview_node(state: AgentState) -> dict:
    """生成执行计划"""
    last_message = state["messages"][-1]
    tool_calls = [
        {"name": tc["name"], "args": tc.get("args", {}), "id": tc.get("id", "")}
        for tc in last_message.tool_calls
    ]
    
    plan = _dry_run_executor.generate_plan(tool_calls)
    
    return {
        "execution_plan": plan
    }
```

- [ ] **Step 5: 添加 hitl 节点**

```python
def hitl_node(state: AgentState) -> dict:
    """人工确认"""
    plan = state["execution_plan"]
    
    # 检查 DENY
    for step in plan.steps:
        if step.risk_assessment.decision == RiskDecision.DENY:
            return {
                "confirmed": False,
                "denied_reason": step.risk_assessment.reason
            }
    
    # 用户确认
    approved = HITLController.confirm(plan)
    
    return {
        "confirmed": approved,
        "denied_reason": None if approved else "用户取消"
    }
```

- [ ] **Step 6: 添加 deny 处理节点**

```python
def deny_node(state: AgentState) -> dict:
    """处理拒绝的操作"""
    from langchain_core.messages import AIMessage
    
    last_message = state["messages"][-1]
    denied_tools = []
    
    for tc in last_message.tool_calls:
        assessment = _risk_guard.assess(tc["name"], tc.get("args", {}))
        if assessment.decision == RiskDecision.DENY:
            denied_tools.append(f"{tc['name']}: {assessment.reason}")
    
    # 记录审计日志
    for tc in last_message.tool_calls:
        assessment = _risk_guard.assess(tc["name"], tc.get("args", {}))
        if assessment.decision == RiskDecision.DENY:
            AuditLogger.log(
                trace_id=state.get("trace_id", ""),
                session_id=state.get("session_id", ""),
                tool_name=tc["name"],
                arguments=tc.get("args", {}),
                risk_level=assessment.risk_level.value,
                decision="deny",
                confirm_state="skipped",
                result="denied",
                error_message=assessment.reason
            )
    
    # 返回拒绝消息
    denial_msg = f"以下操作被系统拒绝:\n" + "\n".join(f"- {t}" for t in denied_tools)
    denial_msg += "\n\n请修改你的请求或尝试其他方案。"
    
    return {
        "messages": [AIMessage(content=denial_msg)]
    }
```

- [ ] **Step 7: 添加 audit 节点**

```python
def audit_node(state: AgentState) -> dict:
    """审计日志"""
    event_ids = []
    
    # 获取最后一个工具调用的结果
    last_message = state["messages"][-1]
    
    # 从历史中找到对应的工具调用
    for i, msg in enumerate(reversed(state["messages"][:-1])):
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            for tc in msg.tool_calls:
                event_id = AuditLogger.log(
                    trace_id=state.get("trace_id", ""),
                    session_id=state.get("session_id", ""),
                    tool_name=tc["name"],
                    arguments=tc.get("args", {}),
                    risk_level="medium",  # 能执行到这里说明已经过确认
                    decision="confirm",
                    confirm_state="confirmed",
                    result="success"
                )
                event_ids.append(event_id)
            break
    
    return {
        "audit_events": state.get("audit_events", []) + event_ids
    }
```

- [ ] **Step 8: 更新 create_agent_app 函数**

```python
def create_agent_app(config: Dict[str, Any]):
    """创建 Agent 应用"""
    tools = create_langchain_tools()
    tool_node = ToolNode(tools)

    model = ChatOpenAI(
        api_key=config.get("api_key"),
        base_url=config.get("base_url"),
        model=config.get("model", "gpt-4o"),
        temperature=0,
    ).bind_tools(tools)

    def agent_chain(state: AgentState) -> dict:
        response = model.invoke(state["messages"])
        return {"messages": [response]}

    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("agent", agent_chain)
    workflow.add_node("preview", preview_node)
    workflow.add_node("hitl", hitl_node)
    workflow.add_node("tools", tool_node)
    workflow.add_node("audit", audit_node)
    workflow.add_node("deny", deny_node)

    # 设置入口
    workflow.add_edge(START, "agent")

    # agent 路由
    workflow.add_conditional_edges(
        "agent",
        route_node,
        {
            "end": END,
            "execute": "tools",
            "preview": "preview",
            "deny": "deny",
        }
    )

    # preview -> hitl
    workflow.add_edge("preview", "hitl")

    # hitl 路由
    workflow.add_conditional_edges(
        "hitl",
        lambda state: "execute" if state.get("confirmed") else "reject",
        {
            "execute": "tools",
            "reject": "agent"  # 用户拒绝，返回 agent 重新规划
        }
    )

    # deny -> agent (重新规划)
    workflow.add_edge("deny", "agent")

    # tools -> audit -> agent
    workflow.add_edge("tools", "audit")
    workflow.add_edge("audit", "agent")

    return workflow.compile()
```

- [ ] **Step 9: 更新 create_langchain_tools 函数**

```python
def create_langchain_tools() -> List[StructuredTool]:
    """创建 LangChain 工具列表"""
    tools = []
    for name, func in registry._tools.items():
        tool = StructuredTool.from_function(
            func=func,
            name=name,
            description=func.__doc__ or f"Tool {name}",
        )
        tools.append(tool)
    return tools
```

- [ ] **Step 10: 运行现有测试确保无回归**

```bash
pytest tests/ -v --ignore=tests/core/test_risk_guard.py --ignore=tests/core/test_dry_run.py --ignore=tests/core/test_audit.py
# Expected: PASS (无回归)
```

- [ ] **Step 11: 提交**

```bash
git add src/agent/graph.py
git commit -m "feat(agent): integrate security framework into LangGraph"
```

---

## Task 9: 更新 orchestrator 支持 trace_id

**Files:**
- Modify: `src/agent/orchestrator.py`

- [ ] **Step 1: 添加 trace_id 和 session_id 生成**

在 `process_deployment` 函数中：

```python
def process_deployment(instruction: str, config: dict):
    """
    处理用户部署指令的核心函数
    """
    # 获取 AI 会话实例
    session = get_session(config)

    # 生成追踪 ID
    trace_id = f"trace_{uuid.uuid4().hex[:12]}"
    session_id = f"sess_{uuid.uuid4().hex[:8]}"

    # 1. RAG 检索
    rag_context = _perform_rag_search(instruction)
    
    # 2. 模板检查
    template_context = _match_template(instruction)
    
    # 3. 组装最终指令
    final_instruction = instruction + template_context + rag_context
    session.add_user_message(final_instruction)
    
    # ... 省略中间代码 ...

    # ============ LangGraph Execution ============
    try:
        app = create_agent_app(config)
    except Exception as e:
        logger.critical(f"Failed to initialize AI Agent: {e}", exc_info=True)
        console.print(f"[bold red]Critical Error:[/bold red] Failed to initialize AI Agent.\n{e}")
        return

    try:
        lc_messages = convert_history_to_messages(session.history)
        
        # 初始化状态，包含 trace_id
        inputs = {
            "messages": lc_messages,
            "trace_id": trace_id,
            "session_id": session_id,
            "execution_plan": None,
            "confirmed": False,
            "denied_reason": None,
            "audit_events": []
        }
        result = app.invoke(inputs)
        
        # ... 省略后续处理 ...
```

- [ ] **Step 2: 添加 uuid 导入**

```python
import uuid
```

- [ ] **Step 3: 提交**

```bash
git add src/agent/orchestrator.py
git commit -m "feat(agent): add trace_id and session_id for audit tracking"
```

---

## Task 10: 集成测试

**Files:**
- Create: `tests/agent/test_security_flow.py`

- [ ] **Step 1: 编写集成测试**

```python
# tests/agent/test_security_flow.py

"""
安全框架集成测试

测试完整的安全执行流程。
"""

import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage, HumanMessage

from src.core.risk_guard import RiskGuard, RiskDecision
from src.core.policy_store import PolicyStore
from src.core.dry_run import DryRunExecutor
from src.core.hitl import HITLController


class TestSecurityFlow:
    
    @pytest.fixture
    def risk_guard(self):
        return RiskGuard(PolicyStore())
    
    @pytest.fixture
    def dry_run_executor(self, risk_guard):
        return DryRunExecutor(risk_guard)
    
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
        from src.core.risk_guard import RiskLevel
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
```

- [ ] **Step 2: 运行集成测试**

```bash
pytest tests/agent/test_security_flow.py -v
# Expected: PASS
```

- [ ] **Step 3: 提交**

```bash
git add tests/agent/test_security_flow.py
git commit -m "test(agent): add security flow integration tests"
```

---

## Task 11: 运行完整测试套件

- [ ] **Step 1: 运行所有测试**

```bash
pytest tests/ -v --cov=src --cov-report=term-missing
# Expected: All PASS, coverage > 80%
```

- [ ] **Step 2: 修复任何失败的测试**

如有失败，逐一修复。

- [ ] **Step 3: 最终提交**

```bash
git add -A
git commit -m "feat(phase1): complete security framework implementation

- Add RiskGuard for risk assessment
- Add PolicyStore for rule management
- Add DryRunExecutor for execution plan generation
- Add HITLController for interactive confirmation
- Add AuditLogger for audit trail
- Integrate security framework into LangGraph

Closes #issue-number"
```

---

## 验收清单

- [ ] `rm -rf /` 等 DENY 规则操作被拦截
- [ ] `restart_*` 等 CONFIRM 规则操作弹出确认
- [ ] `get_*` 等 ALLOW 规则操作直接执行
- [ ] 审计日志正确记录到 `~/.pulao/audit.log`
- [ ] 用户配置可覆盖内置规则
- [ ] 单元测试覆盖率 > 80%
- [ ] 集成测试通过

---

*计划版本: 1.0*
*创建时间: 2026-04-03*
