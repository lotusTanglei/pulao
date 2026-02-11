# Pulao: AI-Powered DevOps Assistant

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg) ![License](https://img.shields.io/badge/license-MIT-green.svg)

Pulao 是一个基于 AI 的智能运维工具，旨在帮助运维人员通过自然语言完成 Docker 中间件部署和系统日常运维。它不仅仅是一个简单的命令生成器，更是一个**懂模板、懂环境、安全可控**的运维伙伴。

## ✨ 核心特性 (Features)

*   **🧩 智能模板适配 (Smart Templates)**: 
    *   拒绝 AI 瞎编配置！Pulao 能够自动从 GitHub (awesome-compose) 拉取经过验证的官方模板。
    *   当你要求部署 "Redis" 时，AI 会基于官方最佳实践模板进行微调（如修改密码、端口），确保部署的稳定性和规范性。
    *   支持 `update-library` 命令一键更新本地模板库。

*   **🛡️ 环境感知 (Context Aware)**:
    *   在部署前自动扫描本机状态（运行中的容器、监听端口）。
    *   **智能冲突检测**：如果发现 Redis 已经在运行，AI 会主动警告并询问：“是否覆盖更新？” 而不是盲目执行。

*   **🧠 智能部署 (AI Deployment)**:
    *   只需要说 "部署一个高可用 Redis 集群"，AI 自动生成 Docker Compose 配置。
    *   支持**交互式命名**：在部署前确认项目名称（如 `my-redis-prod`），避免目录覆盖。
    *   多项目隔离管理，自动归档于 `~/.pulao/deployments/`。

*   **⚡ 本地 Shell 直通 (Direct Shell)**:
    *   无需退出 CLI，使用 `!` 前缀即可直接执行系统命令。
    *   示例：`!docker ps` 或 `!ls -la`。

*   **🛠️ 系统运维 (System Ops)**:
    *   支持自然语言执行复杂运维任务，如 "清理所有退出的容器"、"查看系统负载"。
    *   所有敏感操作执行前均需二次确认。

*   **🔄 多模型切换**: 支持配置多个 AI 提供商 (OpenAI, DeepSeek, Azure 等) 并快速切换。

## 🚀 快速开始 (Quick Start)

### 1. 安装 (Installation)

**一键安装 (推荐)**

GitHub (国际):
```bash
curl -L https://raw.githubusercontent.com/lotusTanglei/pulao/main/install.sh | bash
```

Gitee (国内加速):
```bash
curl -L https://gitee.com/LOTUStudio/pulao/raw/main/install.sh | bash
```

### 2. 基础使用 (Basic Usage)

安装完成后，直接输入 `pulao` 进入交互式 CLI：

```text
  ____        _             
 |  _ \ _   _| | __ _  ___  
 | |_) | | | | |/ _` |/ _ \   Version  : v1.0.0
 |  __/| |_| | | (_| | (_) |  Provider : deepseek
 |_|    \__,_|_|\__,_|\___/   Model    : deepseek-chat

Available Commands / 可用命令:
  • ! <command>           : Execute shell command (e.g., '!ls') / 执行系统命令
  • deploy <instruction>  : Deploy middleware / 部署中间件
  • update-library        : Update template library / 更新模板库
  • config                : Configure provider / 配置提供商
  • providers             : List providers / 列出提供商
  ...
```

### 3. 常用场景

#### 场景 A: 部署中间件 (基于模板)
```bash
> 部署一个 Redis，密码设置为 123456

[System] Using built-in template for: redis
[AI] 正在为您适配 Redis 官方模板...
[Plan] 生成配置如下...
[Confirm] 确认项目名称 (Project Name): my-redis
[Result] 部署成功！
```

#### 场景 B: 更新模板库
```bash
> update-library
Updating template library from https://github.com/docker/awesome-compose.git...
Library updated successfully!
```

#### 场景 C: 执行系统命令
```bash
> !docker ps
CONTAINER ID   IMAGE     PORTS
a1b2c3d4e5f6   redis     0.0.0.0:6379->6379/tcp
```

## 🎮 进阶功能 (Advanced Features)

### 1. 多模型管理 (Multi-Provider)

Pulao 支持配置多个 AI 模型并在它们之间快速切换。

```bash
# 添加新的提供商
> add-provider deepseek

# 切换提供商
> use deepseek
```

### 2. 提示词自定义 (Prompt Customization)

配置文件位于 `~/.pulao/prompts.yaml`。你可以修改此文件来定制 AI 的语气或澄清提问的规则。

## 🛠️ 开发指南 (Development)

```bash
# 1. 克隆项目
git clone https://gitee.com/LOTUStudio/pulao.git
cd pulao

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行
python -m src.main
```

## 📄 License

MIT
