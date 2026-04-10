"""
经验库工具模块

提供经验库管理的工具函数，供 AI Agent 调用。

工具列表：
- save_experience: 保存部署经验
- search_experience: 搜索经验库
- list_experiences: 列出经验
- export_experiences: 导出经验库
- import_experiences: 导入经验库
- experience_stats: 查看经验库统计
"""

from typing import List, Dict, Optional
from src.tools.registry import registry
from src.agent.memory import init_experience_library, Experience
from src.core.logger import logger


@registry.register
def save_experience(
    content: str,
    category: str = "deployment",
    tags: List[str] = None,
    service_name: str = "",
    confidence: float = 0.85
) -> str:
    """
    保存部署经验到经验库。

    将成功的部署经验、故障排查案例等保存到向量数据库，
    后续可通过语义搜索检索。

    参数:
        content: 经验内容（自然语言描述）
        category: 分类 (deployment/troubleshooting/security/config)
        tags: 标签列表，用于过滤
        service_name: 关联的服务名称
        confidence: 置信度 (0.0-1.0)

    返回:
        保存结果信息
    """
    try:
        lib = init_experience_library()

        if tags is None:
            tags = []

        exp_id = lib.save(
            content=content,
            category=category,
            tags=tags,
            service_name=service_name,
            confidence=confidence,
            source="user"
        )

        logger.info(f"Saved experience: {exp_id}")
        return f"✅ 经验已保存 (ID: {exp_id[:8]}...)"

    except Exception as e:
        logger.error(f"Failed to save experience: {e}")
        return f"❌ 保存失败: {str(e)}"


@registry.register
def search_experience(
    query: str,
    top_k: int = 5,
    category: str = None,
    tags: List[str] = None
) -> str:
    """
    语义搜索经验库。

    根据自然语言查询搜索相关经验，支持分类和标签过滤。

    参数:
        query: 查询文本
        top_k: 返回结果数量
        category: 可选的分类过滤
        tags: 可选的标签过滤

    返回:
        匹配的经验列表
    """
    try:
        lib = init_experience_library()

        results = lib.search(
            query=query,
            top_k=top_k,
            category=category,
            tags=tags
        )

        if not results:
            return "📭 未找到相关经验"

        output = [f"🔍 找到 {len(results)} 条相关经验:\n"]

        for i, exp in enumerate(results, 1):
            output.append(f"\n{i}. [{exp.category}] {exp.service_name or '通用'}")
            output.append(f"   {exp.content[:200]}{'...' if len(exp.content) > 200 else ''}")
            output.append(f"   标签: {', '.join(exp.tags) if exp.tags else '无'}")
            output.append(f"   置信度: {exp.confidence:.0%} | 使用: {exp.use_count}次")

        return "\n".join(output)

    except Exception as e:
        logger.error(f"Failed to search experience: {e}")
        return f"❌ 搜索失败: {str(e)}"


@registry.register
def list_experiences(
    category: str = None,
    source: str = None,
    limit: int = 20,
    offset: int = 0
) -> str:
    """
    列出经验库中的经验。

    支持分页和过滤。

    参数:
        category: 可选的分类过滤
        source: 可选的来源过滤 (builtin/user/imported)
        limit: 返回数量限制
        offset: 偏移量

    返回:
        经验列表
    """
    try:
        lib = init_experience_library()

        results = lib.list_all(
            limit=limit,
            offset=offset,
            category=category,
            source=source
        )

        if not results:
            return "📭 经验库为空"

        # 获取总数用于分页信息
        stats = lib.stats()
        total = stats.get("total", 0)

        output = [f"📋 经验列表 (共 {total} 条，显示 {len(results)} 条):\n"]

        for i, exp in enumerate(results, offset + 1):
            output.append(f"\n{i}. [{exp.category}] {exp.service_name or '通用'}")
            output.append(f"   ID: {exp.id[:8]}...")
            output.append(f"   {exp.content[:100]}{'...' if len(exp.content) > 100 else ''}")
            output.append(f"   来源: {exp.source} | 使用: {exp.use_count}次")

        return "\n".join(output)

    except Exception as e:
        logger.error(f"Failed to list experiences: {e}")
        return f"❌ 列表失败: {str(e)}"


@registry.register
def export_experiences(
    file_path: str = "",
    category: str = None
) -> str:
    """
    导出经验库到 JSON 文件。

    导出的文件可以分享给其他用户或导入到其他实例。

    参数:
        file_path: 导出文件路径（可选，默认为 ~/.pulao/experience_export.json）
        category: 可选，只导出指定分类

    返回:
        导出结果信息
    """
    try:
        lib = init_experience_library()

        if not file_path:
            from src.core.config import CONFIG_DIR
            file_path = str(CONFIG_DIR / "experience_export.json")

        categories = [category] if category else None
        count = lib.export_to_file(file_path, categories)

        return f"📤 已导出 {count} 条经验到: {file_path}"

    except Exception as e:
        logger.error(f"Failed to export experiences: {e}")
        return f"❌ 导出失败: {str(e)}"


@registry.register
def import_experiences(
    file_path: str,
    mode: str = "merge"
) -> str:
    """
    从 JSON 文件导入经验库。

    参数:
        file_path: 导入文件路径
        mode: 导入模式
            - merge: 合并（保留现有，添加新的）
            - overwrite: 覆盖（清空后导入）

    返回:
        导入结果信息
    """
    try:
        lib = init_experience_library()

        count = lib.import_from_file(file_path, mode)

        mode_desc = "合并" if mode == "merge" else "覆盖"
        return f"📥 已{mode_desc}导入 {count} 条经验"

    except Exception as e:
        logger.error(f"Failed to import experiences: {e}")
        return f"❌ 导入失败: {str(e)}"


@registry.register
def experience_stats() -> str:
    """
    查看经验库统计信息。

    返回:
        经验库统计信息（总数、分类分布、来源分布、热门标签）
    """
    try:
        lib = init_experience_library()
        stats = lib.stats()

        output = ["📊 经验库统计信息:\n"]
        output.append(f"总数: {stats.get('total', 0)} 条\n")

        # 分类分布
        by_category = stats.get("by_category", {})
        if by_category:
            output.append("\n📁 分类分布:")
            for cat, count in by_category.items():
                output.append(f"   - {cat}: {count}")

        # 来源分布
        by_source = stats.get("by_source", {})
        if by_source:
            output.append("\n📦 来源分布:")
            for src, count in by_source.items():
                output.append(f"   - {src}: {count}")

        # 热门标签
        top_tags = stats.get("top_tags", [])
        if top_tags:
            output.append("\n🏷️ 热门标签:")
            for tag, count in top_tags[:5]:
                output.append(f"   - {tag}: {count}")

        return "\n".join(output)

    except Exception as e:
        logger.error(f"Failed to get experience stats: {e}")
        return f"❌ 获取统计失败: {str(e)}"


@registry.register
def delete_experience(experience_id: str) -> str:
    """
    删除指定的经验。

    参数:
        experience_id: 经验 ID（可从 list_experiences 获取）

    返回:
        删除结果信息
    """
    try:
        lib = init_experience_library()

        # 尝试模糊匹配 ID
        all_exps = lib.list_all(limit=1000)
        matched = None
        for exp in all_exps:
            if exp.id.startswith(experience_id):
                matched = exp
                break

        if not matched:
            return f"❌ 未找到 ID 以 '{experience_id}' 开头的经验"

        lib.delete(matched.id)
        logger.info(f"Deleted experience: {matched.id}")

        return f"🗑️ 已删除经验: {matched.content[:50]}..."

    except Exception as e:
        logger.error(f"Failed to delete experience: {e}")
        return f"❌ 删除失败: {str(e)}"
