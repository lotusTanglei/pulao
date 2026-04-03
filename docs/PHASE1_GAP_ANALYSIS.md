# Phase 1 功能差距分析

> 本文档分析当前项目实现状态与 Phase 1 目标的差距，为后续开发提供优先级指导。

---

## 一、整体完成度概览

```
Phase 1 总体进度: ████████░░░░░░░░░░░░ 40%

已完成: 基础运维能力 (Docker/System/Cluster/Security 工具集)
进行中: 安全机制增强
未开始: 置信度、审计、Dry-Run
```

| 里程碑 | 状态 | 完成度 |
|--------|------|--------|
| 1.1 危险操作确认机制 | 🔴 未实现 | 0% |
| 1.2 部署回滚能力 | 🟡 部分完成 | 30% |
| 1.3 模板库完善 | 🟡 部分完成 | 60% |
| 1.4 监控诊断增强 | 🟢 基本完成 | 80% |
| 1.5 置信度机制与审计日志 | 🔴 未实现 | 0% |
| 1.6 Dry-Run First 模式 | 🔴 未实现 | 0% |

---

## 二、功能差距详细分析

### 2.1 危险操作确认机制 (HITL)

**优先级**: P0 | **状态**: 🔴 未实现 | **完成度**: 0%

#### 设计要求

```
用户输入 → Agent → 工具调用请求
                        ↓
              ┌─────────────────────┐
              │   Risk Guard        │
              │   风险评估引擎       │
              └─────────────────────┘
                        ↓
         ┌──────────────┼──────────────┐
         ↓              ↓              ↓
      DENY          CONFIRM         ALLOW
    (硬阻断)       (人工确认)       (直接执行)
```

#### 当前状态

| 子功能 | 状态 | 说明 |
|--------|------|------|
| 风险分级引擎 | ❌ | 没有 `src/core/risk_guard.py` |
| 规则优先级系统 | ❌ | 没有 deny/confirm/allow 规则定义 |
| HITL 确认状态机 | ❌ | 没有 WAIT_INPUT → APPROVED/REJECTED 流程 |
| 上下文感知风险上浮 | ❌ | 生产环境风险等级不自动上浮 |
| 用户自定义危险操作 | ❌ | 没有配置扩展机制 |

#### 缺口清单

```python
# 需要新增的文件
src/core/risk_guard.py          # 风险评估引擎
src/core/hitl.py                # 人工确认状态机
src/core/policy_store.py        # 规则存储（支持用户扩展）

# 需要修改的文件
src/agent/graph.py              # 在 agent 和 tools 之间插入 Risk Guard 节点
src/agent/orchestrator.py       # 集成 HITL 确认流程
```

#### 预计工作量

| 任务 | 预计时间 |
|------|---------|
| 风险评估引擎设计与实现 | 3 天 |
| HITL 确认状态机 | 2 天 |
| 规则存储与用户扩展 | 1 天 |
| LangGraph 图改造 | 2 天 |
| 单元测试 | 2 天 |
| **合计** | **10 天 (2 周)** |

---

### 2.2 部署回滚能力

**优先级**: P1 | **状态**: 🟡 部分完成 | **完成度**: 30%

#### 设计要求

```
PRECHECK → SNAPSHOT → DEPLOY → HEALTH_CHECK
                              ↓
                    ┌─────────┴─────────┐
                    ↓                   ↓
                 SUCCESS            FAILED
                    ↓                   ↓
                   END            AUTO_ROLLBACK
                                          ↓
                                      RESTORE
                                          ↓
                                      FAILED/OK
```

#### 当前状态

| 子功能 | 状态 | 说明 |
|--------|------|------|
| `rollback_service()` | ✅ | 已实现 `docker compose down` |
| 部署前快照 | ❌ | 不记录容器/网络/卷元数据 |
| 健康检查 | ❌ | 没有 `HEALTH_CHECK` 节点 |
| 自动回滚触发 | ❌ | 部署失败不自动触发回滚 |
| 快照恢复 | ❌ | 无法恢复到快照状态 |

#### 缺口清单

```python
# 需要新增的文件/功能
src/tools/docker/snapshot.py   # 部署快照管理
  - create_deployment_snapshot()   # 创建快照
  - restore_from_snapshot()        # 从快照恢复
  - list_snapshots()               # 快照列表

# 需要修改的文件
src/tools/docker/docker_ops.py # 集成快照和自动回滚
src/tools/system/ops_diagnostics.py # 增强 health_check 能力
src/agent/graph.py              # 添加 Observe 节点
```

#### 快照数据结构设计

```python
@dataclass
class DeploymentSnapshot:
    """部署快照"""
    snapshot_id: str              # UUID
    service_name: str             # 服务名称
    created_at: datetime          # 创建时间

    # 容器配置
    image: str                    # 镜像名称
    env_vars: Dict[str, str]      # 环境变量
    volumes: List[str]            # 挂载卷
    ports: List[str]              # 端口映射
    networks: List[str]           # 网络

    # Compose 文件
    compose_content: str          # 原 compose 文件内容
    compose_path: str             # 文件路径

    # 状态
    containers: List[ContainerState]  # 容器运行状态
```

#### 预计工作量

| 任务 | 预计时间 |
|------|---------|
| 快照数据结构设计 | 1 天 |
| 快照管理实现 | 3 天 |
| 健康检查节点实现 | 2 天 |
| 自动回滚逻辑 | 2 天 |
| LangGraph Observe 节点 | 1 天 |
| 单元测试 | 2 天 |
| **合计** | **11 天 (约 2.5 周)** |

---

### 2.3 模板库管理

**优先级**: P1 | **状态**: 🟡 部分完成 | **完成度**: 60%

#### 当前状态

| 子功能 | 状态 | 说明 |
|--------|------|------|
| 模板获取 | ✅ | `LibraryManager.get_template()` |
| 远程更新 | ✅ | `update_library()` Git clone/pull |
| 模糊搜索 | ✅ | 精确匹配 + 模糊匹配策略 |
| 分类/标签 | ❌ | 不支持分类和标签 |
| 版本管理 | ❌ | 没有 version 字段和版本回退 |
| 软删除/恢复 | ❌ | 没有 status 字段 |
| Schema 校验 | ❌ | 入库前不校验 |

#### 缺口清单

```python
# 需要修改的文件
src/tools/utils/library_manager.py  # 增强资产化管理

# 需要新增的数据结构
@dataclass
class TemplateAsset:
    """模板资产"""
    id: str                      # UUID
    name: str                    # 模板名称
    category: str                # 分类 (database/web/mq/...)
    tags: List[str]              # 标签
    version: int                 # 版本号
    schema_version: str          # Schema 版本
    status: str                  # active | deleted
    created_at: datetime
    updated_at: datetime
    content: str                 # compose 内容
    schema: Optional[Dict]       # values.schema.json
```

#### 预计工作量

| 任务 | 预计时间 |
|------|---------|
| 资产数据结构设计 | 1 天 |
| 版本管理实现 | 2 天 |
| 分类/标签系统 | 1 天 |
| 软删除/恢复 | 1 天 |
| Schema 校验集成 | 1 天 |
| 单元测试 | 1 天 |
| **合计** | **7 天 (约 1.5 周)** |

---

### 2.4 监控诊断增强

**优先级**: P0 | **状态**: 🟢 基本完成 | **完成度**: 80%

#### 当前状态

| 子功能 | 状态 | 说明 |
|--------|------|------|
| 容器日志获取 | ✅ | `get_container_logs()` |
| 日志分析 | ✅ | `analyze_logs()` 错误/警告模式匹配 |
| 容器状态检查 | ✅ | `check_container_status()` |
| 资源监控 | ✅ | CPU/内存/磁盘/负载 |
| 网络诊断 | ✅ | 端口/连通性/DNS |
| 综合诊断 | ✅ | `diagnose_service()` |
| 滑动窗口截断 | ❌ | 大日志无截断机制 |
| 摘要压缩 | ❌ | 无 LLM 摘要压缩 |

#### 缺口清单

```python
# 需要修改的文件
src/tools/system/ops_diagnostics.py

# 需要新增的功能
def truncate_logs_with_sliding_window(
    logs: str,
    max_tokens: int = 4000,
    window_size: int = 500
) -> str:
    """
    滑动窗口日志截断

    策略:
    1. 保留最近 N 条日志
    2. 提取错误/警告关键行
    3. 如果仍超限，调用 LLM 压缩
    """
    pass
```

#### 预计工作量

| 任务 | 预计时间 |
|------|---------|
| 滑动窗口截断实现 | 1 天 |
| LLM 摘要压缩集成 | 1 天 |
| 单元测试 | 0.5 天 |
| **合计** | **2.5 天** |

---

### 2.5 置信度机制

**优先级**: P0 | **状态**: 🔴 未实现 | **完成度**: 0%

#### 设计要求

```python
# 工具调用时附带置信度
{
    "action": "restart_pod",
    "confidence": 0.72,
    "reasoning": "基于日志分析，可能是内存泄漏导致",
    "alternatives": [
        {"action": "increase_memory", "confidence": 0.85},
        {"action": "check_memory_leak", "confidence": 0.80}
    ]
}

# 置信度 < 0.8 时
if confidence < 0.8:
    # 1. 展示置信度和推理过程
    # 2. 展示替代方案
    # 3. 强制人工确认
```

#### 缺口清单

```python
# 需要新增的文件
src/agent/confidence.py        # 置信度评估模块
  - ConfidenceEvaluator            # 置信度评估器
  - evaluate_confidence()          # 评估工具调用置信度
  - generate_alternatives()        # 生成替代方案

# 需要修改的文件
src/agent/graph.py              # 在工具调用前插入置信度评估
src/agent/prompts.py            # 修改 system prompt 要求 AI 输出置信度
src/core/hitl.py                # 低置信度时触发强制确认
```

#### 置信度评估策略

```python
class ConfidenceEvaluator:
    """置信度评估器"""

    def evaluate(self, tool_name: str, args: dict, context: dict) -> float:
        """
        评估工具调用的置信度

        考虑因素:
        1. AI 自报置信度 (从响应中解析)
        2. 历史成功率 (该工具过去执行的成功率)
        3. 上下文匹配度 (用户意图与工具功能的匹配程度)
        4. 风险等级 (高风险操作降低置信度)
        """
        pass
```

#### 预计工作量

| 任务 | 预计时间 |
|------|---------|
| 置信度数据结构设计 | 1 天 |
| 置信度评估器实现 | 2 天 |
| Prompt 改造（要求输出置信度） | 1 天 |
| 低置信度强制确认集成 | 1 天 |
| 单元测试 | 1 天 |
| **合计** | **6 天 (约 1.5 周)** |

---

### 2.6 审计日志

**优先级**: P0 | **状态**: 🔴 未实现 | **完成度**: 0%

#### 设计要求

```python
@dataclass
class AuditEvent:
    """审计事件"""
    event_id: str                 # UUID
    trace_id: str                 # 全链路追踪 ID
    timestamp: datetime           # 事件时间

    # 操作者
    actor: str                    # 用户标识
    session_id: str               # 会话 ID

    # 操作
    action: str                   # 操作类型
    tool_name: str                # 工具名称
    arguments: Dict               # 参数 (敏感信息脱敏)

    # 风险控制
    risk_level: str               # low | medium | high | critical
    confidence: float             # 置信度

    # 确认状态
    confirm_state: str            # skipped | confirmed | rejected | timeout
    confirm_by: Optional[str]     # 确认人

    # 执行结果
    result: str                   # success | failed | rollback
    error_message: Optional[str]

    # 回滚信息
    rollback_from: Optional[str]  # 从哪个事件回滚
    snapshot_id: Optional[str]    # 关联的快照
```

#### 缺口清单

```python
# 需要新增的文件
src/core/audit.py              # 审计日志模块
  - AuditLogger                    # 审计日志记录器
  - AuditEvent                     # 审计事件数据结构
  - write_audit_event()            # 写入审计事件
  - query_audit_events()           # 查询审计事件

# 需要修改的文件
src/agent/graph.py              # 在工具执行后写入审计日志
src/agent/orchestrator.py       # 生成 trace_id
src/core/hitl.py                # 记录确认状态
```

#### 审计日志格式

```json
{
  "event_id": "evt_abc123",
  "trace_id": "trace_xyz789",
  "timestamp": "2026-04-03T10:30:00Z",
  "actor": "admin@example.com",
  "session_id": "sess_456",
  "action": "deploy_service",
  "tool_name": "deploy_compose",
  "arguments": {
    "project_name": "web-app",
    "compose_file": "***REDACTED***"
  },
  "risk_level": "medium",
  "confidence": 0.85,
  "confirm_state": "confirmed",
  "confirm_by": "admin@example.com",
  "result": "success",
  "error_message": null,
  "rollback_from": null,
  "snapshot_id": "snap_123"
}
```

#### 预计工作量

| 任务 | 预计时间 |
|------|---------|
| 审计事件数据结构设计 | 1 天 |
| 审计日志记录器实现 | 2 天 |
| Trace ID 生成与传递 | 1 天 |
| 敏感信息脱敏 | 1 天 |
| LangGraph 集成 | 1 天 |
| 单元测试 | 1 天 |
| **合计** | **7 天 (约 1.5 周)** |

---

### 2.7 Dry-Run First 模式

**优先级**: P0 | **状态**: 🔴 未实现 | **完成度**: 0%

#### 设计要求

```
用户: "帮我扩容 web 服务到 5 副本"
Agent:
  📋 执行计划预览:
  ┌────────────────────────────────────┐
  │ kubectl scale deployment/web       │
  │   --replicas=5                     │
  │   --namespace=production           │
  └────────────────────────────────────┘

  ⚠️ 影响评估:
  ┌────────────────────────────────────┐
  │ 当前副本数: 2                      │
  │ 目标副本数: 5                      │
  │ 预计新增资源:                      │
  │   - CPU: 1.5 核                    │
  │   - 内存: 3 GB                     │
  │ 潜在风险:                          │
  │   - 集群资源利用率将上升至 75%     │
  └────────────────────────────────────┘

  是否执行? [y/N]
```

#### 缺口清单

```python
# 需要新增的文件
src/agent/dry_run.py           # Dry-Run 模式实现
  - DryRunExecutor                 # Dry-Run 执行器
  - generate_execution_plan()      # 生成执行计划
  - estimate_impact()              # 影响评估
  - format_preview()               # 格式化预览

# 需要修改的文件
src/agent/graph.py              # 在执行前插入 Dry-Run 节点
src/agent/orchestrator.py       # 添加 dry_run 参数
src/tools/docker/docker_ops.py # 添加 dry_run 参数支持
```

#### Dry-Run 执行器设计

```python
class DryRunExecutor:
    """Dry-Run 执行器"""

    def preview(self, tool_name: str, args: dict) -> ExecutionPlan:
        """
        生成执行计划预览

        Returns:
            ExecutionPlan:
                - commands: List[str]  # 将执行的命令
                - changes: Dict        # 预期变更
                - risks: List[str]     # 潜在风险
                - resources: Dict      # 资源影响
        """
        pass

    def estimate_impact(self, tool_name: str, args: dict) -> ImpactAssessment:
        """
        影响评估

        Returns:
            ImpactAssessment:
                - current_state: Dict   # 当前状态
                - target_state: Dict    # 目标状态
                - diff: Dict            # 差异
                - warnings: List[str]   # 警告
        """
        pass
```

#### 预计工作量

| 任务 | 预计时间 |
|------|---------|
| 执行计划生成器 | 2 天 |
| 影响评估器 | 2 天 |
| 格式化预览输出 | 1 天 |
| LangGraph 集成 | 1 天 |
| 单元测试 | 1 天 |
| **合计** | **7 天 (约 1.5 周)** |

---

## 三、工作量汇总

### 按功能统计

| 功能 | 优先级 | 完成度 | 剩余工作量 | 建议顺序 |
|------|--------|--------|-----------|---------|
| 危险操作确认 (HITL) | P0 | 0% | 10 天 | **1** |
| 审计日志 | P0 | 0% | 7 天 | **2** |
| 置信度机制 | P0 | 0% | 6 天 | **3** |
| Dry-Run 模式 | P0 | 0% | 7 天 | **4** |
| 部署回滚 | P1 | 30% | 11 天 | 5 |
| 模板库完善 | P1 | 60% | 7 天 | 6 |
| 日志截断 | P0 | 80% | 2.5 天 | 7 |

### 按阶段统计

```
阶段 A (安全基础): HITL + 审计日志
├── 预计时间: 17 天 (约 3.5 周)
└── 产出: 危险操作可拦截、所有操作可追溯

阶段 B (智能增强): 置信度 + Dry-Run
├── 预计时间: 13 天 (约 2.5 周)
└── 产出: 低置信度强制确认、执行前可预览

阶段 C (可靠性完善): 回滚 + 模板库 + 日志截断
├── 预计时间: 20.5 天 (约 4 周)
└── 产出: 部署可回滚、模板可版本化、日志不溢出
```

### 总工作量

```
总计: 50.5 天 (约 10 周 / 2.5 个月)

建议排期:
├── 阶段 A: Week 1-4
├── 阶段 B: Week 5-7
└── 阶段 C: Week 8-11
```

---

## 四、建议开发顺序

### 依赖关系图

```
                    ┌─────────────┐
                    │   HITL      │ ← 基础，其他功能依赖
                    │  (P0-1)     │
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           ↓               ↓               ↓
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │  审计日志   │ │  置信度     │ │  Dry-Run    │
    │  (P0-2)     │ │  (P0-3)     │ │  (P0-4)     │
    └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
           │               │               │
           └───────────────┼───────────────┘
                           ↓
                    ┌─────────────┐
                    │  部署回滚   │
                    │  (P1-5)     │
                    └──────┬──────┘
                           ↓
                    ┌─────────────┐
                    │ 模板库完善  │
                    │  (P1-6)     │
                    └─────────────┘
```

### 第一优先级: HITL + 审计日志

**原因**: 这是安全基线，没有这两个功能，Agent 不能用于生产环境。

**交付物**:
- `src/core/risk_guard.py` - 风险评估引擎
- `src/core/hitl.py` - 人工确认状态机
- `src/core/audit.py` - 审计日志
- LangGraph 图改造 - 插入安全节点

### 第二优先级: 置信度 + Dry-Run

**原因**: 提升用户体验，减少误操作。

**交付物**:
- `src/agent/confidence.py` - 置信度评估
- `src/agent/dry_run.py` - Dry-Run 模式

### 第三优先级: 可靠性完善

**原因**: 锦上添花，可以并行开发。

**交付物**:
- 部署快照与回滚
- 模板版本管理
- 日志截断

---

## 五、下一步行动

### 立即开始

1. **创建功能分支**: `feature/phase1-hitl-audit`
2. **设计数据结构**: 风险规则、审计事件
3. **实现 HITL**: 先实现最简单的确认流程

### 本周目标

- [ ] 完成 `src/core/risk_guard.py` 基础框架
- [ ] 完成 `src/core/hitl.py` 状态机
- [ ] 完成 `src/core/audit.py` 审计日志
- [ ] 改造 `src/agent/graph.py` 插入安全节点

### 验收标准

```bash
# 测试 HITL
pytest tests/core/test_risk_guard.py -v
pytest tests/core/test_hitl.py -v

# 测试审计日志
pytest tests/core/test_audit.py -v

# 集成测试
pytest tests/agent/test_graph_with_security.py -v
```

---

*生成时间: 2026-04-03*
