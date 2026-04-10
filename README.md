# Pulao: AI-Powered DevOps Agent

![Version](https://img.shields.io/badge/version-1.3.0-blue.svg) ![License](https://img.shields.io/badge/license-MIT-green.svg) ![Build](https://img.shields.io/badge/build-passing-brightgreen.svg) ![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen.svg)

Pulao 是一个基于 AI 的智能运维 Agent，旨在帮助运维人员通过自然语言完成 Docker 中间件部署和系统日常运维。它不仅仅是一个简单的命令生成器，更是一个**懂模板、懂环境、安全可控**的运维伙伴。

在最新的 **v1.3.0** 版本中，Pulao 经历了深度的**领域驱动架构重构 (DDD)** 和**系统级性能优化**，引入了完整的自动化测试体系 (Pytest)，并进一步扩展了安全审计与自动化排障能力，进化为真正成熟的企业级 AI Agent。

## ✨ 核心特性 (Features)

*   **🤖 AI Agent 架构 (Powered by LangGraph)**:
    *   **LangGraph 驱动**: 采用 **LangGraph** 作为核心编排引擎，构建稳定、可控的基于状态机的 ReAct Agent。
    *   **智能循环**: 具备强大的“思考-行动-观察”循环能力，轻松处理复杂的多步运维任务（如“先检查端口占用，再部署服务”）。
    *   **自我修正**: 部署失败后，AI 会自动读取 `docker logs`，分析错误并尝试修正配置后重试。
    *   **记忆增强 (RAG)**: 引入 **向量数据库 (ChromaDB)** 实现长期记忆，Agent 能够自动复用历史成功的故障排查方案。

*   **🌐 多集群与环境管理 (Multi-Cluster)**:
    *   支持管理多个集群环境（如 `dev`, `prod`）。
    *   **节点管理**: 轻松添加、移除远程节点，支持 SSH 免密登录预检，确保部署原子性。
    *   **分布式部署**: 一句指令即可将配置分发至多个节点并分别拉起服务，构建高可用集群。

*   **🛡️ 运维诊断与安全合规 (Diagnostics & Security)**:
    *   **安全审计**: 具备镜像漏洞扫描和细粒度的权限控制能力。
    *   **环境预检**: 执行破坏性操作或集群部署前，强制进行环境状态与连通性预检。
    *   **人工确认**: 关键操作（如 `docker compose up`, `rm`）必须经过用户二次确认。

*   **🧩 智能模板适配 (Smart Templates)**: 
    *   拒绝 AI 瞎编配置！自动从 GitHub (awesome-compose) 拉取经过验证的官方模板作为生成参考。
    *   基于官方最佳实践模板进行智能微调（修改密码、端口等），确保部署稳定合规。

*   **⚡ 性能与工程质量 (Performance & Quality)**:
    *   **领域驱动重构**: `src/` 目录按照 Agent、Core、Tools 进行解耦设计，代码结构清晰。
    *   **自动化测试**: 引入完整的 `pytest` 自动化测试套件，全面覆盖核心编排逻辑与工具调用，保障功能迭代的稳定性。
    *   **性能调优**: 经过深度的静态分析与性能分析，优化了响应时间、资源调度与并发处理能力。

## 🚀 快速开始 (Quick Start)

### 1. 安装 (Installation)

**一键安装 (推荐)**

```bash
curl -L https://raw.githubusercontent.com/lotusTanglei/pulao/main/install.sh | bash
```

### 2. 基础使用 (Basic Usage)

安装完成后，直接输入 `pulao` 进入交互式 CLI：

```text
  ____        _             
 |  _ \ _   _| | __ _  ___  
 | |_) | | | | |/ _` |/ _ \   Version  : v1.3.0
 |  __/| |_| | | (_| | (_) |  Provider : deepseek
 |_|    \__,_|_|\__,_|\___/   Model    : deepseek-reasoner

Available Commands / 可用命令:
  • <natural language>    : Ask AI to deploy, manage clusters, or check system status
  • ! <command>           : Execute shell command directly / 直接执行 Shell 命令
  • config / setup        : Configure AI provider / 配置 AI
  • providers             : List AI providers / 列出提供商
  • use <provider>        : Switch AI provider / 切换提供商
  • exit / quit           : Exit / 退出
```

### 3. 常用场景

#### 场景 A: 智能部署与自我修正
```bash
> 帮我在 8080 端口部署一个 Nginx，如果端口被占用就用 8081

[AI] 收到。我先检查 8080 端口占用情况。
[Tool] Executing: check_port(8080)
[Tool] Result: Port 8080 is in use.
[AI] 8080 端口被占用。我将尝试使用 8081 端口部署 Nginx。
[Tool] Executing: deploy_service(nginx, port=8081)
[Result] 部署成功！访问地址: http://localhost:8081
```

#### 场景 B: 集群管理与环境预检
```bash
> 创建生产环境集群并在两台机器上部署服务

[AI] 正在添加节点 worker1...
[Tool] Executing: add_node(worker1, 192.168.1.10) -> 预检 SSH 连通性通过。
[AI] 正在规划双节点部署方案...
[Confirm] 确认在两台节点上执行部署操作？ (y/n) y
[Result] 集群部署完成。
```

## 🛠️ 配置说明 (Configuration)

配置文件位于 `~/.pulao/config.yaml`。

```yaml
api_key: "sk-..."
base_url: "https://api.deepseek.com"
model: "deepseek-reasoner"
language: "zh"  # en / zh
```

## 🛠️ 核心开发技术栈 (Tech Stack)

*   **语言**: Python 3.10+
*   **AI 编排**: LangGraph, LangChain
*   **向量记忆**: ChromaDB
*   **CLI 界面**: Typer, Rich, prompt_toolkit
*   **质量保障**: Pytest, Flake8, Radon, Bandit

## 📄 License

MIT
