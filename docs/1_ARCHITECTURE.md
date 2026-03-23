# Pulao 项目核心架构与流程 (Architecture & Workflow)

## 1. 系统架构概述
Pulao 采用分层架构设计，从上到下依次为用户交互层、AI核心处理层、Agent编排层、工具执行层和底层服务层。当前核心架构由 **LangGraph** 驱动，采用状态机（StateGraph）来编排 AI 的思考与执行过程。

### 核心模块职责映射

| 模块层级 | 核心文件 | 职责说明 |
| :--- | :--- | :--- |
| **用户交互层** | `src/main.py` | 1. 使用 Typer 构建 CLI。<br>2. REPL循环实现 (基于 prompt_toolkit)。<br>3. 拦截高危命令与解析。 |
| **AI 核心处理层** | `src/ai.py` | 1. 封装 AISession 类管理 OpenAI 客户端。<br>2. RAG 检索与上下文拼接。<br>3. 调用 Agent 编排层。 |
| **Agent 编排层** | `src/ai_agent.py` | 1. 定义 LangGraph 状态(State)。<br>2. 定义 `call_model` 与 `execute_tools` 节点。<br>3. 构建循环边 (Edges)。 |
| **工具执行层** | `src/tools.py` | 1. `ToolRegistry` 装饰器注册表。<br>2. 将 Python 函数转换为 OpenAI 工具模式。 |
| **底层服务层** | `src/docker_ops.py`<br>`src/remote_ops.py`<br>`src/cluster.py` | 1. Docker Compose 部署执行。<br>2. SSH 远程操作封装。<br>3. YAML/JSON 配置解析。 |
| **支撑服务层** | `src/memory.py`<br>`src/config.py` | 1. 短期记忆 (JSON) + 长期经验 (ChromaDB)。<br>2. 多 LLM 提供商配置与环境兜底。 |

---

## 2. 核心执行工作流 (Workflow)

```mermaid
graph TD
    A[用户输入 (main.py)] --> B{是否 Shell 命令?}
    B -- Yes --> C[执行 Shell]
    B -- No --> D[process_deployment (ai.py)]
    D --> E[RAG 向量检索 & 模板匹配]
    E --> F[进入 LangGraph 状态机 (ai_agent.py)]
    F --> G((调用 LLM 节点))
    G --> H{需要调工具?}
    H -- Yes --> I[Tools 节点执行 (tools.py)]
    I --> G
    H -- No --> J[输出最终回复]
    J --> K[记忆沉淀至 ChromaDB]
```

### 详细步骤：
1. **预处理与记忆检索 (`src/ai.py`)**:
   - 系统首先在 `ChromaDB` 中搜索历史是否部署过类似服务，提取成功经验（RAG）。
   - 检查本地模板库 (`LibraryManager`) 是否有对应的官方配置。
   - 将“用户输入 + 历史经验 + 模板参考”拼接为最终的 Prompt。
2. **进入 Agent 状态机 (`src/ai_agent.py`)**:
   - `START` -> `agent` 节点：调用 LLM (如 DeepSeek/GPT-4)。
   - LLM 决定需要调用工具 `deploy_service`。
   - 状态机流转到 `tools` 节点：执行 `src/tools.py` 中的对应函数。
   - 工具执行完毕，结果写回 State，状态机流回 `agent` 节点。
   - LLM 看到执行成功，输出最终回复。状态机流转到 `END`。
3. **记忆沉淀 (`src/ai.py`)**:
   - 部署完成后，系统自动将此次“指令 + 结果摘要”存入 `ChromaDB`，供下次 RAG 使用。

---

## 3. 关键设计模式与架构决策 (ADR)

### 3.1 设计模式应用
* **单例模式**: `_CURRENT_SESSION` 和 `get_session` 确保 REPL 循环中只有一个对话实例。
* **注册表模式**: `ToolRegistry` 使用 `@registry.register` 集中管理所有可用工具。
* **策略模式**: `config.py` 支持在不同的 LLM Provider (DeepSeek/OpenAI) 之间动态切换策略。

### 3.2 历史重大决策
* **[2026-03] 抛弃手写 ReAct 循环**：将核心引擎从手写 `while` 循环迁移至 LangGraph。
  * **原因**: 解决了旧架构在处理复杂多步任务时容易死循环、难以扩展多 Agent 协作的技术债务。
* **[2026-02] 引入 ChromaDB**：
  * **原因**: 解决 AI“健忘”问题，不再依赖无限增长的 Context Window，采用向量检索复用历史经验。