# Pulao: AI-Powered DevOps Agent

![Version](https://img.shields.io/badge/version-1.1.0-blue.svg) ![License](https://img.shields.io/badge/license-MIT-green.svg)

Pulao 是一个基于 AI 的智能运维 Agent，旨在帮助运维人员通过自然语言完成 Docker 中间件部署和系统日常运维。它不仅仅是一个简单的命令生成器，更是一个**懂模板、懂环境、安全可控**的运维伙伴。

从 v1.1.0 开始，Pulao 已进化为真正的 **AI Agent**，具备多步推理、工具调用和持久化记忆能力。

## ✨ 核心特性 (Features)

*   **🤖 AI Agent 架构 (New)**:
    *   **ReAct 循环**: AI 能够进行“思考-行动-观察”的循环，处理复杂的多步任务（如“先检查端口占用，再部署服务”）。
    *   **自我修正**: 如果部署失败，AI 会分析错误日志，自动尝试修复配置并重试。
    *   **记忆增强 (RAG)**: 引入 **向量数据库 (ChromaDB)** 实现长期记忆。
        *   **经验复用**: Agent 会自动记住成功的故障排查方案，下次遇到相同问题时直接引用。
        *   **上下文持久化**: 你的对话历史会被完整保存，重启 CLI 后 AI 依然记得之前的上下文。

*   **🌐 多集群管理 (Multi-Cluster)**:
    *   支持管理多个集群环境（如 `dev`, `prod`）。
    *   **节点管理**: 轻松添加、移除远程节点，支持 SSH 免密登录检测。
    *   **分布式部署**: 一句指令即可在多个节点上部署高可用集群（如 Redis Sentinel, K8s 等）。

*   **🧩 智能模板适配 (Smart Templates)**: 
    *   拒绝 AI 瞎编配置！Pulao 能够自动从 GitHub (awesome-compose) 拉取经过验证的官方模板。
    *   当你要求部署 "Redis" 时，AI 会基于官方最佳实践模板进行微调（如修改密码、端口），确保部署的稳定性和规范性。
    *   支持 `update-library` 命令一键更新本地模板库。

*   **🛡️ 安全可控 (Safe & Controlled)**:
    *   **预检机制**: 在执行任何破坏性操作前，AI 会先检查环境（如端口冲突、磁盘空间）。
    *   **人工确认**: 关键操作（如 `docker compose up`, `rm`）必须经过用户二次确认。
    *   **日志审计**: 所有操作记录在 `~/.pulao/pulao.log`，方便追溯。

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
 | |_) | | | | |/ _` |/ _ \   Version  : v1.1.0
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

#### 场景 A: 智能部署 (多步推理)
```bash
> 帮我在 8080 端口部署一个 Nginx，如果端口被占用就用 8081

[AI] 收到。我先检查 8080 端口占用情况。
[Tool] Executing: check_port(8080)
[Tool] Result: Port 8080 is in use.
[AI] 8080 端口被占用。我将尝试使用 8081 端口部署 Nginx。
[Tool] Executing: deploy_service(nginx, port=8081)
[Result] 部署成功！访问地址: http://localhost:8081
```

#### 场景 B: 集群管理 (全自然语言交互)
```bash
# 1. 创建生产环境
> 创建一个名为 production 的集群
[AI] 已为您创建集群 'production'。

# 2. 添加节点
> 添加两个节点：worker1 (192.168.1.10) 和 worker2 (192.168.1.11)，用户都是 root
[AI] 正在添加节点 worker1...
[Tool] Executing: add_node(worker1, 192.168.1.10, root)
[AI] 正在添加节点 worker2...
[Tool] Executing: add_node(worker2, 192.168.1.11, root)
[Result] 节点添加完成。

# 3. 部署高可用集群
> 在 worker1 和 worker2 上部署 Redis 主从集群
[AI] 正在规划双节点 Redis 部署方案...
[Confirm] 确认在 worker1 部署 Master，在 worker2 部署 Slave？ (y/n) y
[Result] 集群部署完成。
```

#### 场景 C: 长期记忆 (RAG)
```bash
# 1. 第一次遇到问题
> 部署一个 Redis，但是不要用默认密码
[AI] 好的，我会在 docker-compose.yml 中设置 REDIS_PASSWORD。
[Result] 部署成功。

# 2. 第二次遇到相似问题
> 再帮我部署一个 Redis
[AI] (检索到相关历史) 发现您之前部署 Redis 时偏好设置非默认密码。
[AI] 这次也为您自动配置了随机密码。
[Result] 部署成功。
```

## 🛠️ 配置说明 (Configuration)

配置文件位于 `~/.pulao/config.yaml`。

```yaml
api_key: "sk-..."
base_url: "https://api.deepseek.com"
model: "deepseek-reasoner"
language: "zh"  # en / zh
```

## 📄 License

MIT
