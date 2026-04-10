"""
回滚操作工具模块

提供部署回滚相关的工具函数。
"""

from typing import List, Optional
from src.tools.registry import registry
from src.core.rollback import get_rollback_manager, DeploymentSnapshot
from src.core.logger import logger


@registry.register
def list_snapshots(project_name: str = None) -> str:
    """
    列出部署快照。

    参数:
        project_name: 可选，过滤指定项目的快照

    返回:
        快照列表信息
    """
    try:
        rollback_mgr = get_rollback_manager()
        snapshots = rollback_mgr.list_snapshots(project_name)

        if not snapshots:
            return "📭 暂无快照"

        output = [f"📋 快照列表 (共 {len(snapshots)} 个):\n"]

        for snap in snapshots:
            status = "✅" if not snap["rollback_performed"] else "🔄"
            output.append(
                f"{status} {snap['id']}\n"
                f"   项目: {snap['project_name']}\n"
                f"   创建: {snap['created_at']}\n"
                f"   容器数: {snap['container_count']}\n"
            )

        return "\n".join(output)

    except Exception as e:
        logger.error(f"Failed to list snapshots: {e}")
        return f"❌ 获取快照列表失败: {str(e)}"


@registry.register
def rollback_deployment(snapshot_id: str) -> str:
    """
    从快照回滚部署。

    将部署恢复到创建快照时的状态。

    参数:
        snapshot_id: 快照 ID（从 list_snapshots 获取）

    返回:
        回滚结果信息
    """
    try:
        rollback_mgr = get_rollback_manager()

        # 检查快照是否存在
        snapshot = rollback_mgr.get_snapshot(snapshot_id)
        if not snapshot:
            return f"❌ 快照不存在: {snapshot_id}"

        if snapshot.rollback_performed:
            return f"⚠️ 该快照已用于回滚，无法重复使用: {snapshot_id}"

        # 执行回滚
        logger.info(f"Starting rollback for snapshot: {snapshot_id}")
        success = rollback_mgr.rollback(snapshot_id)

        if success:
            return f"✅ 回滚成功: {snapshot.project_name} 已恢复到 {snapshot.created_at}"
        else:
            return f"❌ 回滚失败: 请检查日志获取详细错误信息"

    except Exception as e:
        logger.error(f"Failed to rollback: {e}")
        return f"❌ 回滚失败: {str(e)}"


@registry.register
def get_snapshot_info(snapshot_id: str) -> str:
    """
    获取快照详细信息。

    参数:
        snapshot_id: 快照 ID

    返回:
        快照详细信息
    """
    try:
        rollback_mgr = get_rollback_manager()
        snapshot = rollback_mgr.get_snapshot(snapshot_id)

        if not snapshot:
            return f"❌ 快照不存在: {snapshot_id}"

        output = [
            f"📦 快照详情:\n",
            f"ID: {snapshot.id}",
            f"项目: {snapshot.project_name}",
            f"创建时间: {snapshot.created_at}",
            f"容器数: {len(snapshot.containers)}",
            f"已回滚: {'是' if snapshot.rollback_performed else '否'}",
        ]

        if snapshot.rollback_at:
            output.append(f"回滚时间: {snapshot.rollback_at}")

        # 容器信息
        if snapshot.containers:
            output.append("\n📁 容器快照:")
            for c in snapshot.containers[:5]:  # 最多显示5个
                output.append(f"  - {c.name}: {c.image} ({c.status})")
            if len(snapshot.containers) > 5:
                output.append(f"  ... 还有 {len(snapshot.containers) - 5} 个容器")

        return "\n".join(output)

    except Exception as e:
        logger.error(f"Failed to get snapshot info: {e}")
        return f"❌ 获取快照信息失败: {str(e)}"


@registry.register
def delete_snapshot(snapshot_id: str) -> str:
    """
    删除快照。

    参数:
        snapshot_id: 快照 ID

    返回:
        删除结果
    """
    try:
        rollback_mgr = get_rollback_manager()
        success = rollback_mgr.delete_snapshot(snapshot_id)

        if success:
            return f"🗑️ 快照已删除: {snapshot_id}"
        else:
            return f"❌ 快照不存在或删除失败: {snapshot_id}"

    except Exception as e:
        logger.error(f"Failed to delete snapshot: {e}")
        return f"❌ 删除失败: {str(e)}"


@registry.register
def cleanup_old_snapshots(days: int = 30, keep: int = 10) -> str:
    """
    清理旧快照。

    删除超过指定天数的快照（每个项目保留最近 N 个）。

    参数:
        days: 保留天数（默认30天）
        keep: 每个项目最少保留的快照数（默认10个）

    返回:
        清理结果
    """
    try:
        rollback_mgr = get_rollback_manager()
        rollback_mgr.cleanup_old_snapshots(max_age_days=days, keep_count=keep)

        return f"🧹 已清理超过 {days} 天的旧快照（每个项目保留最近 {keep} 个）"

    except Exception as e:
        logger.error(f"Failed to cleanup snapshots: {e}")
        return f"❌ 清理失败: {str(e)}"
