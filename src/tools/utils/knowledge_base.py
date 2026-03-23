"""
知识库管理模块

本模块负责运维知识的沉淀、检索和管理，包括：
1. 部署方案保存
2. 故障案例记录
3. 最佳实践总结
4. 知识检索和推荐

主要功能：
    - 保存运维经验到知识库
    - 语义搜索相关知识
    - 自动推荐相似解决方案
    - 知识分类和标签管理
    - 知识导出和分享

依赖：
    - ChromaDB: 向量数据库
    - OpenAI Embeddings: 文本嵌入
"""

import json
import time
import uuid
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src.core.config import CONFIG_DIR
from src.core.logger import logger
from src.agent.memory import init_vector_memory

console = Console()

KNOWLEDGE_DIR = CONFIG_DIR / "knowledge"
KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class KnowledgeEntry:
    """知识条目数据类"""
    id: str
    title: str
    content: str
    category: str  # deployment, troubleshooting, configuration, best_practice
    tags: List[str]
    created_at: str
    updated_at: str
    source: str  # user, ai, auto
    metadata: Dict


class KnowledgeBase:
    """
    知识库管理类
    
    提供知识的增删改查和语义检索功能
    """
    
    CATEGORIES = [
        "deployment",       # 部署方案
        "troubleshooting",  # 故障排查
        "configuration",    # 配置管理
        "best_practice",    # 最佳实践
        "security",         # 安全相关
        "other"             # 其他
    ]
    
    def __init__(self):
        """初始化知识库"""
        self.knowledge_file = KNOWLEDGE_DIR / "entries.json"
        self.entries: Dict[str, KnowledgeEntry] = {}
        self._load_entries()
        self.vector_memory = None
        try:
            self.vector_memory = init_vector_memory()
        except Exception as e:
            logger.warning(f"Vector memory not available: {e}")
    
    def _load_entries(self):
        """从文件加载知识条目"""
        if self.knowledge_file.exists():
            try:
                with open(self.knowledge_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for entry_id, entry_data in data.items():
                        self.entries[entry_id] = KnowledgeEntry(**entry_data)
                logger.info(f"Loaded {len(self.entries)} knowledge entries")
            except Exception as e:
                logger.error(f"Failed to load knowledge entries: {e}")
    
    def _save_entries(self):
        """保存知识条目到文件"""
        try:
            data = {eid: asdict(entry) for eid, entry in self.entries.items()}
            with open(self.knowledge_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved {len(self.entries)} knowledge entries")
        except Exception as e:
            logger.error(f"Failed to save knowledge entries: {e}")
    
    def add_entry(
        self,
        title: str,
        content: str,
        category: str = "other",
        tags: List[str] = None,
        source: str = "user",
        metadata: Dict = None
    ) -> KnowledgeEntry:
        """
        添加知识条目
        
        参数:
            title: 标题
            content: 内容
            category: 分类
            tags: 标签列表
            source: 来源（user/ai/auto）
            metadata: 元数据
        
        返回:
            创建的知识条目
        """
        entry_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()
        
        entry = KnowledgeEntry(
            id=entry_id,
            title=title,
            content=content,
            category=category if category in self.CATEGORIES else "other",
            tags=tags or [],
            created_at=now,
            updated_at=now,
            source=source,
            metadata=metadata or {}
        )
        
        self.entries[entry_id] = entry
        self._save_entries()
        
        # 添加到向量数据库
        if self.vector_memory:
            try:
                text_for_embedding = f"{title}\n{content}"
                self.vector_memory.add_memory(
                    text_for_embedding,
                    metadata={
                        "type": "knowledge",
                        "entry_id": entry_id,
                        "category": category,
                        "tags": tags or []
                    }
                )
                logger.info(f"Added knowledge to vector memory: {entry_id}")
            except Exception as e:
                logger.warning(f"Failed to add to vector memory: {e}")
        
        return entry
    
    def update_entry(
        self,
        entry_id: str,
        title: str = None,
        content: str = None,
        category: str = None,
        tags: List[str] = None,
        metadata: Dict = None
    ) -> Optional[KnowledgeEntry]:
        """
        更新知识条目
        
        参数:
            entry_id: 条目ID
            title: 新标题（可选）
            content: 新内容（可选）
            category: 新分类（可选）
            tags: 新标签（可选）
            metadata: 新元数据（可选）
        
        返回:
            更新后的知识条目，如果不存在返回 None
        """
        if entry_id not in self.entries:
            return None
        
        entry = self.entries[entry_id]
        
        if title:
            entry.title = title
        if content:
            entry.content = content
        if category and category in self.CATEGORIES:
            entry.category = category
        if tags is not None:
            entry.tags = tags
        if metadata:
            entry.metadata.update(metadata)
        
        entry.updated_at = datetime.now().isoformat()
        
        self._save_entries()
        
        return entry
    
    def delete_entry(self, entry_id: str) -> bool:
        """
        删除知识条目
        
        参数:
            entry_id: 条目ID
        
        返回:
            True 如果删除成功
        """
        if entry_id in self.entries:
            del self.entries[entry_id]
            self._save_entries()
            return True
        return False
    
    def get_entry(self, entry_id: str) -> Optional[KnowledgeEntry]:
        """
        获取知识条目
        
        参数:
            entry_id: 条目ID
        
        返回:
            知识条目，如果不存在返回 None
        """
        return self.entries.get(entry_id)
    
    def list_entries(
        self,
        category: str = None,
        tag: str = None,
        limit: int = 20
    ) -> List[KnowledgeEntry]:
        """
        列出知识条目
        
        参数:
            category: 按分类过滤（可选）
            tag: 按标签过滤（可选）
            limit: 返回数量限制
        
        返回:
            知识条目列表
        """
        entries = list(self.entries.values())
        
        if category:
            entries = [e for e in entries if e.category == category]
        
        if tag:
            entries = [e for e in entries if tag in e.tags]
        
        # 按更新时间排序
        entries.sort(key=lambda x: x.updated_at, reverse=True)
        
        return entries[:limit]
    
    def search(self, query: str, limit: int = 5) -> List[Dict]:
        """
        语义搜索知识库
        
        参数:
            query: 查询文本
            limit: 返回数量限制
        
        返回:
            匹配的知识条目列表
        """
        results = []
        
        # 首先尝试向量搜索
        if self.vector_memory:
            try:
                vector_results = self.vector_memory.search_memory(query)
                if vector_results and vector_results.get('documents'):
                    documents = vector_results['documents'][0]
                    metadatas = vector_results.get('metadatas', [[]])[0]
                    
                    for doc, meta in zip(documents, metadatas or []):
                        entry_id = meta.get('entry_id') if meta else None
                        if entry_id and entry_id in self.entries:
                            entry = self.entries[entry_id]
                            results.append({
                                "entry": entry,
                                "relevance": "high",
                                "match_type": "semantic"
                            })
            except Exception as e:
                logger.warning(f"Vector search failed: {e}")
        
        # 关键词搜索作为补充
        query_lower = query.lower()
        for entry in self.entries.values():
            # 避免重复
            if any(r["entry"].id == entry.id for r in results):
                continue
            
            # 标题或内容包含关键词
            if query_lower in entry.title.lower() or query_lower in entry.content.lower():
                results.append({
                    "entry": entry,
                    "relevance": "medium",
                    "match_type": "keyword"
                })
            
            if len(results) >= limit:
                break
        
        return results[:limit]
    
    def get_stats(self) -> Dict:
        """
        获取知识库统计信息
        
        返回:
            统计信息字典
        """
        stats = {
            "total_entries": len(self.entries),
            "by_category": {},
            "by_source": {},
            "recent_entries": []
        }
        
        for entry in self.entries.values():
            # 按分类统计
            if entry.category not in stats["by_category"]:
                stats["by_category"][entry.category] = 0
            stats["by_category"][entry.category] += 1
            
            # 按来源统计
            if entry.source not in stats["by_source"]:
                stats["by_source"][entry.source] = 0
            stats["by_source"][entry.source] += 1
        
        # 最近条目
        recent = sorted(self.entries.values(), key=lambda x: x.updated_at, reverse=True)[:5]
        stats["recent_entries"] = [{"id": e.id, "title": e.title, "category": e.category} for e in recent]
        
        return stats
    
    def export_to_markdown(self, output_path: str = None) -> str:
        """
        导出知识库为 Markdown 格式
        
        参数:
            output_path: 输出文件路径（可选）
        
        返回:
            Markdown 内容字符串
        """
        lines = []
        lines.append("# 运维知识库\n")
        lines.append(f"导出时间: {datetime.now().isoformat()}\n")
        lines.append(f"条目总数: {len(self.entries)}\n")
        
        for category in self.CATEGORIES:
            entries = [e for e in self.entries.values() if e.category == category]
            if not entries:
                continue
            
            lines.append(f"\n## {category.upper()}\n")
            
            for entry in sorted(entries, key=lambda x: x.updated_at, reverse=True):
                lines.append(f"\n### {entry.title}\n")
                lines.append(f"- ID: {entry.id}")
                lines.append(f"- 标签: {', '.join(entry.tags) or '无'}")
                lines.append(f"- 来源: {entry.source}")
                lines.append(f"- 更新时间: {entry.updated_at}\n")
                lines.append(f"```\n{entry.content}\n```\n")
        
        content = "\n".join(lines)
        
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        return content


# ============ 便捷函数 ============

_knowledge_base = None


def get_knowledge_base() -> KnowledgeBase:
    """获取知识库单例"""
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = KnowledgeBase()
    return _knowledge_base


def save_deployment_experience(
    title: str,
    description: str,
    yaml_content: str = None,
    tags: List[str] = None
) -> str:
    """
    保存部署经验
    
    参数:
        title: 标题
        description: 描述
        yaml_content: YAML 配置（可选）
        tags: 标签列表
    
    返回:
        保存结果信息
    """
    kb = get_knowledge_base()
    
    content = description
    if yaml_content:
        content += f"\n\n配置文件:\n```yaml\n{yaml_content}\n```"
    
    entry = kb.add_entry(
        title=title,
        content=content,
        category="deployment",
        tags=tags or ["deployment"],
        source="user"
    )
    
    return f"部署经验已保存: {entry.title} (ID: {entry.id})"


def save_troubleshooting_case(
    title: str,
    problem: str,
    solution: str,
    tags: List[str] = None
) -> str:
    """
    保存故障排查案例
    
    参数:
        title: 标题
        problem: 问题描述
        solution: 解决方案
        tags: 标签列表
    
    返回:
        保存结果信息
    """
    kb = get_knowledge_base()
    
    content = f"## 问题描述\n{problem}\n\n## 解决方案\n{solution}"
    
    entry = kb.add_entry(
        title=title,
        content=content,
        category="troubleshooting",
        tags=tags or ["troubleshooting"],
        source="user"
    )
    
    return f"故障排查案例已保存: {entry.title} (ID: {entry.id})"


def search_knowledge(query: str, limit: int = 5) -> str:
    """
    搜索知识库
    
    参数:
        query: 查询文本
        limit: 返回数量限制
    
    返回:
        搜索结果字符串
    """
    kb = get_knowledge_base()
    results = kb.search(query, limit=limit)
    
    if not results:
        return "未找到相关知识条目"
    
    lines = [f"找到 {len(results)} 条相关知识:\n"]
    
    for i, result in enumerate(results, 1):
        entry = result["entry"]
        relevance = result["relevance"]
        
        lines.append(f"\n[{i}] {entry.title}")
        lines.append(f"    分类: {entry.category}")
        lines.append(f"    相关度: {relevance}")
        lines.append(f"    ID: {entry.id}")
        lines.append(f"    内容摘要: {entry.content[:200]}...")
    
    return "\n".join(lines)


def list_knowledge(category: str = None, limit: int = 20) -> str:
    """
    列出知识库条目
    
    参数:
        category: 分类过滤（可选）
        limit: 返回数量限制
    
    返回:
        条目列表字符串
    """
    kb = get_knowledge_base()
    entries = kb.list_entries(category=category, limit=limit)
    
    if not entries:
        return "知识库暂无条目"
    
    lines = [f"知识库条目 (共 {len(entries)} 条):\n"]
    
    for entry in entries:
        lines.append(f"  [{entry.id}] {entry.title}")
        lines.append(f"      分类: {entry.category}, 标签: {', '.join(entry.tags) or '无'}")
    
    return "\n".join(lines)


def get_knowledge_stats() -> str:
    """
    获取知识库统计信息
    
    返回:
        统计信息字符串
    """
    kb = get_knowledge_base()
    stats = kb.get_stats()
    
    lines = ["知识库统计信息:\n"]
    lines.append(f"  总条目数: {stats['total_entries']}")
    
    if stats['by_category']:
        lines.append("\n  按分类:")
        for cat, count in stats['by_category'].items():
            lines.append(f"    - {cat}: {count}")
    
    if stats['by_source']:
        lines.append("\n  按来源:")
        for source, count in stats['by_source'].items():
            lines.append(f"    - {source}: {count}")
    
    if stats['recent_entries']:
        lines.append("\n  最近条目:")
        for entry in stats['recent_entries']:
            lines.append(f"    - [{entry['id']}] {entry['title']}")
    
    return "\n".join(lines)


def export_knowledge(output_path: str = None) -> str:
    """
    导出知识库
    
    参数:
        output_path: 输出文件路径（可选）
    
    返回:
        导出结果信息
    """
    kb = get_knowledge_base()
    
    if not output_path:
        output_path = str(KNOWLEDGE_DIR / f"knowledge_export_{int(time.time())}.md")
    
    content = kb.export_to_markdown(output_path)
    
    return f"知识库已导出到: {output_path}\n共 {len(kb.entries)} 条记录"
