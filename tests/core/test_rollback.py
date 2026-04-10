"""
回滚模块测试
"""

import pytest
import json
import tempfile
import os
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from src.core.rollback import (
    RollbackManager,
    ContainerSnapshot,
    DeploymentSnapshot,
    get_rollback_manager
)


class TestContainerSnapshot:
    """测试 ContainerSnapshot 数据类"""

    def test_create_container_snapshot(self):
        """测试创建容器快照"""
        snapshot = ContainerSnapshot(
            name="test-container",
            image="nginx:latest",
            status="running",
            env=["KEY=value"],
            mounts=[{"source": "/host", "destination": "/container"}],
            ports=[{"internal": 80, "external": 8080}],
            networks=["default"]
        )

        assert snapshot.name == "test-container"
        assert snapshot.image == "nginx:latest"
        assert snapshot.status == "running"
        assert len(snapshot.env) == 1
        assert len(snapshot.mounts) == 1


class TestDeploymentSnapshot:
    """测试 DeploymentSnapshot 数据类"""

    def test_create_deployment_snapshot(self):
        """测试创建部署快照"""
        containers = [
            ContainerSnapshot(name="c1", image="img1", status="running")
        ]

        snapshot = DeploymentSnapshot(
            id="test-snapshot-123",
            project_name="test-project",
            created_at="2026-01-01T00:00:00",
            compose_file="version: '3'",
            containers=containers
        )

        assert snapshot.id == "test-snapshot-123"
        assert snapshot.project_name == "test-project"
        assert len(snapshot.containers) == 1
        assert snapshot.rollback_performed is False


class TestRollbackManager:
    """测试 RollbackManager 类"""

    @pytest.fixture
    def temp_dir(self, tmp_path):
        """创建临时目录"""
        return tmp_path

    @pytest.fixture
    def rollback_mgr(self, temp_dir):
        """创建 RollbackManager 实例"""
        with patch('src.core.rollback.SNAPSHOT_DIR', temp_dir / "snapshots"):
            with patch('src.core.rollback.AuditLogger'):
                mgr = RollbackManager()
                mgr.snapshot_dir = temp_dir / "snapshots"
                mgr.snapshot_dir.mkdir(parents=True, exist_ok=True)
                yield mgr

    def test_create_snapshot(self, rollback_mgr, temp_dir):
        """测试创建快照"""
        with patch.object(rollback_mgr, '_capture_containers', return_value=[]):
            snapshot_id = rollback_mgr.create_snapshot(
                project_name="test-project",
                compose_file="version: '3'"
            )

        assert snapshot_id is not None
        assert "test-project" in snapshot_id

        # 验证文件已创建
        snapshot_file = rollback_mgr.snapshot_dir / f"{snapshot_id}.json"
        assert snapshot_file.exists()

    def test_get_snapshot(self, rollback_mgr):
        """测试获取快照"""
        with patch.object(rollback_mgr, '_capture_containers', return_value=[]):
            snapshot_id = rollback_mgr.create_snapshot(
                project_name="test-project",
                compose_file="version: '3'"
            )

        snapshot = rollback_mgr.get_snapshot(snapshot_id)

        assert snapshot is not None
        assert snapshot.id == snapshot_id
        assert snapshot.project_name == "test-project"

    def test_get_nonexistent_snapshot(self, rollback_mgr):
        """测试获取不存在的快照"""
        snapshot = rollback_mgr.get_snapshot("nonexistent-id")
        assert snapshot is None

    def test_list_snapshots(self, rollback_mgr):
        """测试列出快照"""
        with patch.object(rollback_mgr, '_capture_containers', return_value=[]):
            rollback_mgr.create_snapshot("project-a", "version: '3'")
            rollback_mgr.create_snapshot("project-b", "version: '3'")

        snapshots = rollback_mgr.list_snapshots()

        assert len(snapshots) == 2

    def test_list_snapshots_filter_by_project(self, rollback_mgr):
        """测试按项目过滤快照"""
        with patch.object(rollback_mgr, '_capture_containers', return_value=[]):
            rollback_mgr.create_snapshot("project-a", "version: '3'")
            rollback_mgr.create_snapshot("project-b", "version: '3'")

        snapshots = rollback_mgr.list_snapshots(project_name="project-a")

        assert len(snapshots) == 1
        assert snapshots[0]["project_name"] == "project-a"

    def test_delete_snapshot(self, rollback_mgr):
        """测试删除快照"""
        with patch.object(rollback_mgr, '_capture_containers', return_value=[]):
            snapshot_id = rollback_mgr.create_snapshot("test", "version: '3'")

        success = rollback_mgr.delete_snapshot(snapshot_id)
        assert success is True

        # 验证文件已删除
        snapshot = rollback_mgr.get_snapshot(snapshot_id)
        assert snapshot is None

    def test_delete_nonexistent_snapshot(self, rollback_mgr):
        """测试删除不存在的快照"""
        success = rollback_mgr.delete_snapshot("nonexistent")
        assert success is False

    def test_rollback_updates_status(self, rollback_mgr):
        """测试回滚更新快照状态"""
        with patch.object(rollback_mgr, '_capture_containers', return_value=[]):
            snapshot_id = rollback_mgr.create_snapshot("test", "version: '3'")

        with patch.object(rollback_mgr, '_stop_project'):
            with patch.object(rollback_mgr, '_restore_compose_file'):
                with patch.object(rollback_mgr, '_restart_project', return_value=True):
                    success = rollback_mgr.rollback(snapshot_id)

        assert success is True

        # 验证状态已更新
        snapshot = rollback_mgr.get_snapshot(snapshot_id)
        assert snapshot.rollback_performed is True
        assert snapshot.rollback_at is not None

    def test_rollback_already_performed(self, rollback_mgr):
        """测试已回滚的快照不能再次回滚"""
        with patch.object(rollback_mgr, '_capture_containers', return_value=[]):
            snapshot_id = rollback_mgr.create_snapshot("test", "version: '3'")

        with patch.object(rollback_mgr, '_stop_project'):
            with patch.object(rollback_mgr, '_restore_compose_file'):
                with patch.object(rollback_mgr, '_restart_project', return_value=True):
                    # 第一次回滚
                    success1 = rollback_mgr.rollback(snapshot_id)
                    assert success1 is True

                    # 第二次回滚
                    success2 = rollback_mgr.rollback(snapshot_id)
                    assert success2 is False


class TestRollbackManagerSingleton:
    """测试单例模式"""

    def test_get_rollback_manager_singleton(self):
        """测试单例返回相同实例"""
        import src.core.rollback as rb
        rb._ROLLBACK_MANAGER = None

        with patch('src.core.rollback.SNAPSHOT_DIR'):
            with patch('src.core.rollback.AuditLogger'):
                mgr1 = get_rollback_manager()
                mgr2 = get_rollback_manager()

                assert mgr1 is mgr2


class TestContainerCapture:
    """测试容器捕获功能"""

    @pytest.fixture
    def rollback_mgr(self, tmp_path):
        """创建 RollbackManager 实例"""
        with patch('src.core.rollback.SNAPSHOT_DIR', tmp_path / "snapshots"):
            with patch('src.core.rollback.AuditLogger'):
                mgr = RollbackManager()
                mgr.snapshot_dir = tmp_path / "snapshots"
                mgr.snapshot_dir.mkdir(parents=True, exist_ok=True)
                yield mgr

    def test_capture_containers_empty(self, rollback_mgr):
        """测试无容器时捕获"""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=""
            )

            containers = rollback_mgr._capture_containers("test-project")
            assert containers == []

    def test_capture_containers_success(self, rollback_mgr):
        """测试成功捕获容器"""
        with patch('subprocess.run') as mock_run:
            # 第一次调用：获取容器列表
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="container123"),
                # 第二次调用：inspect 容器
                MagicMock(
                    returncode=0,
                    stdout=json.dumps([{
                        "Name": "/test-container",
                        "Config": {
                            "Image": "nginx:latest",
                            "Env": ["KEY=value"]
                        },
                        "State": {"Status": "running"},
                        "Mounts": [],
                        "NetworkSettings": {"Networks": {"default": {}}}
                    }])
                )
            ]

            containers = rollback_mgr._capture_containers("test-project")

            assert len(containers) == 1
            assert containers[0].name == "test-container"
            assert containers[0].image == "nginx:latest"

    def test_inspect_container_failure(self, rollback_mgr):
        """测试容器 inspect 失败"""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout=""
            )

            result = rollback_mgr._inspect_container("nonexistent")
            assert result is None
