# Pulao 项目能力矩阵文档

本文档全面展示 Pulao 项目当前具备的所有能力，帮助用户和开发者快速了解系统的功能边界和应用场景。

---

## 一、项目概述

**Pulao** 是一个 AI 驱动的智能运维助手，通过自然语言交互帮助运维人员完成 Docker 部署、系统运维、安全审计、知识管理和 GitOps 工作流。

**项目版本**: 1.1.0  
**核心定位**: DevOps + AI Agent + GitOps

---

## 二、能力矩阵总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Pulao 能力矩阵总览                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐     │
│  │  部署能力   │   │  运维能力   │   │  安全能力   │   │  知识能力   │     │
│  │  ★★★★★    │   │  ★★★★★    │   │  ★★★★☆    │   │  ★★★★☆    │     │
│  └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘     │
│                                                                             │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐                         │
│  │  环境能力   │   │  集群能力   │   │  AI 能力    │                         │
│  │  ★★★★☆    │   │  ★★★★☆    │   │  ★★★★★    │                         │
│  └─────────────┘   └─────────────┘   └─────────────┘                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 三、详细能力矩阵

### 3.1 部署能力

| 能力项 | 功能描述 | 实现状态 | 工具函数 |
|-------|---------|---------|---------|
| **单机部署** | 在本机部署 Docker Compose 服务 | ✅ 完整实现 | `deploy_service` |
| **集群部署** | 在多个节点分布式部署服务 | ✅ 完整实现 | `deploy_cluster_service` |
| **模板库管理** | 从 GitHub 拉取预置模板 | ✅ 完整实现 | `update_template_library` |
| **服务回滚** | 停止并删除已部署的服务 | ✅ 完整实现 | `rollback_deploy` |
| **GitOps 部署** | 从 Git 仓库自动部署 | ✅ 完整实现 | `deploy_env` |

**使用示例**:
```
用户: "帮我部署一个 Redis"
AI: 调用 deploy_service() 生成 docker-compose.yml 并部署

用户: "在集群上部署 MySQL 主从"
AI: 调用 deploy_cluster_service() 在多节点部署
```

---

### 3.2 运维能力

| 能力项 | 功能描述 | 实现状态 | 工具函数 |
|-------|---------|---------|---------|
| **日志查看** | 获取容器运行日志 | ✅ 完整实现 | `get_logs` |
| **日志分析** | 自动分析日志中的错误和警告 | ✅ 完整实现 | `analyze_logs` |
| **容器状态检查** | 检查容器运行状态和健康检查 | ✅ 完整实现 | `check_container` |
| **容器列表** | 列出所有运行中的容器 | ✅ 完整实现 | `list_docker_containers` |
| **资源监控** | 查看 CPU、内存、磁盘使用情况 | ✅ 完整实现 | `system_status` |
| **磁盘检查** | 检查磁盘空间使用情况 | ✅ 完整实现 | `check_disk` |
| **端口检查** | 检查端口占用状态 | ✅ 完整实现 | `check_port` |
| **网络诊断** | 测试网络连通性 | ✅ 完整实现 | `check_network` |
| **DNS 解析** | 检查域名解析 | ✅ 完整实现 | `check_dns` |
| **综合诊断** | 对服务进行全面健康检查 | ✅ 完整实现 | `diagnose` |
| **容器重启** | 重启故障容器 | ✅ 完整实现 | `restart_docker_container` |
| **容器停止** | 停止运行中的容器 | ✅ 完整实现 | `stop_docker_container` |

**使用示例**:
```
用户: "Redis 容器启动不了，帮我排查"
AI: 
  1. 调用 diagnose("redis") 进行综合诊断
  2. 调用 get_logs("redis") 查看日志
  3. 分析问题并提供解决方案
  4. 建议保存案例到知识库
```

---

### 3.3 安全能力

| 能力项 | 功能描述 | 实现状态 | 工具函数 |
|-------|---------|---------|---------|
| **镜像漏洞扫描** | 使用 Trivy 扫描镜像漏洞 | ✅ 完整实现 | `scan_image` |
| **Docker 安全配置检查** | 检查 Docker 守护进程安全配置 | ✅ 完整实现 | `check_docker_security` |
| **敏感信息检测** | 检测文本中的密码、API Key 等 | ✅ 完整实现 | `detect_secrets` |
| **综合安全审计** | 执行全面安全检查 | ✅ 完整实现 | `security_audit` |

**使用示例**:
```
用户: "扫描 nginx:latest 镜像的漏洞"
AI: 调用 scan_image("nginx:latest")
    返回漏洞统计和修复建议

用户: "检查 Docker 安全配置"
AI: 调用 check_docker_security()
    返回安全配置检查报告
```

---

### 3.4 知识能力

| 能力项 | 功能描述 | 实现状态 | 工具函数 |
|-------|---------|---------|---------|
| **经验保存** | 保存部署经验到知识库 | ✅ 完整实现 | `save_experience` |
| **案例保存** | 保存故障排查案例 | ✅ 完整实现 | `save_case` |
| **知识搜索** | 语义搜索知识库 | ✅ 完整实现 | `search_kb` |
| **知识列表** | 列出知识库条目 | ✅ 完整实现 | `list_kb` |
| **知识统计** | 获取知识库统计信息 | ✅ 完整实现 | `kb_stats` |
| **知识导出** | 导出知识库为 Markdown | ✅ 完整实现 | `export_kb` |

**知识分类**:
- `deployment`: 部署方案
- `troubleshooting`: 故障排查
- `configuration`: 配置管理
- `best_practice`: 最佳实践
- `security`: 安全相关
- `other`: 其他

**使用示例**:
```
用户: "把这个部署方案保存下来"
AI: 调用 save_experience(title, content, category)
    返回保存确认

用户: "之前遇到过类似的 Redis 问题吗？"
AI: 调用 search_kb("Redis 问题")
    返回相关历史案例
```

---

### 3.5 环境能力（GitOps）

| 能力项 | 功能描述 | 实现状态 | 工具函数 |
|-------|---------|---------|---------|
| **GitOps 初始化** | 初始化 Git 仓库集成 | ✅ 完整实现 | `init_gitops` |
| **仓库克隆** | 克隆 Git 仓库 | ✅ 完整实现 | `clone_repo` |
| **更新拉取** | 拉取远程更新 | ✅ 完整实现 | `pull_updates` |
| **变更推送** | 推送本地变更 | ✅ 完整实现 | `push_changes` |
| **Git 状态** | 查看 Git 仓库状态 | ✅ 完整实现 | `git_status` |
| **环境创建** | 创建部署环境 | ✅ 完整实现 | `create_env` |
| **环境切换** | 切换当前环境 | ✅ 完整实现 | `switch_env` |
| **环境列表** | 列出所有环境 | ✅ 完整实现 | `list_envs` |
| **环境部署** | 部署到指定环境 | ✅ 完整实现 | `deploy_env` |
| **环境同步** | 从 Git 同步并部署 | ✅ 完整实现 | `sync_env` |
| **GitOps 状态** | 查看 GitOps 完整状态 | ✅ 完整实现 | `gitops_status` |
| **变更日志** | 查看配置变更历史 | ✅ 完整实现 | `view_changelog` |

**使用示例**:
```
用户: "初始化 GitOps，仓库地址是 https://github.com/org/configs.git"
AI: 调用 init_gitops(repo_url)
    返回初始化结果

用户: "创建开发环境 dev"
AI: 调用 create_env("dev", "develop")
    返回环境创建结果

用户: "同步开发环境"
AI: 调用 sync_env("dev")
    拉取最新配置并部署
```

---

### 3.6 集群能力

| 能力项 | 功能描述 | 实现状态 | 工具函数 |
|-------|---------|---------|---------|
| **集群创建** | 创建新的集群配置 | ✅ 完整实现 | `create_cluster` |
| **集群切换** | 切换当前操作的集群 | ✅ 完整实现 | `switch_cluster` |
| **集群列表** | 列出所有集群 | ✅ 完整实现 | `list_clusters` |
| **节点添加** | 向集群添加节点 | ✅ 完整实现 | `add_node` |
| **节点移除** | 从集群移除节点 | ✅ 完整实现 | `remove_node` |
| **节点列表** | 列出集群节点状态 | ✅ 完整实现 | `list_nodes` |
| **远程执行** | 通过 SSH 执行远程命令 | ✅ 完整实现 | `execute_command` (带 host 参数) |

**使用示例**:
```
用户: "创建一个名为 production 的集群"
AI: 调用 create_cluster("production")

用户: "添加节点 worker1，地址 192.168.1.11"
AI: 调用 add_node("worker1", "192.168.1.11", "root")
```

---

### 3.7 AI 能力

| 能力项 | 功能描述 | 实现状态 | 技术实现 |
|-------|---------|---------|---------|
| **自然语言理解** | 理解用户意图 | ✅ 完整实现 | OpenAI API / DeepSeek |
| **多轮对话** | 保持对话上下文 | ✅ 完整实现 | AISession + History |
| **工具调用** | 自主选择和调用工具 | ✅ 完整实现 | LangGraph ReAct Agent |
| **推理能力** | 多步骤推理规划 | ✅ 完整实现 | ReAct 循环 |
| **长期记忆** | RAG 向量检索 | ✅ 完整实现 | ChromaDB |
| **自我修正** | 根据结果调整策略 | ✅ 完整实现 | ReAct 循环 |
| **主动建议** | 主动提供优化建议 | ✅ 完整实现 | 提示词引导 |

---

## 四、工具函数完整列表

### 4.1 按类别统计

| 类别 | 工具数量 |
|------|---------|
| 部署工具 | 5 个 |
| 运维诊断工具 | 14 个 |
| 安全扫描工具 | 4 个 |
| 知识库工具 | 6 个 |
| GitOps 工具 | 12 个 |
| 集群管理工具 | 6 个 |
| **总计** | **47 个** |

### 4.2 完整工具列表

**部署工具**:
1. `deploy_service` - 单机部署
2. `deploy_cluster_service` - 集群部署
3. `update_template_library` - 更新模板库
4. `rollback_deploy` - 服务回滚
5. `deploy_env` - 环境部署

**运维诊断工具**:
1. `get_logs` - 获取容器日志
2. `check_container` - 检查容器状态
3. `list_docker_containers` - 列出容器
4. `system_status` - 系统资源状态
5. `check_disk` - 磁盘空间检查
6. `check_port` - 端口检查
7. `check_network` - 网络连通性测试
8. `check_dns` - DNS 解析检查
9. `diagnose` - 综合诊断
10. `restart_docker_container` - 重启容器
11. `stop_docker_container` - 停止容器
12. `execute_command` - 执行 Shell 命令
13. `get_container_stats` - 容器资源统计
14. `list_containers` - 列出容器（内部）

**安全扫描工具**:
1. `scan_image` - 镜像漏洞扫描
2. `check_docker_security` - Docker 安全配置检查
3. `detect_secrets` - 敏感信息检测
4. `security_audit` - 综合安全审计

**知识库工具**:
1. `save_experience` - 保存经验
2. `save_case` - 保存案例
3. `search_kb` - 搜索知识库
4. `list_kb` - 列出知识条目
5. `kb_stats` - 知识库统计
6. `export_kb` - 导出知识库

**GitOps 工具**:
1. `init_gitops` - 初始化 GitOps
2. `clone_repo` - 克隆仓库
3. `pull_updates` - 拉取更新
4. `push_changes` - 推送变更
5. `git_status` - Git 状态
6. `create_env` - 创建环境
7. `switch_env` - 切换环境
8. `list_envs` - 列出环境
9. `sync_env` - 同步环境
10. `gitops_status` - GitOps 状态
11. `view_changelog` - 变更日志
12. `init_git_repo` - 初始化 Git 仓库（内部）

**集群管理工具**:
1. `create_cluster` - 创建集群
2. `switch_cluster` - 切换集群
3. `list_clusters` - 列出集群
4. `add_node` - 添加节点
5. `remove_node` - 移除节点
6. `list_nodes` - 列出节点

---

## 五、数据存储结构

### 5.1 配置目录

```
~/.pulao/
├── config.yaml              # 主配置文件
├── history.json             # 对话历史
├── clusters.yaml            # 集群配置
├── chroma_db/               # 向量数据库
├── knowledge/               # 知识库
│   └── entries.json
├── gitops/                  # GitOps 配置
│   ├── git_config.json
│   ├── environments.json
│   ├── changelog.json
│   ├── repo/               # Git 仓库
│   └── environments/       # 环境配置
│       ├── dev/
│       ├── staging/
│       └── prod/
└── deployments/             # 部署目录
    ├── redis/
    │   └── docker-compose.yml
    └── mysql/
        └── docker-compose.yml
```

### 5.2 配置文件格式

**config.yaml**:
```yaml
current_provider: default
language: zh
providers:
  default:
    api_key: ""
    base_url: https://api.deepseek.com
    model: deepseek-reasoner
```

**clusters.yaml**:
```yaml
current_cluster: default
clusters:
  default:
    nodes: []
  production:
    nodes:
      - name: master
        host: 192.168.1.10
        user: root
        role: master
        key_path: ~/.ssh/id_rsa
        status: Online
```

---

## 六、典型使用场景

### 6.1 场景一：快速部署中间件

```
用户输入: "帮我部署一个 Redis 集群，3 个节点"

AI 处理流程:
1. 分析请求：部署 Redis，3 节点集群
2. 生成 docker-compose.yml 配置
3. 检查端口是否可用
4. 调用 deploy_cluster_service()
5. 返回部署结果
6. 建议保存部署经验到知识库
```

### 6.2 场景二：故障排查

```
用户输入: "MySQL 容器无法启动，帮我排查"

AI 处理流程:
1. 调用 diagnose("mysql") 进行综合诊断
2. 调用 get_logs("mysql") 查看日志
3. 分析错误原因
4. 提供修复建议
5. 执行修复操作（如需要）
6. 建议保存案例到知识库
```

### 6.3 场景三：安全审计

```
用户输入: "部署前帮我扫描镜像漏洞"

AI 处理流程:
1. 调用 scan_image() 扫描镜像
2. 分析漏洞严重程度
3. 提供修复建议
4. 建议使用更安全的镜像版本
```

### 6.4 场景四：GitOps 工作流

```
用户输入: "初始化 GitOps 并创建开发环境"

AI 处理流程:
1. 调用 init_gitops(repo_url)
2. 调用 create_env("dev", "develop")
3. 调用 sync_env("dev")
4. 返回环境状态
```

### 6.5 场景五：知识沉淀

```
用户输入: "把这个解决方案保存下来"

AI 处理流程:
1. 提取解决方案内容
2. 调用 save_case(title, problem, solution)
3. 确认保存成功
```

---

## 七、技术架构

### 7.1 核心技术栈

| 组件 | 技术 | 版本要求 |
|------|------|---------|
| 编程语言 | Python | 3.10+ |
| CLI 框架 | Typer | Latest |
| 终端美化 | Rich | Latest |
| AI 框架 | LangGraph | Latest |
| LLM SDK | OpenAI | Latest |
| 向量数据库 | ChromaDB | Latest |
| 容器运行时 | Docker | 20.10+ |
| 漏洞扫描 | Trivy | Latest (可选) |
| 版本控制 | Git | 2.0+ |

### 7.2 架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Pulao 系统架构                                     │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐
│   用户交互层     │
│   (main.py)      │
│                 │
│ • CLI 界面      │
│ • REPL 循环     │
│ • 命令解析      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│   AI 处理层      │────▶│  Agent 编排层   │
│   (ai.py)        │     │ (ai_agent.py)   │
│                 │     │                 │
│ • AISession     │     │ • LangGraph     │
│ • 消息管理       │     │ • ReAct 循环    │
│ • RAG 检索      │     │ • 工具节点      │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            工具执行层 (tools.py)                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐    │
│  │  部署工具   │   │  运维工具   │   │  安全工具   │   │  知识工具   │    │
│  └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘    │
│                                                                             │
│  ┌─────────────┐   ┌─────────────┐                                         │
│  │ GitOps 工具 │   │  集群工具   │                                         │
│  └─────────────┘   └─────────────┘                                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            支撑服务层                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│ • config.py      - 配置管理                                                 │
│ • memory.py      - 记忆管理                                                 │
│ • prompts.py     - 提示词管理                                               │
│ • logger.py      - 日志系统                                                 │
│ • i18n.py        - 国际化                                                   │
│ • docker_ops.py  - Docker 操作                                              │
│ • cluster.py     - 集群管理                                                 │
│ • remote_ops.py  - 远程操作                                                 │
│ • system_ops.py  - 系统操作                                                 │
│ • library_manager.py - 模板库                                               │
│ • ops_diagnostics.py - 运维诊断                                             │
│ • security_scan.py - 安全扫描                                               │
│ • knowledge_base.py - 知识库                                                │
│ • gitops.py      - GitOps 工作流                                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 八、未来扩展方向

### 8.1 短期规划

| 方向 | 描述 | 优先级 |
|------|------|--------|
| Web 界面 | 提供 Web UI 管理界面 | 中 |
| 监控集成 | Prometheus/Grafana 集成 | 中 |
| 告警系统 | 自动告警和响应 | 中 |

### 8.2 长期规划

| 方向 | 描述 | 优先级 |
|------|------|--------|
| Kubernetes 支持 | 扩展到 K8s 平台 | 低 |
| 云平台集成 | AWS/阿里云/腾讯云 | 低 |
| 多用户支持 | 企业级多租户 | 低 |

---

## 九、版本历史

| 版本 | 日期 | 主要更新 |
|------|------|---------|
| 1.0.0 | 2026-03-01 | 基础 AI Agent + Docker 部署 |
| 1.1.0 | 2026-03-09 | 新增运维诊断、安全扫描、知识库、GitOps |

---

*文档版本：1.0.0*  
*生成日期：2026-03-09*  
*项目版本：1.1.0*
