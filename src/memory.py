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
from src.logger import logger  # 日志记录
from src.config import CONFIG_DIR, load_config  # 配置目录


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
