"""
部署回滚模块

实现部署状态快照和自动回滚机制。

核心功能：
1. 部署前自动创建状态快照
2. 部署失败自动触发回滚
3. 回滚操作审计日志
4. 手动回滚支持

快照内容：
- 容器配置（镜像、环境变量、挂载点、端口映射）
- docker-compose.yml 文件备份
- 时间戳和部署 ID
"""

import json
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field

from src.core.logger import logger
from src.core.config import CONFIG_DIR
from src.core.audit import AuditLogger


# 快照存储目录
SNAPSHOT_DIR = CONFIG_DIR / "snapshots"


@dataclass
class ContainerSnapshot:
    """容器快照"""
    name: str
    image: str
    status: str
    env: List[str] = field(default_factory=list)
    mounts: List[Dict] = field(default_factory=list)
    ports: List[Dict] = field(default_factory=list)
    networks: List[str] = field(default_factory=list)


@dataclass
class DeploymentSnapshot:
    """部署快照"""
    id: str                          # 快照 ID
    project_name: str                # 项目名称
    created_at: str                  # 创建时间
    compose_file: str                # docker-compose.yml 备份
    containers: List[ContainerSnapshot] = field(default_factory=list)
    rollback_performed: bool = False
    rollback_at: Optional[str] = None


class RollbackManager:
    """
    回滚管理器

    管理部署快照和回滚操作。
    """

    def __init__(self):
        """初始化回滚管理器"""
        self.snapshot_dir = SNAPSHOT_DIR
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.audit_logger = AuditLogger()

    def create_snapshot(self, project_name: str, compose_file: str) -> str:
        """
        创建部署前快照

        参数:
            project_name: 项目名称
            compose_file: docker-compose.yml 内容

        返回:
            快照 ID
        """
        import uuid

        snapshot_id = f"{project_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        # 获取当前容器状态
        containers = self._capture_containers(project_name)

        snapshot = DeploymentSnapshot(
            id=snapshot_id,
            project_name=project_name,
            created_at=datetime.now().isoformat(),
            compose_file=compose_file,
            containers=containers
        )

        # 保存快照
        snapshot_path = self.snapshot_dir / f"{snapshot_id}.json"
        with open(snapshot_path, "w", encoding="utf-8") as f:
            json.dump(asdict(snapshot), f, ensure_ascii=False, indent=2)

        logger.info(f"Created deployment snapshot: {snapshot_id}")

        # 审计日志
        self.audit_logger.log(
            action="snapshot_create",
            resource=project_name,
            details={"snapshot_id": snapshot_id, "container_count": len(containers)}
        )

        return snapshot_id

    def rollback(self, snapshot_id: str) -> bool:
        """
        从快照回滚

        参数:
            snapshot_id: 快照 ID

        返回:
            回滚是否成功
        """
        snapshot_path = self.snapshot_dir / f"{snapshot_id}.json"

        if not snapshot_path.exists():
            logger.error(f"Snapshot not found: {snapshot_id}")
            return False

        # 加载快照
        with open(snapshot_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        snapshot = DeploymentSnapshot(
            id=data["id"],
            project_name=data["project_name"],
            created_at=data["created_at"],
            compose_file=data["compose_file"],
            containers=[ContainerSnapshot(**c) for c in data.get("containers", [])],
            rollback_performed=data.get("rollback_performed", False),
            rollback_at=data.get("rollback_at")
        )

        if snapshot.rollback_performed:
            logger.warning(f"Snapshot already used for rollback: {snapshot_id}")
            return False

        logger.info(f"Starting rollback from snapshot: {snapshot_id}")

        try:
            # 步骤1: 停止当前容器
            self._stop_project(snapshot.project_name)

            # 步骤2: 恢复 docker-compose.yml
            self._restore_compose_file(snapshot.project_name, snapshot.compose_file)

            # 步骤3: 重新启动服务
            success = self._restart_project(snapshot.project_name)

            if success:
                # 更新快照状态
                snapshot.rollback_performed = True
                snapshot.rollback_at = datetime.now().isoformat()
                with open(snapshot_path, "w", encoding="utf-8") as f:
                    json.dump(asdict(snapshot), f, ensure_ascii=False, indent=2)

                logger.info(f"Rollback completed: {snapshot_id}")

                # 审计日志
                self.audit_logger.log(
                    action="rollback_execute",
                    resource=snapshot.project_name,
                    details={
                        "snapshot_id": snapshot_id,
                        "success": True,
                        "container_count": len(snapshot.containers)
                    }
                )

            return success

        except Exception as e:
            logger.error(f"Rollback failed: {e}")

            # 审计日志
            self.audit_logger.log(
                action="rollback_execute",
                resource=snapshot.project_name,
                details={
                    "snapshot_id": snapshot_id,
                    "success": False,
                    "error": str(e)
                }
            )

            return False

    def list_snapshots(self, project_name: str = None) -> List[Dict]:
        """
        列出快照

        参数:
            project_name: 可选，过滤项目名称

        返回:
            快照信息列表
        """
        snapshots = []

        for snapshot_file in self.snapshot_dir.glob("*.json"):
            try:
                with open(snapshot_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if project_name and not data["project_name"].startswith(project_name):
                    continue

                snapshots.append({
                    "id": data["id"],
                    "project_name": data["project_name"],
                    "created_at": data["created_at"],
                    "container_count": len(data.get("containers", [])),
                    "rollback_performed": data.get("rollback_performed", False)
                })
            except Exception as e:
                logger.warning(f"Failed to read snapshot {snapshot_file}: {e}")

        # 按创建时间倒序
        snapshots.sort(key=lambda x: x["created_at"], reverse=True)
        return snapshots

    def get_snapshot(self, snapshot_id: str) -> Optional[DeploymentSnapshot]:
        """获取快照详情"""
        snapshot_path = self.snapshot_dir / f"{snapshot_id}.json"

        if not snapshot_path.exists():
            return None

        with open(snapshot_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return DeploymentSnapshot(
            id=data["id"],
            project_name=data["project_name"],
            created_at=data["created_at"],
            compose_file=data["compose_file"],
            containers=[ContainerSnapshot(**c) for c in data.get("containers", [])],
            rollback_performed=data.get("rollback_performed", False),
            rollback_at=data.get("rollback_at")
        )

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """删除快照"""
        snapshot_path = self.snapshot_dir / f"{snapshot_id}.json"

        if not snapshot_path.exists():
            return False

        try:
            snapshot_path.unlink()
            logger.info(f"Deleted snapshot: {snapshot_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete snapshot: {e}")
            return False

    def cleanup_old_snapshots(self, max_age_days: int = 30, keep_count: int = 10):
        """
        清理旧快照

        参数:
            max_age_days: 最大保留天数
            keep_count: 每个项目最少保留的快照数
        """
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=max_age_days)
        cutoff_str = cutoff.isoformat()

        # 按项目分组
        project_snapshots = {}
        for snapshot in self.list_snapshots():
            proj = snapshot["project_name"]
            if proj not in project_snapshots:
                project_snapshots[proj] = []
            project_snapshots[proj].append(snapshot)

        deleted = 0
        for proj, snapshots in project_snapshots.items():
            # 保留最近的 N 个
            to_delete = snapshots[keep_count:]

            for snap in to_delete:
                if snap["created_at"] < cutoff_str and not snap["rollback_performed"]:
                    if self.delete_snapshot(snap["id"]):
                        deleted += 1

        logger.info(f"Cleaned up {deleted} old snapshots")

    def _capture_containers(self, project_name: str) -> List[ContainerSnapshot]:
        """捕获项目容器的当前状态"""
        containers = []

        try:
            # 获取项目容器列表
            cmd = ["docker", "compose", "-p", project_name, "ps", "-q"]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0 or not result.stdout.strip():
                return containers

            container_ids = result.stdout.strip().split("\n")

            for cid in container_ids:
                if not cid.strip():
                    continue

                # 获取容器详情
                inspect = self._inspect_container(cid.strip())
                if inspect:
                    containers.append(inspect)

        except Exception as e:
            logger.warning(f"Failed to capture containers: {e}")

        return containers

    def _inspect_container(self, container_id: str) -> Optional[ContainerSnapshot]:
        """获取容器详细信息"""
        try:
            cmd = ["docker", "inspect", container_id]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                return None

            data = json.loads(result.stdout)[0]
            config = data.get("Config", {})
            host_config = data.get("HostConfig", {})

            return ContainerSnapshot(
                name=data.get("Name", "").lstrip("/"),
                image=config.get("Image", ""),
                status=data.get("State", {}).get("Status", "unknown"),
                env=config.get("Env", []),
                mounts=[
                    {"source": m.get("Source"), "destination": m.get("Destination")}
                    for m in data.get("Mounts", [])
                ],
                ports=[
                    {"internal": p.get("PrivatePort"), "external": p.get("PublicPort")}
                    for p in config.get("ExposedPorts", {}).keys()
                ] if config.get("ExposedPorts") else [],
                networks=list(data.get("NetworkSettings", {}).get("Networks", {}).keys())
            )

        except Exception as e:
            logger.warning(f"Failed to inspect container {container_id}: {e}")
            return None

    def _stop_project(self, project_name: str):
        """停止项目容器"""
        from src.core.config import CONFIG_DIR
        deploy_dir = CONFIG_DIR / "deployments" / project_name

        if deploy_dir.exists():
            cmd = ["docker", "compose", "down"]
            subprocess.run(cmd, cwd=deploy_dir, capture_output=True, timeout=60)

    def _restore_compose_file(self, project_name: str, compose_content: str):
        """恢复 docker-compose.yml 文件"""
        from src.core.config import CONFIG_DIR
        deploy_dir = CONFIG_DIR / "deployments" / project_name
        deploy_dir.mkdir(parents=True, exist_ok=True)

        compose_path = deploy_dir / "docker-compose.yml"
        with open(compose_path, "w", encoding="utf-8") as f:
            f.write(compose_content)

        logger.info(f"Restored compose file for {project_name}")

    def _restart_project(self, project_name: str) -> bool:
        """重新启动项目"""
        from src.core.config import CONFIG_DIR
        deploy_dir = CONFIG_DIR / "deployments" / project_name

        if not deploy_dir.exists():
            return False

        cmd = ["docker", "compose", "up", "-d", "--remove-orphans"]
        result = subprocess.run(cmd, cwd=deploy_dir, capture_output=True, timeout=120)

        return result.returncode == 0


# 全局回滚管理器
_ROLLBACK_MANAGER: Optional[RollbackManager] = None


def get_rollback_manager() -> RollbackManager:
    """获取全局回滚管理器"""
    global _ROLLBACK_MANAGER
    if _ROLLBACK_MANAGER is None:
        _ROLLBACK_MANAGER = RollbackManager()
    return _ROLLBACK_MANAGER
