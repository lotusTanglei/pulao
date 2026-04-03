# Phase 1 安全框架设计文档

> 版本: 1.0
> 日期: 2026-04-03
> 状态: 待审核

---

## 一、概述

### 1.1 背景

Pulao 当前是一个"裸奔"的 ReAct Agent：AI 决定调用工具后直接执行，没有任何安全拦截机制。这在生产环境中是不可接受的。

### 1.2 目标

为 Pulao 添加安全执行框架，实现：

1. **危险操作拦截** - 高危操作直接拒绝
2. **人工确认 (HITL)** - 中高风险操作需用户确认
3. **执行预览 (Dry-Run)** - 修改性操作先展示计划
4. **审计追溯** - 所有操作记录到日志

### 1.3 范围

| 功能 | 优先级 | 说明 |
|------|--------|------|
| 风险评估引擎 | P0 | 评估每个工具调用的风险等级 |
| HITL 人工确认 | P0 | 终端交互式确认 |
| Dry-Run 预览 | P0 | 执行计划生成和展示 |
| 审计日志 | P0 | 写入 JSON Lines 文件 |
| 置信度机制 | P0 | AI 自报 + 低置信度确认 |

---

## 二、架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      LangGraph 状态机                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  START ──► agent ──► route ──► preview ──► hitl ──► tools     │
│               │          │          │         │         │      │
│               │          │          │         │         │      │
│               │      ┌───┴───┐      │         │         │      │
│               │      │       │      │         │         │      │
│               │   execute  deny     │         │         │      │
│               │      │       │      │         │         │      │
│               │      │       └──────┼─────────┤         │      │
│               │      │              │         │         │      │
│               │      ▼              ▼         ▼         ▼      │
│               │   tools         preview   hitl     tools       │
│               │      │              │         │         │      │
│               │      │              └────┬────┘         │      │
│               │      │                   │              │      │
│               │      │              approved?           │      │
│               │      │              │      │            │      │
│               │      │            YES      NO           │      │
│               │      │              │      │            │      │
│               │      │              │      └──────┐     │      │
│               │      │              │             │     │      │
│               │      ▼              ▼             ▼     ▼      │
│               │   audit ◄───────────┴─────────────┴────┘      │
│               │      │                                          │
│               └──────┼──────────────────────────────────────────│
│                      │                                          │
│                      ▼                                          │
│                    agent ──────────────────────────────────────►│
│                      │                                          │
│                      ▼                                          │
│                     END                                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 状态机节点

| 节点 | 职责 | 输入 | 输出 |
|------|------|------|------|
| `agent` | AI 推理，生成工具调用 | messages | messages + tool_calls |
| `route` | 路由决策 | tool_calls | execute / preview / deny |
| `preview` | 生成执行计划 | tool_calls | ExecutionPlan |
| `hitl` | 人工确认 | ExecutionPlan | approved: bool |
| `tools` | 执行工具 | tool_calls | tool_results |
| `audit` | 写审计日志 | tool_calls + results | event_id |

### 2.3 新增模块

```
src/
├── core/
│   ├── risk_guard.py      # 风险评估引擎
│   ├── policy_store.py    # 规则存储
│   ├── hitl.py            # 人工确认交互
│   ├── dry_run.py         # 执行计划生成
│   └── audit.py           # 审计日志
└── agent/
    └── graph.py           # 改造后的状态机
```

---

## 三、数据结构

### 3.1 风险等级

```python
from enum import Enum

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

### 3.2 风险评估结果

```python
from dataclasses import dataclass
from typing import List, Optional

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

### 3.3 执行计划

```python
@dataclass
class ExecutionStep:
    """执行步骤"""
    step_id: int
    tool_name: str
    arguments: dict
    risk_assessment: RiskAssessment
    preview_text: str                    # 操作预览描述

@dataclass
class ExecutionPlan:
    """执行计划"""
    plan_id: str                         # UUID
    steps: List[ExecutionStep]
    total_risk: RiskLevel                # 整体风险（取最高）
    summary: str                         # 计划摘要
    rollback_hint: Optional[str]         # 回滚提示
```

### 3.4 审计事件

```python
@dataclass
class AuditEvent:
    """审计事件"""
    event_id: str                        # UUID
    trace_id: str                        # 全链路追踪 ID
    timestamp: str                       # ISO 8601
    session_id: str                      # 会话 ID
    
    tool_name: str
    arguments: dict                      # 已脱敏
    risk_level: str
    decision: str
    confirm_state: str                   # skipped/confirmed/rejected
    result: str                          # success/failed/denied
    error_message: Optional[str]
    plan_id: Optional[str]
```

---

## 四、风险评估引擎

### 4.1 内置规则

```python
BUILTIN_RULES = {
    # DENY - 直接拒绝
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
    
    # CONFIRM - 需要确认 (中高风险工具)
    "confirm": [
        {"pattern": "restart_*", "reason": "重启服务会导致短暂不可用"},
        {"pattern": "stop_*", "reason": "停止服务会影响可用性"},
        {"pattern": "deploy_*", "reason": "部署会改变服务状态"},
        {"pattern": "rollback_*", "reason": "回滚操作影响较大"},
        {"pattern": "execute_command", "reason": "Shell 命令需要确认"},
        {"pattern": "push_changes", "reason": "推送变更到远程仓库"},
    ],
    
    # ALLOW - 直接执行 (只读工具)
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
```

### 4.2 风险评估逻辑

```python
class RiskGuard:
    """风险评估引擎"""
    
    def __init__(self, policy_store: PolicyStore):
        self.policy_store = policy_store
    
    def assess(self, tool_name: str, arguments: dict) -> RiskAssessment:
        """
        评估工具调用风险
        
        优先级: DENY > CONFIRM > ALLOW
        """
        rules = self.policy_store.get_rules()
        
        # 1. 检查 DENY 规则
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
        
        # 2. 检查 CONFIRM 规则
        for rule in rules.get("confirm", []):
            if self._match_pattern(tool_name, arguments, rule["pattern"]):
                # 进一步判断风险等级
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
        
        # 3. 默认 ALLOW
        return RiskAssessment(
            tool_name=tool_name,
            risk_level=RiskLevel.LOW,
            decision=RiskDecision.ALLOW,
            reason="未匹配任何风险规则",
            matched_rule=None,
            affected_resources=[],
            rollback_possible=True
        )
    
    def _match_pattern(self, tool_name: str, arguments: dict, pattern: str) -> bool:
        """
        匹配规则模式
        
        支持两种模式:
        1. 工具名通配符: restart_* 匹配 restart_docker_container
        2. 参数内容: rm -rf 匹配 execute_command 的 command 参数
        """
        # 工具名通配符匹配
        if "*" in pattern:
            prefix = pattern.rstrip("*")
            if tool_name.startswith(prefix):
                return True
        elif tool_name == pattern:
            return True
        
        # 参数内容匹配 (针对 execute_command)
        if "command" in arguments:
            if pattern in arguments["command"]:
                return True
        
        return False
    
    def _determine_risk_level(self, tool_name: str, arguments: dict) -> RiskLevel:
        """确定风险等级"""
        # 检查是否涉及生产环境关键词
        prod_keywords = ["prod", "production", "live", "master", "main"]
        args_str = str(arguments).lower()
        
        for keyword in prod_keywords:
            if keyword in args_str:
                return RiskLevel.HIGH  # 生产环境操作升级为高风险
        
        return RiskLevel.MEDIUM
    
    def _check_rollback_possible(self, tool_name: str) -> bool:
        """检查是否可回滚"""
        non_rollback_tools = {"execute_command", "push_changes"}
        return tool_name not in non_rollback_tools
```

### 4.3 用户配置覆盖

```yaml
# ~/.pulao/policies.yaml (可选)

# 用户自定义规则，与内置规则合并
rules:
  deny:
    - pattern: "rm -rf /data/production"
      reason: "禁止删除生产数据目录"
  
  confirm:
    - pattern: "deploy_cluster_*"
      reason: "集群部署需要确认"
  
  allow:
    - pattern: "restart_*"
      reason: "公司策略允许直接重启"  # 覆盖内置的 confirm 规则
```

---

## 五、Dry-Run 执行计划

### 5.1 执行计划生成

```python
class DryRunExecutor:
    """Dry-Run 执行器"""
    
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
            
            # 生成预览描述
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
        """生成操作预览描述"""
        previews = {
            "deploy_service": f"部署服务 '{args.get('project_name', 'unknown')}'",
            "deploy_cluster_service": f"集群部署 '{args.get('project_name', 'unknown')}'",
            "restart_docker_container": f"重启容器 '{args.get('container_name', 'unknown')}'",
            "stop_docker_container": f"停止容器 '{args.get('container_name', 'unknown')}'",
            "rollback_deploy": f"回滚服务 '{args.get('project_name', 'unknown')}'",
            "execute_command": f"执行命令: {args.get('command', 'unknown')}",
            "push_changes": f"推送变更: {args.get('message', 'Update')}",
        }
        return previews.get(tool_name, f"执行 {tool_name}")
    
    def _generate_summary(self, steps: List[ExecutionStep]) -> str:
        """生成计划摘要"""
        total = len(steps)
        risk_counts = {}
        for step in steps:
            level = step.risk_assessment.risk_level.value
            risk_counts[level] = risk_counts.get(level, 0) + 1
        
        parts = [f"共 {total} 个操作"]
        for level, count in risk_counts.items():
            parts.append(f"{level}: {count}")
        
        return ", ".join(parts)
    
    def _generate_rollback_hint(self, steps: List[ExecutionStep]) -> Optional[str]:
        """生成回滚提示"""
        rollbackable = [s for s in steps if s.risk_assessment.rollback_possible]
        
        if len(rollbackable) == len(steps):
            return "所有操作均可通过相应命令回滚"
        elif len(rollbackable) == 0:
            return "警告: 操作不可逆，请谨慎确认"
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

---

## 六、HITL 人工确认

### 6.1 确认交互

```python
from rich.console import Console
from rich.table import Table

console = Console()

class HITLController:
    """人工确认控制器"""
    
    @staticmethod
    def confirm(plan: ExecutionPlan) -> bool:
        """
        展示执行计划并等待用户确认
        
        Returns:
            True: 用户确认执行
            False: 用户拒绝
        """
        console.print(f"\n[bold]📋 执行计划预览[/bold]")
        console.print(f"[dim]计划 ID: {plan.plan_id}[/dim]")
        
        # 风险等级颜色
        risk_colors = {
            RiskLevel.READONLY: "green",
            RiskLevel.LOW: "green",
            RiskLevel.MEDIUM: "yellow",
            RiskLevel.HIGH: "red",
            RiskLevel.CRITICAL: "red bold",
        }
        risk_color = risk_colors.get(plan.total_risk, "white")
        
        console.print(f"整体风险: [{risk_color}]{plan.total_risk.value.upper()}[/{risk_color}]")
        console.print(f"摘要: {plan.summary}\n")
        
        # 步骤列表
        for step in plan.steps:
            step_color = risk_colors.get(step.risk_assessment.risk_level, "white")
            icon = {"readonly": "📖", "low": "🟢", "medium": "🟡", "high": "🔴", "critical": "⛔"}.get(
                step.risk_assessment.risk_level.value, "⚪"
            )
            
            console.print(f"  {icon} [{step_color}]{step.preview_text}[/{step_color}]")
            
            # 高风险显示原因
            if step.risk_assessment.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
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
```

### 6.2 交互示例

```
用户: 帮我重启 web-server 容器并清理旧日志

AI: 我将执行以下操作...

📋 执行计划预览
计划 ID: plan_a1b2c3d4
整体风险: 🟡 MEDIUM
摘要: 共 2 个操作, medium: 2

  🟡 重启容器 'web-server'
     ⚠️  重启服务会导致短暂不可用
  🟡 执行命令: rm -f /var/log/old_logs/*.log
     ⚠️  Shell 命令需要确认

部分操作可回滚 (1/2)

是否执行以上 2 个操作? [y/N]: y

✅ 执行中...
```

---

## 七、审计日志

### 7.1 日志管理器

```python
import json
from datetime import datetime, timezone
from pathlib import Path
import uuid

class AuditLogger:
    """审计日志管理器"""
    
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
        error_message: str = None,
        plan_id: str = None
    ) -> str:
        """写入审计日志"""
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
        
        cls.AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
        
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

### 7.2 日志格式示例

```json
{"event_id":"evt_a1b2c3d4e5f6","trace_id":"trace_xyz","timestamp":"2026-04-03T10:30:00+00:00","session_id":"sess_456","tool_name":"deploy_service","arguments":{"project_name":"web-app","yaml_content":"..."},"risk_level":"medium","decision":"confirm","confirm_state":"confirmed","result":"success","error_message":null,"plan_id":"plan_abc"}
```

### 7.3 日志位置

```bash
~/.pulao/audit.log

# 查看最近记录
tail -20 ~/.pulao/audit.log

# 实时监控
tail -f ~/.pulao/audit.log

# 搜索失败操作
grep '"result":"failed"' ~/.pulao/audit.log
```

---

## 八、置信度机制

### 8.1 Prompt 改造

在系统提示词中添加置信度输出要求：

```python
CONFIDENCE_INSTRUCTION = """
## 置信度输出要求

当你决定调用工具时，必须在内部思考中评估置信度：

置信度评分规则：
- 0.9-1.0: 非常确定，有明确证据支持
- 0.7-0.9: 比较确定，但存在不确定性
- 0.5-0.7: 中等确定，可能有其他原因
- 0.3-0.5: 不太确定，建议先收集更多信息
- 0.0-0.3: 非常不确定，不应执行

当置信度低于 0.8 时：
1. 考虑是否可以先执行只读操作收集更多信息
2. 提供替代方案供用户选择
3. 不要直接执行高风险操作
"""
```

### 8.2 置信度解析与处理

```python
class ConfidenceHandler:
    """置信度处理器"""
    
    LOW_CONFIDENCE_THRESHOLD = 0.8
    
    @classmethod
    def handle(cls, confidence: float, reasoning: str, alternatives: List[dict]) -> bool:
        """
        处理低置信度情况
        
        Returns:
            True: 继续执行
            False: 用户拒绝
        """
        if confidence >= cls.LOW_CONFIDENCE_THRESHOLD:
            return True
        
        # 低置信度提示
        console.print(f"\n[yellow]⚠️  置信度: {confidence:.0%}[/yellow]")
        console.print(f"[dim]{reasoning}[/dim]")
        
        if alternatives:
            console.print("\n[bold]替代方案:[/bold]")
            for i, alt in enumerate(alternatives, 1):
                console.print(f"  {i}. {alt.get('description', '')} (置信度: {alt.get('confidence', 0):.0%})")
        
        console.print(f"\n[bold]置信度低于 {cls.LOW_CONFIDENCE_THRESHOLD:.0%}，是否继续?[/bold] [y/N]: ", end="")
        
        try:
            choice = input().strip().lower()
            return choice in ('y', 'yes')
        except (EOFError, KeyboardInterrupt):
            return False
```

---

## 九、LangGraph 状态机改造

### 9.1 状态定义

```python
from typing import TypedDict, List, Optional, Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """Agent 状态"""
    messages: Annotated[List[BaseMessage], add_messages]
    
    # 安全框架新增
    trace_id: str
    execution_plan: Optional[ExecutionPlan]
    confirmed: bool
    denied_reason: Optional[str]
    audit_events: List[str]
```

### 9.2 节点函数

```python
def route_node(state: AgentState) -> str:
    """路由决策"""
    last_message = state["messages"][-1]
    
    if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
        return "end"
    
    # 评估所有工具调用的风险
    highest_decision = RiskDecision.ALLOW
    
    for tc in last_message.tool_calls:
        assessment = risk_guard.assess(tc["name"], tc.get("args", {}))
        
        if assessment.decision == RiskDecision.DENY:
            return "deny"
        if assessment.decision == RiskDecision.CONFIRM:
            highest_decision = RiskDecision.CONFIRM
    
    if highest_decision == RiskDecision.CONFIRM:
        return "preview"
    
    return "execute"

def preview_node(state: AgentState) -> dict:
    """生成执行计划"""
    last_message = state["messages"][-1]
    tool_calls = last_message.tool_calls
    
    plan = dry_run_executor.generate_plan(tool_calls)
    
    return {
        "execution_plan": plan
    }

def hitl_node(state: AgentState) -> dict:
    """人工确认"""
    plan = state["execution_plan"]
    
    # 检查是否有 DENY 的步骤
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

def audit_node(state: AgentState) -> dict:
    """审计日志"""
    # 从 state 中提取执行结果，写入审计日志
    event_ids = []
    
    # ... 实现细节
    
    return {
        "audit_events": state.get("audit_events", []) + event_ids
    }
```

### 9.3 图构建

```python
from langgraph.graph import StateGraph, END, START

def create_agent_app(config: dict):
    tools = create_langchain_tools()
    tool_node = ToolNode(tools)
    
    model = ChatOpenAI(
        api_key=config.get("api_key"),
        base_url=config.get("base_url"),
        model=config.get("model", "gpt-4o"),
        temperature=0,
    ).bind_tools(tools)
    
    workflow = StateGraph(AgentState)
    
    # 节点
    workflow.add_node("agent", agent_node)
    workflow.add_node("preview", preview_node)
    workflow.add_node("hitl", hitl_node)
    workflow.add_node("tools", tool_node)
    workflow.add_node("audit", audit_node)
    
    # 边
    workflow.add_edge(START, "agent")
    
    # agent 路由
    workflow.add_conditional_edges(
        "agent",
        route_node,
        {
            "end": END,
            "execute": "tools",
            "preview": "preview",
            "deny": "agent",  # 返回 agent 重新规划
        }
    )
    
    # preview -> hitl -> (tools 或 agent)
    workflow.add_edge("preview", "hitl")
    workflow.add_conditional_edges(
        "hitl",
        lambda state: "execute" if state["confirmed"] else "reject",
        {
            "execute": "tools",
            "reject": "agent"
        }
    )
    
    # tools -> audit -> agent
    workflow.add_edge("tools", "audit")
    workflow.add_edge("audit", "agent")
    
    return workflow.compile()
```

---

## 十、文件清单

### 10.1 新增文件

| 文件 | 行数估算 | 说明 |
|------|---------|------|
| `src/core/risk_guard.py` | ~150 | 风险评估引擎 |
| `src/core/policy_store.py` | ~80 | 规则存储 |
| `src/core/hitl.py` | ~60 | 人工确认 |
| `src/core/dry_run.py` | ~100 | 执行计划生成 |
| `src/core/audit.py` | ~50 | 审计日志 |
| `tests/core/test_risk_guard.py` | ~200 | 单元测试 |
| `tests/core/test_dry_run.py` | ~150 | 单元测试 |
| `tests/core/test_audit.py` | ~100 | 单元测试 |

### 10.2 修改文件

| 文件 | 改动说明 |
|------|---------|
| `src/agent/graph.py` | 改造状态机，插入安全节点 |
| `src/agent/orchestrator.py` | 添加 trace_id 生成 |
| `src/agent/prompts.py` | 添加置信度输出指令 |
| `src/core/config.py` | 添加 policy_store 配置路径 |

---

## 十一、测试计划

### 11.1 单元测试

```python
# tests/core/test_risk_guard.py

def test_deny_rm_rf_root():
    """测试 rm -rf / 被拒绝"""
    assessment = risk_guard.assess("execute_command", {"command": "rm -rf /"})
    assert assessment.decision == RiskDecision.DENY

def test_confirm_restart_container():
    """测试重启容器需要确认"""
    assessment = risk_guard.assess("restart_docker_container", {"container_name": "web"})
    assert assessment.decision == RiskDecision.CONFIRM

def test_allow_get_logs():
    """测试获取日志直接执行"""
    assessment = risk_guard.assess("get_logs", {"container_name": "web"})
    assert assessment.decision == RiskDecision.ALLOW

def test_user_rule_override():
    """测试用户规则覆盖内置规则"""
    # 配置用户规则允许 restart_*
    policy_store.add_user_rule("allow", "restart_*", "用户允许")
    
    assessment = risk_guard.assess("restart_docker_container", {"container_name": "web"})
    assert assessment.decision == RiskDecision.ALLOW
```

### 11.2 集成测试

```python
# tests/agent/test_security_flow.py

def test_deny_flow():
    """测试 DENY 流程：拒绝后返回 agent 重新规划"""
    pass

def test_confirm_flow_accepted():
    """测试 CONFIRM 流程：用户确认后执行"""
    pass

def test_confirm_flow_rejected():
    """测试 CONFIRM 流程：用户拒绝后返回 agent"""
    pass
```

---

## 十二、实施计划

### 12.1 开发顺序

```
Week 1-2: 安全基础
├── Day 1-3:  risk_guard.py + policy_store.py
├── Day 4-5:  hitl.py + dry_run.py
├── Day 6-7:  audit.py
└── Day 8-10: graph.py 改造 + 单元测试

Week 3-4: 置信度 + 集成
├── Day 1-2:  prompts.py 改造
├── Day 3-4:  置信度解析与处理
├── Day 5-7:  集成测试
└── Day 8-10: 文档 + 边界情况处理
```

### 12.2 验收标准

- [ ] `rm -rf /` 等 DENY 规则操作被拦截
- [ ] `restart_*` 等 CONFIRM 规则操作弹出确认
- [ ] `get_*` 等 ALLOW 规则操作直接执行
- [ ] 审计日志正确记录所有操作
- [ ] 用户配置可覆盖内置规则
- [ ] 单元测试覆盖率 > 90%

---

*文档版本: 1.0*
*最后更新: 2026-04-03*
