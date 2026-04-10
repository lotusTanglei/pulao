"""
对话历史管理模块

本模块负责管理 AI 对话的历史记录，实现跨会话的记忆持久化。

主要功能：
1. 历史记录加载：从 JSON 文件读取对话历史
2. 历史记录保存：将对话历史写入 JSON 文件
3. 历史记录清除：删除历史记录文件

配置文件：~/.pulao/history.json

数据结构：
    - 历史记录存储为消息列表
    - 每条消息包含角色 (role) 和内容 (content)
    - 支持用户消息和 AI 消息

使用场景：
    - 保持对话上下文连贯性
    - 提供多轮对话支持
    - 会话恢复
"""

# ============ 标准库导入 ============
import json
import os
from pathlib import Path
from typing import List, Dict, Optional
import uuid

# ============ 第三方库导入 ============
import chromadb
import openai

# ============ 本地模块导入 ============
from src.core.logger import logger  # 日志记录
from src.core.config import CONFIG_DIR, load_config  # 配置目录


# ============ 历史文件路径 ============

# 对话历史文件路径
HISTORY_FILE = CONFIG_DIR / "history.json"


# ============ 记忆管理器类 ============

class MemoryManager:
    """
    对话历史管理器
    
    提供静态方法管理对话历史的持久化存储。
    历史记录以 JSON 格式保存在用户配置目录中。
    
    主要功能：
        - 加载历史记录
        - 保存历史记录
        - 清除历史记录
    """
    
    # ============ 历史记录加载方法 ============
    
    @staticmethod
    def load_history() -> List[Dict]:
        """
        加载对话历史记录
        
        从 JSON 文件读取对话历史。
        
        返回:
            消息列表，每条消息包含 role 和 content
        
        异常处理：
            - 文件不存在：返回空列表
            - 文件损坏：记录警告并返回空列表
            - 其他错误：记录错误并返回空列表
        """
        if not HISTORY_FILE.exists():
            return []
            
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
                # 验证数据类型
                if isinstance(history, list):
                    return history
                else:
                    logger.warning("History file corrupted (not a list), resetting.")
                    return []
        except Exception as e:
            logger.error(f"Failed to load history: {e}")
            return []

    # ============ 历史记录保存方法 ============
    
    @staticmethod
    def save_history(history: List[Dict]):
        """
        保存对话历史记录
        
        将对话历史写入 JSON 文件。
        
        参数:
            history: 消息列表
        
        存储格式：
            - JSON 格式
            - UTF-8 编码
            - 格式化缩进
        
        注意:
            - 会自动创建父目录
            - 会覆盖现有文件
        
        优化考虑：
            - 可以限制保存的消息数量防止文件无限增长
            - AISession 单独管理系统提示词
        """
        try:
            # 确保目录存在
            HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            
            # 写入历史记录
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save history: {e}")

    # ============ 历史记录清除方法 ============
    
    @staticmethod
    def clear_history():
        """
        清除对话历史记录
        
        删除历史记录文件。
        
        注意:
            - 如果文件不存在不会报错
            - 无法恢复，请谨慎使用
        """
        if HISTORY_FILE.exists():
            try:
                os.remove(HISTORY_FILE)
            except Exception as e:
                logger.error(f"Failed to clear history: {e}")


# ============ 向量记忆类 ============

class EmbeddingService:
    """
    嵌入向量服务
    
    负责将文本转换为向量。
    """
    
    def __init__(self):
        """
        初始化嵌入服务
        """
        config = load_config()
        # 优先使用配置中的 API Key
        self.client = openai.OpenAI(
            api_key=config.get("api_key", ""),
            base_url=config.get("base_url")
        )
        # 默认使用 text-embedding-3-small 模型
        self.model = "text-embedding-3-small"

    def get_embedding(self, text: str) -> List[float]:
        """
        获取文本的嵌入向量
        
        参数:
            text: 输入文本
            
        返回:
            嵌入向量列表
        """
        try:
            # 移除换行符以优化嵌入效果
            text = text.replace("\n", " ")
            response = self.client.embeddings.create(
                input=[text],
                model=self.model
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise


class VectorMemory:
    """
    向量记忆存储
    
    使用 ChromaDB 存储和检索文本向量。
    """
    
    def __init__(self):
        """
        初始化向量记忆
        
        - 初始化 ChromaDB 客户端
        - 获取或创建集合
        - 初始化嵌入服务
        """
        db_path = CONFIG_DIR / "chroma_db"
        try:
            self.client = chromadb.PersistentClient(path=str(db_path))
            # 获取或创建集合
            self.collection = self.client.get_or_create_collection(name="memory")
            self.embedding_service = EmbeddingService()
        except Exception as e:
            logger.error(f"Failed to initialize VectorMemory: {e}")
            raise

    def add_memory(self, text: str, metadata: Dict = None):
        """
        添加记忆
        
        生成嵌入并添加到 ChromaDB 集合。
        
        参数:
            text: 记忆文本
            metadata: 元数据字典
        """
        try:
            embedding = self.embedding_service.get_embedding(text)
            # 生成唯一 ID
            doc_id = str(uuid.uuid4())
            
            self.collection.add(
                documents=[text],
                embeddings=[embedding],
                metadatas=[metadata] if metadata else None,
                ids=[doc_id]
            )
            logger.info(f"Added memory: {text[:50]}...")
        except Exception as e:
            logger.error(f"Failed to add memory: {e}")
            raise

    def search_memory(self, query: str, n_results: int = 3) -> Dict:
        """
        搜索记忆
        
        根据查询生成嵌入并在 ChromaDB 中搜索最相似的记录。
        
        参数:
            query: 查询文本
            n_results: 返回结果数量
            
        返回:
            查询结果字典
        """
        try:
            embedding = self.embedding_service.get_embedding(query)
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=n_results
            )
            return results
        except Exception as e:
            logger.error(f"Failed to search memory: {e}")
            raise


# 全局向量记忆实例
_VECTOR_MEMORY: Optional[VectorMemory] = None


def init_vector_memory() -> VectorMemory:
    """
    初始化全局向量记忆实例

    返回:
        VectorMemory 实例
    """
    global _VECTOR_MEMORY
    if _VECTOR_MEMORY is None:
        _VECTOR_MEMORY = VectorMemory()
    return _VECTOR_MEMORY


# ============ 经验库模块 ============

from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import List as TypingList
import json


@dataclass
class Experience:
    """
    部署经验条目

    存储成功的部署经验、故障排查案例等知识。
    """
    id: str                                    # UUID
    content: str                               # 自然语言描述
    category: str                              # deployment/troubleshooting/security/config
    tags: TypingList[str] = field(default_factory=list)  # 标签，用于过滤
    service_name: str = ""                     # 关联服务名
    confidence: float = 0.85                   # AI 置信度
    created_at: str = ""                       # ISO 格式时间
    last_used: str = ""                        # ISO 格式时间
    use_count: int = 0                         # 使用次数（热度）
    source: str = "user"                       # builtin/user/imported

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.last_used:
            self.last_used = self.created_at

    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'Experience':
        """从字典创建"""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            content=data.get("content", ""),
            category=data.get("category", "deployment"),
            tags=data.get("tags", []),
            service_name=data.get("service_name", ""),
            confidence=data.get("confidence", 0.85),
            created_at=data.get("created_at", ""),
            last_used=data.get("last_used", ""),
            use_count=data.get("use_count", 0),
            source=data.get("source", "user")
        )

    def touch(self):
        """更新使用时间和计数"""
        self.last_used = datetime.now().isoformat()
        self.use_count += 1


# 经验库导出文件路径
EXPERIENCE_EXPORT_FILE = CONFIG_DIR / "experience_library.json"


class ExperienceLibrary:
    """
    经验库管理器

    基于向量检索的部署经验库，支持：
    - 语义搜索
    - 标签过滤
    - 导出/导入
    - 使用热度追踪
    """

    # 分类常量
    CATEGORY_DEPLOYMENT = "deployment"
    CATEGORY_TROUBLESHOOTING = "troubleshooting"
    CATEGORY_SECURITY = "security"
    CATEGORY_CONFIG = "config"

    def __init__(self):
        """初始化经验库"""
        db_path = CONFIG_DIR / "chroma_db"
        try:
            self.client = chromadb.PersistentClient(path=str(db_path))
            self.collection = self.client.get_or_create_collection(
                name="experiences",
                metadata={"description": "Deployment experience library"}
            )
            self.embedding_service = EmbeddingService()
            logger.info("ExperienceLibrary initialized")
        except Exception as e:
            logger.error(f"Failed to initialize ExperienceLibrary: {e}")
            raise

    def save(
        self,
        content: str,
        category: str = CATEGORY_DEPLOYMENT,
        tags: TypingList[str] = None,
        service_name: str = "",
        confidence: float = 0.85,
        source: str = "user"
    ) -> str:
        """
        保存经验到向量库

        参数:
            content: 经验内容（自然语言描述）
            category: 分类 (deployment/troubleshooting/security/config)
            tags: 标签列表
            service_name: 关联服务名
            confidence: AI 置信度
            source: 来源 (builtin/user/imported)

        返回:
            经验 ID
        """
        try:
            exp_id = str(uuid.uuid4())
            now = datetime.now().isoformat()
            tags = tags or []

            # 元数据
            metadata = {
                "category": category,
                "tags": ",".join(tags),  # ChromaDB 不支持列表，转为逗号分隔
                "service_name": service_name,
                "confidence": confidence,
                "created_at": now,
                "last_used": now,
                "use_count": 0,
                "source": source
            }

            # 生成嵌入
            embedding = self.embedding_service.get_embedding(content)

            # 添加到集合
            self.collection.add(
                ids=[exp_id],
                documents=[content],
                embeddings=[embedding],
                metadatas=[metadata]
            )

            logger.info(f"Saved experience: {exp_id[:8]}... ({category})")
            return exp_id

        except Exception as e:
            logger.error(f"Failed to save experience: {e}")
            raise

    def search(
        self,
        query: str,
        top_k: int = 5,
        category: str = None,
        service_name: str = None,
        tags: TypingList[str] = None
    ) -> TypingList[Experience]:
        """
        语义搜索经验

        参数:
            query: 查询文本
            top_k: 返回数量
            category: 分类过滤
            service_name: 服务名过滤
            tags: 标签过滤（AND 逻辑）

        返回:
            Experience 列表
        """
        try:
            embedding = self.embedding_service.get_embedding(query)

            # 构建过滤条件
            where_filter = None
            if category or service_name:
                conditions = []
                if category:
                    conditions.append({"category": category})
                if service_name:
                    conditions.append({"service_name": service_name})
                if len(conditions) == 1:
                    where_filter = conditions[0]
                else:
                    where_filter = {"$and": conditions}

            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=top_k,
                where=where_filter,
                include=["documents", "metadatas", "distances"]
            )

            experiences = []
            if results and results.get("documents"):
                for i, doc in enumerate(results["documents"][0]):
                    meta = results["metadatas"][0][i] if results.get("metadatas") else {}

                    # 标签后过滤（ChromaDB 不支持列表查询）
                    if tags:
                        meta_tags = set(meta.get("tags", "").split(","))
                        if not all(t in meta_tags for t in tags):
                            continue

                    exp = Experience(
                        id=results["ids"][0][i],
                        content=doc,
                        category=meta.get("category", "deployment"),
                        tags=meta.get("tags", "").split(",") if meta.get("tags") else [],
                        service_name=meta.get("service_name", ""),
                        confidence=float(meta.get("confidence", 0.85)),
                        created_at=meta.get("created_at", ""),
                        last_used=meta.get("last_used", ""),
                        use_count=int(meta.get("use_count", 0)),
                        source=meta.get("source", "user")
                    )
                    experiences.append(exp)

            logger.info(f"Search found {len(experiences)} experiences for: {query[:50]}...")
            return experiences

        except Exception as e:
            logger.error(f"Failed to search experiences: {e}")
            return []

    def get(self, exp_id: str) -> Optional[Experience]:
        """根据 ID 获取经验"""
        try:
            results = self.collection.get(
                ids=[exp_id],
                include=["documents", "metadatas"]
            )
            if results and results.get("documents"):
                doc = results["documents"][0]
                meta = results["metadatas"][0]
                return Experience(
                    id=exp_id,
                    content=doc,
                    category=meta.get("category", "deployment"),
                    tags=meta.get("tags", "").split(",") if meta.get("tags") else [],
                    service_name=meta.get("service_name", ""),
                    confidence=float(meta.get("confidence", 0.85)),
                    created_at=meta.get("created_at", ""),
                    last_used=meta.get("last_used", ""),
                    use_count=int(meta.get("use_count", 0)),
                    source=meta.get("source", "user")
                )
            return None
        except Exception as e:
            logger.error(f"Failed to get experience {exp_id}: {e}")
            return None

    def touch(self, exp_id: str):
        """更新经验的使用时间和计数"""
        try:
            exp = self.get(exp_id)
            if exp:
                exp.touch()
                # 更新 ChromaDB 中的元数据
                self.collection.update(
                    ids=[exp_id],
                    metadatas=[exp.to_dict()]
                )
        except Exception as e:
            logger.warning(f"Failed to touch experience {exp_id}: {e}")

    def list_all(
        self,
        category: str = None,
        source: str = None,
        limit: int = 100
    ) -> TypingList[Experience]:
        """
        列出所有经验（支持过滤）

        参数:
            category: 分类过滤
            source: 来源过滤
            limit: 最大数量

        返回:
            Experience 列表
        """
        try:
            where_filter = None
            if category or source:
                conditions = []
                if category:
                    conditions.append({"category": category})
                if source:
                    conditions.append({"source": source})
                if len(conditions) == 1:
                    where_filter = conditions[0]
                else:
                    where_filter = {"$and": conditions}

            results = self.collection.get(
                where=where_filter,
                limit=limit,
                include=["documents", "metadatas"]
            )

            experiences = []
            if results and results.get("documents"):
                for i, doc in enumerate(results["documents"]):
                    meta = results["metadatas"][i]
                    exp = Experience(
                        id=results["ids"][i],
                        content=doc,
                        category=meta.get("category", "deployment"),
                        tags=meta.get("tags", "").split(",") if meta.get("tags") else [],
                        service_name=meta.get("service_name", ""),
                        confidence=float(meta.get("confidence", 0.85)),
                        created_at=meta.get("created_at", ""),
                        last_used=meta.get("last_used", ""),
                        use_count=int(meta.get("use_count", 0)),
                        source=meta.get("source", "user")
                    )
                    experiences.append(exp)

            return experiences

        except Exception as e:
            logger.error(f"Failed to list experiences: {e}")
            return []

    def delete(self, exp_id: str) -> bool:
        """删除经验"""
        try:
            self.collection.delete(ids=[exp_id])
            logger.info(f"Deleted experience: {exp_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete experience {exp_id}: {e}")
            return False

    def export_to_file(
        self,
        file_path: str = None,
        categories: TypingList[str] = None
    ) -> int:
        """
        导出经验到 JSON 文件

        参数:
            file_path: 导出文件路径（默认 ~/.pulao/experience_library.json）
            categories: 只导出指定分类（None = 全部）

        返回:
            导出的经验数量
        """
        try:
            file_path = file_path or str(EXPERIENCE_EXPORT_FILE)

            # 获取所有经验
            experiences = self.list_all(limit=10000)

            # 分类过滤
            if categories:
                experiences = [e for e in experiences if e.category in categories]

            # 构建导出结构
            export_data = {
                "version": "1.0",
                "exported_at": datetime.now().isoformat(),
                "count": len(experiences),
                "experiences": [e.to_dict() for e in experiences]
            }

            # 写入文件
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)

            logger.info(f"Exported {len(experiences)} experiences to {file_path}")
            return len(experiences)

        except Exception as e:
            logger.error(f"Failed to export experiences: {e}")
            raise

    def import_from_file(
        self,
        file_path: str,
        mode: str = "merge"
    ) -> int:
        """
        从 JSON 文件导入经验

        参数:
            file_path: 导入文件路径
            mode: 导入模式
                - merge: 合并（保留现有，添加新的）
                - overwrite: 覆盖（清空后导入）

        返回:
            导入的经验数量
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 验证格式
            if not isinstance(data, dict) or "experiences" not in data:
                raise ValueError("Invalid export file format")

            experiences_data = data.get("experiences", [])

            # 覆盖模式：清空现有数据
            if mode == "overwrite":
                existing = self.list_all(limit=10000)
                for exp in existing:
                    self.delete(exp.id)
                logger.info("Cleared existing experiences (overwrite mode)")

            # 导入经验
            imported = 0
            for exp_data in experiences_data:
                exp = Experience.from_dict(exp_data)

                # 检查是否已存在（merge 模式）
                if mode == "merge":
                    existing = self.get(exp.id)
                    if existing:
                        continue  # 跳过已存在的

                # 重新生成嵌入并存储
                embedding = self.embedding_service.get_embedding(exp.content)
                self.collection.add(
                    ids=[exp.id],
                    documents=[exp.content],
                    embeddings=[embedding],
                    metadatas=[exp.to_dict()]
                )
                imported += 1

            logger.info(f"Imported {imported} experiences from {file_path}")
            return imported

        except Exception as e:
            logger.error(f"Failed to import experiences: {e}")
            raise

    def stats(self) -> Dict:
        """获取经验库统计信息"""
        try:
            all_exps = self.list_all(limit=10000)

            # 按分类统计
            by_category = {}
            for exp in all_exps:
                cat = exp.category
                by_category[cat] = by_category.get(cat, 0) + 1

            # 按来源统计
            by_source = {}
            for exp in all_exps:
                src = exp.source
                by_source[src] = by_source.get(src, 0) + 1

            # 热门标签
            tag_counts = {}
            for exp in all_exps:
                for tag in exp.tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
            top_tags = sorted(tag_counts.items(), key=lambda x: -x[1])[:10]

            return {
                "total": len(all_exps),
                "by_category": by_category,
                "by_source": by_source,
                "top_tags": top_tags
            }

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"total": 0, "by_category": {}, "by_source": {}, "top_tags": []}


# 全局经验库实例
_EXPERIENCE_LIBRARY: Optional[ExperienceLibrary] = None


def init_experience_library() -> ExperienceLibrary:
    """初始化全局经验库实例"""
    global _EXPERIENCE_LIBRARY
    if _EXPERIENCE_LIBRARY is None:
        _EXPERIENCE_LIBRARY = ExperienceLibrary()
    return _EXPERIENCE_LIBRARY
