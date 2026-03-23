# 📚 Pulao 核心导航 (Index)

> **使用指南**：本文档是 Pulao 项目的**最高层级入口**。无论你离开多久，从这里开始阅读，可以通过链接跳转到你需要的任何细节。

---

## 1. 📂 文档地图 (Document Map)

当前的 `docs/` 目录结构按**生命周期**和**功能边界**进行了划分：

```text
docs/
├── 导航与大纲 (从这里开始)
│   └── INDEX.md                   <-- 本文件，最高入口
│
├── 架构与设计 (底层原理)
│   ├── TECHNICAL_DOC.md           # 核心架构、代码模块职责、LangGraph工作流
│   └── WORKFLOW.md                # 业务执行流（用户输入 -> 意图识别 -> 工具调用）
│
├── 现状与能力 (我们能做什么)
│   ├── CAPABILITY_MATRIX.md       # 详细的能力矩阵（单机/集群/各类中间件支持度）
│   └── PROJECT_EVALUATION.md      # 当前项目的技术债务、痛点评估
│
├── 规划与演进 (我们要去哪)
│   ├── PHASE2_IMPLEMENTATION.md   # [待开发] P0: 监控、告警、智能排障能力
│   └── PHASE3_IMPLEMENTATION.md   # [待开发] P1: 漏洞扫描、权限控制、安全审计
│
└── 测试与维护 (如何保证质量)
    ├── TEST_PLAN.md               # 自动化测试用例与边界条件
    └── LEARNING_GUIDE.md          # 新人/回归开发者上手指南
```

---

## 2. 🧩 系统核心模块映射 (Core Modules)

如果你需要直接改代码，这里是核心模块的快速定位：

| 模块边界 | 核心文件 | 职责说明 | 当前状态 |
| :--- | :--- | :--- | :--- |
| **交互入口** | `src/main.py` | CLI 界面、REPL 循环、命令解析 | 🟢 稳定 |
| **Agent 引擎** | `src/ai.py`<br>`src/ai_agent.py` | LangGraph 编排、大模型调用、历史记录管理 | 🟡 刚完成升级，需观察 |
| **记忆系统** | `src/memory.py` | JSON短期记忆 + ChromaDB 长文本向量记忆(RAG) | 🟢 稳定 |
| **底层工具链** | `src/tools.py` | 暴露给 AI 的所有 Function Calling 注册表 | 🟢 稳定 |
| **执行器** | `src/docker_ops.py`<br>`src/cluster.py` | 实际的 Docker 部署、集群 SSH 分发逻辑 | 🟢 稳定 |

---

## 3. 🎯 核心开发计划 (Roadmap & Todo)

以下是根据评估报告提取的**高优先级待办事项**。当你准备恢复开发时，请从这里挑选：

### 阶段 2：运维能力补全 (Phase 2)
*详细设计见 [PHASE2_IMPLEMENTATION.md](./PHASE2_IMPLEMENTATION.md)*
- [ ] **Feature**: 实现 `ops_diagnostics.py`，允许 AI 读取 `docker logs` 自动排查失败原因。
- [ ] **Feature**: 部署前强制资源预检（端口是否占用、磁盘空间是否充足）。
- [ ] **Refactor**: 优化 `history.json` 的存储机制，防止长期对话导致 Token 溢出。

### 阶段 3：企业级安全与合规 (Phase 3)
*详细设计见 [PHASE3_IMPLEMENTATION.md](./PHASE3_IMPLEMENTATION.md)*
- [ ] **Feature**: 集成 Trivy，在生成 YAML 后、执行部署前进行镜像漏洞扫描。
- [ ] **Feature**: 实现部署快照与回滚机制（记录上一次的 `docker-compose.yml`）。

---

## 4. 📝 更新维护约定

1. **唯一事实来源**：任何新的宏观计划、模块重构，必须先在本文档（`INDEX.md`）中登记。
2. **状态同步**：当完成 Roadmap 中的任务时，请在此处勾选 `[x]`，并同步更新 `CAPABILITY_MATRIX.md`。
3. **废弃归档**：如果某份设计文档（如旧的 ReAct 设计）不再适用，不要直接删除，请移入 `docs/archive/` 目录并标记 `[DEPRECATED]`。