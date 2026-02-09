# Pulao: AI-Powered DevOps Assistant

Pulao 是一个基于 AI 的智能运维工具，旨在帮助运维人员通过自然语言完成 Docker 中间件部署和系统日常运维。它不仅仅是一个简单的命令生成器，更是一个懂你意图、安全可控的运维伙伴。

## ✨ 核心特性 (Features)

*   **🧠 智能部署**: 只需要说 "部署一个高可用 Redis 集群"，AI 自动生成 Docker Compose 配置。
*   **🛠️ 系统运维**: 支持自然语言执行 Shell 命令，如 "查看系统负载"、"清理 Docker 缓存"。
*   **🗣️ 交互式澄清**: 当需求模糊时（如仅说“安装 MySQL”），AI 会主动询问版本、密码等关键信息。
*   **🔄 多模型切换**: 支持配置多个 AI 提供商 (OpenAI, DeepSeek, Azure 等) 并快速切换。
*   **🎨 提示词管理**: 支持自定义 AI 的 System Prompt，定制专属的运维风格。
*   **⚡ 极速体验**: 针对国内网络环境优化 Docker 镜像加速，一键安装。

## 🚀 快速开始 (Quick Start)

### 1. 安装 (Installation)

**一键安装 (推荐)**

```bash
curl -L https://raw.githubusercontent.com/lotusTanglei/pulao/main/install.sh | bash
```

### 2. 基础使用 (Basic Usage)

安装完成后，直接输入 `pulao` 进入交互式 CLI：

```bash
$ pulao

Pulao AI-Ops - AI-Ops: Natural Language Middleware Deployment Tool
--------------------------------------------------
Available Commands / 可用命令:
  • deploy <instruction>: Deploy middleware (e.g., 'deploy redis') / 部署中间件
  • config or setup : Configure current provider / 配置当前提供商
  • providers          : List all providers / 列出所有提供商
  • use <name>          : Switch provider / 切换提供商
  • add-provider <name> : Add new provider / 添加提供商
  • exit or quit   : Exit Pulao / 退出
--------------------------------------------------

> 部署一个高可用的 Redis 哨兵集群
> 查看当前磁盘使用率
```

## 🎮 进阶功能 (Advanced Features)

### 1. 多模型管理 (Multi-Provider)

Pulao 支持配置多个 AI 模型（例如同时使用 OpenAI 和 DeepSeek），并在它们之间快速切换，方便对比效果或作为备用方案。

```bash
# 添加新的提供商
> add-provider deepseek

# 列出所有提供商
> providers
  1. default
  2. deepseek * (current)

# 切换提供商 (通过名称或编号)
> use 1
Switched to provider: default
```

### 2. 系统运维指令 (System Ops)

除了部署中间件，你还可以让 Pulao 帮你执行日常 Linux 运维任务。所有命令在执行前都会展示并要求确认，确保安全。

**示例指令：**
*   **查询**: "查看当前运行的 Docker 容器" -> `docker ps`
*   **清理**: "删除所有 Exited 状态的容器" -> `docker container prune -f`
*   **监控**: "查看最近 5 分钟的系统负载" -> `uptime`
*   **网络**: "查看 8080 端口被谁占用了" -> `lsof -i :8080`

### 3. 提示词自定义 (Prompt Customization)

Pulao 允许你自定义 AI 的行为规则。配置文件位于 `~/.pulao/prompts.yaml`。

你可以修改此文件来：
*   调整 AI 的语气或角色设定。
*   修改澄清提问的规则（例如强制要求询问特定参数）。
*   定制 Docker Compose 的生成模板要求。

**默认配置示例 (`~/.pulao/prompts.yaml`)**:
```yaml
clarification_rules:
  zh: |
    澄清提问规则:
    1. 你必须使用**中文**进行提问。
    2. 仅确认核心要素：软件版本、密码、持久化、端口。
...
```

## 🛠️ 开发指南 (Development)

```bash
# 1. 克隆项目
git clone https://github.com/lotusTanglei/pulao.git
cd pulao

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行
python -m src.main
```

## 📄 License

MIT
