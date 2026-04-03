# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概览

Pulao 是基于 LangGraph 的智能运维 Agent，通过自然语言完成 Docker 部署与系统运维。

### 核心架构

**LangGraph 状态机** ([src/agent/graph.py](src/agent/graph.py)):
- `AgentState`: 消息列表状态，使用 `add_messages` reducer 自动追加消息
- `create_agent_app()`: 构建状态机，包含 agent 节点和 tools 节点
- 流程: START → agent → (tool_calls → tools → agent)* → END

**工具注册系统** ([src/tools/registry.py](src/tools/registry.py)):
- 使用 `@registry.register` 装饰器注册工具
- 自动从函数签名生成 OpenAI 函数调用 Schema
- 工具函数的 docstring 第一行作为 AI 描述

**记忆系统** ([src/agent/memory.py](src/agent/memory.py)):
- `MemoryManager`: JSON 文件存储对话历史 (`~/.pulao/history.json`)
- `VectorMemory`: ChromaDB 向量存储，支持 RAG 检索
- `EmbeddingService`: 使用 OpenAI embedding API 生成向量

**配置系统** ([src/core/config.py](src/core/config.py)):
- 多 Provider 支持: `providers: {name: {api_key, base_url, model}}`
- 配置合并: 全局配置 + 用户配置，用户优先
- 自动迁移旧版扁平配置到新版嵌套结构

## 开发命令

```bash
# 运行 CLI
python -m src.main

# 运行测试 (包含覆盖率报告)
pytest -v --cov=src --cov-report=term-missing --cov-report=html

# 运行单个测试文件
pytest tests/tools/test_registry.py -v

# 运行单个测试用例
pytest tests/tools/test_registry.py::TestToolRegistry::test_register_and_get_tool -v

# 代码质量检查
flake8 src/ tests/
bandit -r src/

# 类型检查 (可选)
mypy src/
```

## 项目结构约定

```
pulao/
├── src/
│   ├── agent/          # LangGraph 状态机、会话管理、记忆
│   ├── core/           # 配置、UI、日志、国际化
│   ├── tools/          # 工具注册表 (Docker/集群/安全/系统)
│   └── main.py         # CLI 入口
├── tests/              # Pytest 测试
└── install.sh          # 安装脚本
```

## 代码规范

- **代码风格**: PEP 8 + Flake8
- **类型注解**: 函数参数和返回值必须使用类型注解
- **文档字符串**: 所有工具函数必须包含 docstring（第一行作为 AI 描述）
- **提交信息**: Conventional Commits (feat/fix/refactor/test/chore/docs)
- **分支模型**: GitFlow (main=生产, develop=开发)
- **测试要求**: 新功能必带单元测试，目标覆盖率 100%

## 工具开发

添加新工具时，在 `src/tools/` 相应模块中定义函数，然后使用 `@registry.register` 装饰器注册：

```python
@registry.register
def my_tool(param: str, optional: int = 10) -> str:
    """
    工具描述 (AI 会看到这个)

    参数说明可以写在这里，AI 会自动从签名推断
    """
    # 实现逻辑
    return "result"
```

重要：工具函数的 docstring 第一行会被提取为 AI 描述，必须清晰简洁。

## 常见问题

**LangGraph 消息格式**:
- `HumanMessage`: 用户消息
- `AIMessage`: AI 响应，可能包含 `tool_calls`
- `ToolMessage`: 工具执行结果，包含 `tool_call_id`

**对话历史持久化**:
- 每次添加消息后自动调用 `session.save()`
- 系统提示词在每次请求时动态更新（包含最新系统信息）

**模板库位置**:
- 本地模板: `~/.pulao/templates/`
- 可用 `update_template_library` 工具更新

---

最后更新: 2026-03-30 | 版本: v1.3.0
