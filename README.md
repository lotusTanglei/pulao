# Pulao: AI-Powered DevOps Assistant

Pulao 是一个基于 AI 的智能运维工具，旨在帮助运维人员通过自然语言完成 Docker 中间件的部署与管理。

## ✨ 特性 (Features)

*   **自然语言交互**: 只需要说 "部署一个高可用 Redis 集群"，剩下的交给 AI。
*   **一键安装**: 针对 Ubuntu 环境优化，自动配置 Docker 与 Python 环境。
*   **安全可控**: 生成配置后需人工确认，支持自定义 LLM API (OpenAI/Azure/Local)。
*   **美观易用**: 现代化的 CLI 界面。

## 🚀 快速开始 (Quick Start)

### 1. 获取代码与安装 (Download & Installation)

**方式一：一键安装 (Standard)**

```bash
# -L: 跟随重定向
# 如果没有反应，可能是因为网络问题或 404 错误，去掉 -s 参数查看详细信息
curl -L https://raw.githubusercontent.com/lotusTanglei/pulao/main/install.sh | bash
```
**方式二：手动下载 (Manual)**

```bash
# 1. 下载源码压缩包
curl -L -o pulao.zip https://github.com/lotusTanglei/pulao/archive/refs/heads/main.zip

# 2. 解压
unzip pulao.zip
cd pulao-main

# 3. 安装
chmod +x install.sh
sudo ./install.sh
```

安装完成后，你可以直接运行 `pulao` 命令进入交互模式。

### 2. 使用 (Usage)

直接输入 `pulao` 进入交互式 CLI：

```bash
$ pulao

Pulao AI-Ops - AI-Ops: Natural Language Middleware Deployment Tool
Type 'exit' or 'quit' to leave.

> 部署一个高可用的 Redis 哨兵集群
```

或者使用单次命令模式：

```bash
pulao deploy "部署一个 3 节点的 Redis 哨兵集群，密码设置为 123456"
```

### 3. 配置 (Configuration)

在交互模式下输入 `config` 或 `setup`，或者运行：

```bash
pulao config
```

你需要提供：
*   API Key
*   Base URL (例如 `https://api.openai.com/v1` 或中转地址)
*   Model Name (例如 `gpt-4o`)

## 🛠️ 开发指南 (Development)

```bash
# 安装依赖
pip install -r requirements.txt

# 运行
python -m src.main --help
```

## 📄 License

MIT
