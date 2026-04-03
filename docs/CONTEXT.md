# Pulao 项目技术全景图

> 本文档为 LLM 辅助开发提供系统级上下文，方便进行代码评审、架构评估及后续开发。

---

## 1. 整体架构设计与核心模块划分

Pulao 采用**领域驱动设计 (DDD)** 的思想，以解耦 AI 的"思考层"和"执行层"。架构自上而下划分为四个核心层次：

- **交互层 (Interaction Layer)**：基于 Typer 与 prompt_toolkit，提供带有语法高亮、自动补全的交互式 REPL 循环。负责指令接收与敏感操作的拦截（Human-in-the-Loop）。
- **编排层 (Orchestration Layer)**：基于 LangGraph 的状态机引擎。负责 RAG 上下文检索、多轮对话记忆聚合，并通过"思考-行动-观察" (ReAct) 循环调用领域工具。
- **领域工具层 (Domain Tools Layer)**：将底层能力封装为 OpenAI Function Calling 格式。分为四个子领域：
  - `Docker`：容器生命周期管理、本地/集群部署。
  - `Cluster`：多节点定义、SSH 连通预检、批量命令分发。
  - `Security`：Trivy 镜像扫描、敏感配置审查。
  - `System`：系统资源监控、端口检查、日志分析。
- **支撑服务层 (Core Services Layer)**：配置管理、国际化 (i18n)、ChromaDB 向量数据库（用于沉淀故障排查经验）、结构化日志。

---

## 2. 技术栈选型依据

| 技术 | 选型理由 |
|------|----------|
| **Python 3.10+** | 兼顾运维脚本编写的便捷性与 LangChain 生态的兼容性 |
| **LangGraph** | 替代早期手写的 `while` ReAct 循环，解决复杂多步任务中死循环、状态难以控制的问题 |
| **ChromaDB** | 轻量级本地向量数据库，极低成本实现运维经验的 RAG 长期记忆 |
| **Typer + Rich** | 现代化 CLI 参数解析 + 美观的 Markdown 渲染、表格和高亮 |
| **Pytest** | 简单且功能强大，配合 `unittest.mock` 完美解决系统底层依赖调用的拦截 |

---

## 3. 当前开发进度与任务状态

**当前整体进度**：**约 40%** (已完成 Phase 1 核心，正在向 Phase 2 集群化和 Ansible 演进阶段过渡)

### 已完成功能

- 交互式 CLI 框架及基于 DeepSeek 等 OpenAI 兼容接口的调用
- 单机 Docker 的自动化部署、状态查询、端口冲突检查
- 危险命令操作前的二次人工确认拦截 (HITL)
- 多节点集群的基本定义、SSH 免密联通性预检、配置文件 SCP 分发
- 安全漏洞扫描与 Docker 日志自我分析

### 进行中的开发任务

- 单节点部署失败的自动化回滚机制 (Rollback)
- 引入 Ansible 替代当前的纯 SSH 子进程循环

### 待解决的技术难点

| 难点 | 描述 | 计划方案 |
|------|------|----------|
| **LLM 上下文溢出** | `docker logs` 大段日志超出模型 Token 限制 | 基于滑动窗口或正则表达式的关键日志截断 |
| **多节点一致性控制** | 纯 Python SSH 执行难以保证幂等性 | 引入 Ansible |
| **提示词注入攻击** | LLM 可能被诱导生成恶意脚本 | 沙箱验证层 + yamllint 校验 |

---

## 4. 项目目录结构与关键配置

### 目录结构

```text
pulao/
├── src/
│   ├── agent/        # LangGraph 编排、Prompt 管理、ChromaDB 记忆检索
│   ├── core/         # 全局配置、日志、子进程安全封装、i18n
│   ├── tools/        # 领域驱动解耦的工具箱
│   │   ├── cluster/  # 节点增删改、SSH 远程执行封装
│   │   ├── docker/   # Docker 环境检测、容器管理、Compose 部署
│   │   ├── security/ # 漏洞扫描、敏感信息检测
│   │   ├── system/   # OS 资源监控、DNS/网络连通性诊断
│   │   └── registry.py # 全局 Tool 注册表
│   └── main.py       # Typer CLI 与 REPL 循环入口
├── tests/            # Pytest 单元测试目录
├── install.sh        # 一键安装脚本
├── pytest.ini        # Pytest 配置文件
└── requirements.txt  # 核心依赖清单
```

### 关键配置文件

| 文件 | 用途 |
|------|------|
| `~/.pulao/config.yaml` | LLM API 密钥、模型名称、语言偏好 |
| `~/.pulao/clusters.yaml` | 多节点集群定义（IP、角色、SSH Key 路径） |
| `~/.pulao/deployments/` | AI 生成的 `docker-compose.yml` 缓存 |

### 主要依赖库

- `langgraph` & `langchain`
- `chromadb`
- `typer`
- `rich`
- `pytest`

---

## 5. 质量保证信息 (QA)

### 测试覆盖率

通过 DDD 重构与代码解耦，`src/agent` 与 `src/tools` 的核心逻辑单元测试覆盖率达到 **100%**。所有底层系统调用均通过 mock 进行隔离验证。

### CI/CD 状态

本项目为早期开发阶段的个人开源项目，**暂未接入线上自动化 CI/CD 流水线**。质量保障依赖本地 `pytest` 回归测试与人工审查。

### 部署环境

- 开发与运行环境：本地 Python 虚拟环境
- 系统兼容：macOS 与 Linux
- 目标节点要求：标准 Docker 守护进程 + 无密码 SSH 信任关系

---

## 6. 已知问题与性能瓶颈

### 已知问题

| 问题 | 影响 | 计划解决 |
|------|------|----------|
| 网络质量差时 SSH 预检阻塞 | 用户体验下降 | 改用 `asyncio` 异步并发检查 |

### 性能瓶颈

| 瓶颈 | 描述 | 优化方案 |
|------|------|----------|
| LLM 响应延迟 | 多步工具调用导致多次网络往返 | 流式输出 + 进度提示 |
| RAG 检索开销 | ChromaDB 初始化耗时随数据增长 | 连接池 + 延迟加载 |

### 安全风险

| 风险 | 描述 | 应对措施 |
|------|------|----------|
| 提示词注入 | LLM 被诱导生成恶意脚本 | 沙箱验证层 + yamllint 校验 |
| 高危路径挂载 | YAML 中挂载 `/etc`、`/` 等系统目录 | 路径黑名单拦截 |

---

## 7. 代码规范与开发约定

- **代码风格**: PEP 8 + Flake8
- **类型注解**: 函数参数和返回值必须使用类型注解
- **文档字符串**: 所有工具函数必须包含 docstring（第一行作为 AI 描述）
- **提交信息**: Conventional Commits (feat/fix/refactor/test/chore/docs)
- **分支模型**: GitFlow (main=生产, develop=开发)
- **测试要求**: 新功能必带单元测试，目标覆盖率 100%

---

*最后更新: 2026-04-03*
