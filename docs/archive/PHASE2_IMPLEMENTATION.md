# Pulao 项目第二阶段功能实现文档

## 概述

本文档记录 Pulao 项目第二阶段的功能实现，主要包括：
1. 安全扫描能力（Trivy 镜像漏洞扫描、安全配置检查）
2. 知识库管理能力（知识沉淀、语义检索、导出分享）

---

## 一、新增模块

### 1.1 安全扫描模块 (security_scan.py)

**文件位置**: `src/security_scan.py`

**功能概述**:
- Docker 镜像漏洞扫描（集成 Trivy）
- Docker 安全配置检查
- 敏感信息检测
- 综合安全审计

**核心类和函数**:

| 类/函数 | 说明 |
|--------|------|
| `Vulnerability` | 漏洞信息数据类 |
| `SecurityScanResult` | 安全扫描结果数据类 |
| `check_trivy_installed()` | 检查 Trivy 是否已安装 |
| `install_trivy_guide()` | 返回 Trivy 安装指南 |
| `scan_image_with_trivy()` | 使用 Trivy 扫描镜像漏洞 |
| `parse_trivy_json_output()` | 解析 Trivy JSON 输出 |
| `format_scan_result()` | 格式化扫描结果 |
| `check_docker_security_config()` | 检查 Docker 安全配置 |
| `detect_sensitive_info()` | 检测文本中的敏感信息 |
| `comprehensive_security_check()` | 执行综合安全检查 |

**使用示例**:

```python
from src.security_scan import scan_image_with_trivy, format_scan_result

# 扫描镜像
result = scan_image_with_trivy("nginx:latest")

# 格式化输出
print(format_scan_result(result, show_details=True))
```

### 1.2 知识库模块 (knowledge_base.py)

**文件位置**: `src/knowledge_base.py`

**功能概述**:
- 运维知识沉淀（部署方案、故障案例）
- 语义检索（基于向量数据库）
- 知识分类和标签管理
- 知识导出和分享

**核心类和函数**:

| 类/函数 | 说明 |
|--------|------|
| `KnowledgeEntry` | 知识条目数据类 |
| `KnowledgeBase` | 知识库管理类 |
| `save_deployment_experience()` | 保存部署经验 |
| `save_troubleshooting_case()` | 保存故障排查案例 |
| `search_knowledge()` | 搜索知识库 |
| `list_knowledge()` | 列出知识条目 |
| `get_knowledge_stats()` | 获取知识库统计 |
| `export_knowledge()` | 导出知识库 |

**知识分类**:
- `deployment`: 部署方案
- `troubleshooting`: 故障排查
- `configuration`: 配置管理
- `best_practice`: 最佳实践
- `security`: 安全相关
- `other`: 其他

**使用示例**:

```python
from src.knowledge_base import get_knowledge_base, save_troubleshooting_case

# 保存故障案例
save_troubleshooting_case(
    title="Redis 连接超时问题",
    problem="Redis 容器启动后无法连接，报错 Connection refused",
    solution="检查发现是端口映射配置错误，修正后问题解决"
)

# 搜索知识
kb = get_knowledge_base()
results = kb.search("Redis 连接问题")
```

---

## 二、新增工具函数

### 2.1 安全扫描工具

| 工具名称 | 功能 | 参数 |
|---------|------|------|
| `scan_image` | 扫描 Docker 镜像漏洞 | `image_name`: 镜像名称 |
| `check_docker_security` | 检查 Docker 安全配置 | 无 |
| `detect_secrets` | 检测文本中的敏感信息 | `text`: 要检测的文本 |
| `security_audit` | 执行综合安全审计 | `image_name`: 可选镜像名称 |

### 2.2 知识库工具

| 工具名称 | 功能 | 参数 |
|---------|------|------|
| `save_experience` | 保存运维经验 | `title`, `content`, `category` |
| `save_case` | 保存故障排查案例 | `title`, `problem`, `solution` |
| `search_kb` | 搜索知识库 | `query`: 搜索关键词 |
| `list_kb` | 列出知识条目 | `category`: 可选分类过滤 |
| `kb_stats` | 获取知识库统计 | 无 |
| `export_kb` | 导出知识库 | `output_path`: 可选输出路径 |

---

## 三、AI 提示词更新

### 3.1 新增规则

**诊断规则 (diagnostics_rules)**:
- 用户报告问题时，先用 `diagnose` 进行综合检查
- 用 `get_logs` 查看日志定位错误
- 用 `check_container` 验证容器健康状态
- 根据发现的问题提供修复建议
- 问题解决后，主动建议用 `save_case` 保存案例

**安全规则 (security_rules)**:
- 部署新镜像前，建议用 `scan_image` 扫描漏洞
- 用 `check_docker_security` 进行配置审计
- 审查配置时用 `detect_secrets` 检测敏感信息
- 对发现的漏洞提供修复建议

**知识管理规则 (knowledge_rules)**:
- 部署成功后，建议用 `save_experience` 保存经验
- 问题解决后，建议用 `save_case` 保存案例
- 复杂操作前，用 `search_kb` 搜索相关知识
- 遇到类似问题时，主动推荐相关知识点

### 3.2 角色定义扩展

AI 角色从原来的"DevOps 专家"扩展为：
- 部署中间件（单机或多机集群）
- 系统运维和故障排查
- 安全扫描和审计
- 知识管理和经验分享

---

## 四、数据存储

### 4.1 知识库数据

**存储位置**: `~/.pulao/knowledge/entries.json`

**数据结构**:
```json
{
  "abc12345": {
    "id": "abc12345",
    "title": "Redis 连接超时问题",
    "content": "## 问题描述\n...\n\n## 解决方案\n...",
    "category": "troubleshooting",
    "tags": ["redis", "connection"],
    "created_at": "2026-03-09T10:00:00",
    "updated_at": "2026-03-09T10:00:00",
    "source": "user",
    "metadata": {}
  }
}
```

### 4.2 向量数据库

知识库条目同时存储到 ChromaDB 向量数据库，支持语义检索。

---

## 五、使用场景

### 5.1 安全扫描场景

**用户**: "帮我扫描 nginx:latest 镜像的漏洞"

**AI 行为**:
1. 调用 `scan_image("nginx:latest")`
2. 返回漏洞统计和详情
3. 提供修复建议

### 5.2 故障排查场景

**用户**: "Redis 容器启动不了，帮我排查"

**AI 行为**:
1. 调用 `diagnose("redis")` 进行综合诊断
2. 调用 `get_logs("redis")` 查看日志
3. 分析问题原因
4. 提供解决方案
5. 问题解决后，建议保存案例

### 5.3 知识沉淀场景

**用户**: "把这个部署方案保存下来"

**AI 行为**:
1. 调用 `save_experience(title, content, category)`
2. 返回保存确认

### 5.4 知识检索场景

**用户**: "之前遇到过类似的 Redis 问题吗？"

**AI 行为**:
1. 调用 `search_kb("Redis 问题")`
2. 返回相关历史案例
3. 推荐解决方案

---

## 六、依赖要求

### 6.1 必需依赖

- Python 3.10+
- Docker
- ChromaDB（向量数据库）

### 6.2 可选依赖

- **Trivy**: 镜像漏洞扫描（如未安装，系统会提示安装指南）

安装 Trivy:
```bash
# macOS
brew install trivy

# Ubuntu/Debian
sudo apt-get install trivy

# Docker
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:latest image <image_name>
```

---

## 七、测试验证

### 7.1 功能测试

```bash
# 启动 Pulao
python -m src.main

# 测试安全扫描
> 扫描 nginx:latest 镜像的漏洞

# 测试知识库
> 保存一个部署经验
> 搜索知识库
```

### 7.2 预期输出

**安全扫描输出示例**:
```
============================================================
镜像安全扫描报告: nginx:latest
============================================================

漏洞统计:
  总计: 5
  中危 (MEDIUM): 3
  低危 (LOW): 2

安全建议:
  [*] 存在中危漏洞，建议尽快修复

============================================================
```

**知识库搜索输出示例**:
```
找到 2 条相关知识:

[1] Redis 连接超时问题
    分类: troubleshooting
    相关度: high
    ID: abc12345
    内容摘要: Redis 容器启动后无法连接...

[2] MySQL 部署最佳实践
    分类: best_practice
    相关度: medium
    ID: def67890
    内容摘要: 生产环境 MySQL 部署建议...
```

---

## 八、后续规划

### 8.1 第三阶段计划

根据项目评估文档，第三阶段将实现：
- 多环境编排与 GitOps
- 或多平台扩展（Kubernetes/云平台）

### 8.2 改进方向

1. **安全扫描增强**:
   - 支持 CI/CD 集成
   - 自动化漏洞修复建议

2. **知识库增强**:
   - 支持团队协作
   - 知识图谱构建
   - 自动知识提取

---

*文档版本: 2.0.0*
*完成日期: 2026-03-09*
*项目版本: 1.2.0*
