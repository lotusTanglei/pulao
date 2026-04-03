# Pulao Phase 1 详细设计文档（单节点运维）

## 1. 文档定位

本文件是 Phase 1 的详细设计文档，目标是为后续编码提供统一设计基线，而不是本地可执行测试手册。

适用范围：
- 单节点 Docker 运维增强
- 危险操作确认机制
- 部署失败自动回滚
- 模板库能力
- 监控与日志诊断能力

不在本阶段范围：
- 多节点一致性执行
- Ansible 接入
- Kubernetes 集群接入

## 2. 设计约束与前提

### 2.1 约束

- 系统入口为 CLI + LangGraph 编排
- 工具层通过统一注册表暴露能力
- 不允许 AI 直接绕过工具层执行高风险系统命令
- 所有高风险动作必须可审计、可追溯

### 2.2 前提

- 该项目当前不以本地端到端测试为主验证路径
- 设计阶段优先产出模块边界、契约、状态机和失败处理策略
- 验证策略以“可远端执行/可模拟回放”为主

## 3. Phase 1 总体目标

### 3.1 功能目标

- 对高风险运维动作建立强制人工确认门禁
- 部署动作具备失败自动回滚能力
- 模板能力从“单次生成”提升为“可管理资产”
- 监控与诊断输出可用于一线故障定位

### 3.2 非功能目标

- 可追溯：关键动作具备审计事件
- 可恢复：失败路径具备自动回退
- 可控：危险动作存在统一策略开关
- 可演进：模块可扩展到 Phase 2

## 4. 逻辑架构设计

### 4.1 分层架构

```text
User CLI
  -> Interaction Layer (REPL / HITL Confirm)
  -> Orchestration Layer (LangGraph StateFlow)
  -> Policy Gate (Risk Guard / Allow-Deny)
  -> Domain Tools
       - docker
       - security
       - system
  -> Core Services
       - config
       - logging
       - audit
       - i18n
```

### 4.2 核心设计思想

- 编排层只负责任务流转，不承载系统命令细节
- 工具层承载具体执行语义并返回结构化结果
- 策略门控作为跨切能力，对所有执行路径前置生效
- 审计作为全链路旁路，不影响主流程但必须落库成功

## 5. 模块详细设计

## 5.1 风险控制模块（Risk Guard）

### 模块职责

- 对即将执行的动作进行风险分级
- 决定是否必须进入人工确认
- 输出可解释的风险命中原因

### 输入

- tool_name
- tool_args
- runtime_context（环境、角色、会话来源）

### 输出

- risk_level：low / medium / high
- requires_confirm：bool
- matched_rules：命中规则列表
- reason：可读解释

### 规则优先级

1. 硬阻断规则（deny）
2. 强制确认规则（confirm-required）
3. 通行规则（allow）
4. 默认策略（default）

### 关键规则示例

- 包含 `rm -rf /` 直接 deny
- 包含 `shutdown` / `reboot` 强制 confirm
- 生产上下文风险等级自动上浮一级

## 5.2 人工确认模块（HITL）

### 模块职责

- 对高风险动作提供确认交互
- 支持确认、拒绝、超时三种结果
- 将确认过程写入审计

### 状态机

```text
INIT -> WAIT_INPUT -> APPROVED -> FINISH
                  -> REJECTED -> FINISH
                  -> TIMEOUT  -> FINISH
```

### 行为约束

- REJECTED/TIMEOUT 必须中断执行
- APPROVED 才允许下游工具执行

## 5.3 部署与回滚模块（Deploy Guard）

### 模块职责

- 包装部署全过程
- 在执行前创建可恢复快照
- 健康检查失败时自动回滚

### 主流程状态机

```text
PRECHECK -> SNAPSHOT -> DEPLOY -> HEALTH_CHECK -> SUCCESS
                                    |
                                    v
                                 FAILED
                                    |
                                    v
                                 ROLLBACK -> POST_CHECK -> ROLLED_BACK
                                                      |
                                                      v
                                                   MANUAL_TAKEOVER
```

### 关键决策

- 没有快照禁止部署
- 健康检查失败必须回滚
- 回滚失败必须显式上报码并触发人工接管

## 5.4 模板资产模块（Template Store）

### 模块职责

- 将模板从一次性产物升级为可版本化资产
- 提供 CRUD、检索、软删除、恢复

### 数据结构

```yaml
template:
  id: string
  name: string
  category: string
  tags: [string]
  version: int
  content: string
  schema_version: string
  status: active|deleted
  created_at: datetime
  updated_at: datetime
```

### 设计要点

- 更新即新版本
- 删除仅软删除
- 入库前执行 schema 校验

## 5.5 监控与诊断模块（Observe）

### 模块职责

- 采集资源视图：CPU、内存、磁盘、端口
- 处理日志视图：筛选、裁剪、关键行提取
- 给出规则化诊断建议

### 日志处理策略

- 输入日志先按时间窗口切片
- 再按关键词提取关键段
- 再做摘要压缩，输出结构化诊断结果

### 输出结构

```yaml
diagnosis:
  severity: info|warn|critical
  findings:
    - type: string
      evidence: string
      suggestion: string
```

## 6. 编排流程详细设计

## 6.1 统一执行链路

```text
User Intent
  -> Plan Task
  -> Select Tool
  -> Risk Evaluate
  -> HITL Confirm(if needed)
  -> Execute Tool
  -> Observe Result
  -> Audit Persist
  -> Respond
```

## 6.2 错误分层处理

- 业务可恢复错误：进入重试/回滚分支
- 业务不可恢复错误：终止并要求人工介入
- 系统错误：记录错误码、上下文并终止

## 6.3 超时与重试策略

- 外部命令执行可配置超时阈值
- 仅幂等操作允许自动重试
- 非幂等操作失败后默认不重试，走人工确认路径

## 7. 数据与契约设计

## 7.1 审计事件模型

```yaml
audit_event:
  event_id: string
  trace_id: string
  ts: datetime
  actor: string
  action: string
  risk_level: low|medium|high
  confirm_state: approved|rejected|timeout|not_required
  result: success|failed
  rollback: success|failed|na
  error_code: string
  detail: string
```

## 7.2 快照模型

```yaml
deployment_snapshot:
  snapshot_id: string
  project: string
  compose_ref: string
  container_meta: object
  network_meta: object
  volume_meta: object
  created_at: datetime
```

## 7.3 接口契约

- `evaluate_risk(tool_name, args, ctx) -> RiskDecision`
- `request_confirm(action, risk, timeout_sec) -> ConfirmDecision`
- `create_snapshot(project_id) -> SnapshotMeta`
- `deploy(project_id, compose_path) -> DeployResult`
- `rollback(snapshot_id) -> RollbackResult`
- `collect_metrics(target) -> MetricsResult`
- `analyze_logs(target, window, keywords) -> DiagnosisResult`

## 8. 安全设计

### 8.1 访问控制

- 高风险动作需二次确认
- 关键路径支持角色限制
- 默认最小权限执行

### 8.2 输入防护

- 工具参数 schema 强校验
- 高危参数黑名单
- 命令模板化，禁止任意拼接执行

### 8.3 审计与追踪

- 全链路 trace_id
- 每次高风险动作必须有审计记录
- 审计写入失败时主流程返回失败

## 9. 可靠性设计

### 9.1 幂等性

- 只读查询天然幂等
- 部署操作通过 snapshot + 状态检查保障可恢复
- 回滚操作要求“多次执行结果一致”

### 9.2 降级策略

- 模型不可用时提供手动模式
- 诊断能力降级不影响核心部署能力
- 审计不可用时禁止高风险动作执行

### 9.3 可观测性

- 日志分级：info/warn/error
- 指标最小集：执行耗时、失败率、回滚次数、确认拒绝率
- 事件最小集：确认事件、部署事件、回滚事件

## 10. 实施分解（设计到开发映射）

## 10.1 里程碑与顺序

1. M1 风险识别 + HITL 门禁
2. M2 部署快照 + 自动回滚
3. M3 模板资产化管理
4. M4 监控诊断增强

## 10.2 每里程碑最小交付

- M1：策略引擎、确认交互、审计事件打通
- M2：快照接口、健康检查、回滚接口与错误码
- M3：模板模型、版本策略、检索接口
- M4：日志处理链、指标采集、诊断结构输出

## 10.3 远端验证建议

由于不依赖本地端到端测试，建议采用：
- 远端沙箱主机验证关键流程
- 回放任务集验证状态机正确性
- 审计日志抽样校验确认关键事件完整

## 11. 风险与待决策项

### 11.1 主要风险

- 风险规则覆盖不足导致漏拦截
- 快照粒度不足导致回滚不完整
- 日志裁剪过度导致诊断信息丢失

### 11.2 待决策项

- 风险规则存储位置与热更新机制
- 回滚快照是否包含镜像版本锁定
- 审计数据保留周期与归档策略

## 12. 设计完成判定标准

- 模块边界清晰且无职责重叠
- 状态机覆盖主路径和失败路径
- 接口契约可直接转开发任务
- 安全与可靠性策略具备可落地条件
- 待决策项已形成明确 owner 和决策入口
