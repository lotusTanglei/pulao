# Pulao 未来发展路线图 (Roadmap)

> 核心原则：做减法，聚焦运维痛点。不堆砌伪需求。

## 近期计划 (Next Sprint)
**代号：运维深度补全**

1. **实现 `ops_diagnostics.py` (高优)**
   * **目标**：让 AI 具备排障能力。
   * **功能**：新增 `get_container_logs(name)` 和 `get_system_status()` 工具。
   * **验收**：当服务启动失败时，AI 能自动调用日志工具，并指出具体报错原因（如：配置文件缩进错误）。

2. **强化部署预检机制 (中优)**
   * **目标**：降低部署失败率。
   * **功能**：在生成 YAML 之后，执行 `docker compose up` 之前，强制 Agent 调用 `check_port_available` 等检查工具。
   * **实现方式**：在 LangGraph 中增加一个 `verify_environment` 的前置节点。

## 中期计划 (Next Quarter)
**代号：安全与合规**

1. **镜像安全扫描 (`security_scan.py`)**
   * **目标**：企业级安全准入。
   * **功能**：集成 Trivy 或类似工具，AI 选用镜像时必须先过扫描。

2. **操作快照与回滚机制**
   * **目标**：提供后悔药。
   * **功能**：每次部署前备份原有目录，支持“撤销刚才的部署”自然语言指令。

## 远期愿景 (Future)
* **多 Agent 协作网络**：将单一 Agent 拆分为 "Planner(架构师)"、"Executor(运维)"、"Reviewer(安全专家)"，在 LangGraph 中形成多节点辩论机制。
* **Web 控制台**：提供可视化拓扑图和审批流界面。