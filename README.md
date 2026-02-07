# Pulao: AI-Powered DevOps Assistant

Pulao 是一个基于 AI 的智能运维工具，旨在帮助运维人员通过自然语言完成 Docker 中间件的部署与管理。

## ✨ 特性 (Features)

*   **自然语言交互**: 只需要说 "部署一个高可用 Redis 集群"，剩下的交给 AI。
*   **一键安装**: 针对 Ubuntu 环境优化，自动配置 Docker 与 Python 环境。
*   **安全可控**: 生成配置后需人工确认，支持自定义 LLM API (OpenAI/Azure/Local)。
*   **美观易用**: 现代化的 CLI 界面。

## 🚀 快速开始 (Quick Start)

### 1. 获取代码与安装 (Download & Installation)

推荐使用以下的一键安装命令，它会自动下载并安装所有依赖（无需手动下载或安装 unzip）：

```bash
curl -fsSL https://raw.githubusercontent.com/lotusTanglei/pulao/main/install.sh | sudo bash
```

安装完成后，你可以使用 `ai-ops` 命令。

### 2. 配置 (Configuration)

首次使用前，请配置 LLM API 信息：

```bash
ai-ops config
```

你需要提供：
*   API Key
*   Base URL (例如 `https://api.openai.com/v1` 或中转地址)
*   Model Name (例如 `gpt-4o`)

### 3. 部署 (Deployment)

使用自然语言描述你的需求：

```bash
ai-ops deploy "部署一个 3 节点的 Redis 哨兵集群，密码设置为 123456"
```

AI 将生成 Docker Compose 配置文件，确认后自动部署。

## 🛠️ 开发指南 (Development)

```bash
# 安装依赖
pip install -r requirements.txt

# 运行
python -m src.main --help
```

## 📄 License

MIT
