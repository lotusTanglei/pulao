# Pulao v1.2.0 Test Cases (RAG & Long-term Memory)

## 0. 前置条件 (Prerequisites)
- [ ] 已安装 `chromadb` (通过 `pip install chromadb` 或 `install.sh`)
- [ ] `~/.pulao/config.yaml` 中配置了有效的 OpenAI/DeepSeek API Key
- [ ] `~/.pulao/chroma_db` 目录可写

---

## 1. 基础功能测试 (Basic Functionality)

### Case 1.1: 向量库初始化
**步骤**:
1. 启动 `pulao` CLI。
2. 观察终端日志或 `~/.pulao/pulao.log`。
**预期**:
- 日志中出现 `Initializing Vector Memory...`。
- `~/.pulao/chroma_db` 目录被创建。

### Case 1.2: Embedding 生成
**步骤**:
1. 在代码中手动调用 `EmbeddingService.get_embedding("test")` (或使用临时脚本)。
**预期**:
- 返回非空的 float 列表 (长度通常为 1536)。
- 第二次调用相同文本应命中缓存 (响应更快)。

---

## 2. 记忆存储测试 (Memory Storage)

### Case 2.1: 单轮对话记忆
**步骤**:
1. 输入指令: "部署一个 Nginx 到 8080 端口"。
2. 等待 AI 执行完成并返回 "部署成功"。
3. 退出 CLI。
**预期**:
- 日志中显示 `Saving interaction to vector memory...`。
- ChromaDB 中新增一条记录，Metadata 包含时间戳。

### Case 2.2: 错误案例记忆
**步骤**:
1. 输入指令: "部署一个不存在的服务 xxx"。
2. AI 尝试部署并报错。
**预期**:
- 交互记录仍被保存，Metadata 中标记结果摘要（包含错误信息）。

---

## 3. RAG 检索测试 (Retrieval Augmented Generation)

### Case 3.1: 经验复用 (Experience Replay)
**步骤**:
1. **第一次交互**: 输入 "部署 Redis，设置密码为 123456"。
2. 确认部署成功。
3. **第二次交互**: 输入 "再部署一个 Redis，端口 6380"。
**预期**:
- CLI 显示 `Found X relevant memories.` (灰色提示)。
- AI 的回复中提到参考了之前的配置（如设置密码），或者生成的 YAML 文件中自动带上了 `requirepass 123456`。

### Case 3.2: 语义搜索 (Semantic Search)
**步骤**:
1. **第一次交互**: "服务器负载很高怎么办？" -> AI 建议使用 `uptime` 和 `top`。
2. **第二次交互**: "感觉电脑变慢了" (换一种说法)。
**预期**:
- AI 能够检索到上次关于 "负载高" 的问答，并给出类似的建议。

---

## 4. 边界条件测试 (Edge Cases)

### Case 4.1: 无历史记录
**步骤**:
1. 清空 `~/.pulao/chroma_db`。
2. 启动 CLI，输入指令。
**预期**:
- 系统正常运行，不报错。
- `Found 0 relevant memories.`。

### Case 4.2: API 故障
**步骤**:
1. 断网或配置错误的 API Key。
2. 输入指令。
**预期**:
- Embedding 获取失败时，系统应降级处理（记录 Error Log 但不崩溃）。
- 对话继续进行，只是没有 RAG 增强。

### Case 4.3: 长文本处理
**步骤**:
1. 输入一段非常长的指令 (> 8192 tokens)。
**预期**:
- Embedding 服务自动截断或分片处理，不抛出 `BadRequestError`。
