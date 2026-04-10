"""
经验库测试模块

测试 ExperienceLibrary 类的核心功能。
"""

import pytest
import json
import tempfile
import os
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from src.agent.memory import (
    Experience,
    ExperienceLibrary,
    init_experience_library
)


class TestExperienceDataclass:
    """测试 Experience 数据类"""

    def test_create_experience_basic(self):
        """测试基本创建"""
        exp = Experience(
            id="test-123",
            content="Redis cluster deployment experience",
            category="deployment"
        )

        assert exp.id == "test-123"
        assert exp.content == "Redis cluster deployment experience"
        assert exp.category == "deployment"
        assert exp.tags == []
        assert exp.confidence == 0.85
        assert exp.source == "user"
        assert exp.use_count == 0

    def test_experience_auto_timestamp(self):
        """测试自动生成时间戳"""
        exp = Experience(
            id="test-456",
            content="Test",
            category="deployment"
        )

        assert exp.created_at != ""
        assert exp.last_used != ""

    def test_to_dict(self):
        """测试转换为字典"""
        exp = Experience(
            id="test-789",
            content="Test content",
            category="troubleshooting",
            tags=["redis", "cluster"],
            confidence=0.92
        )

        d = exp.to_dict()

        assert d["id"] == "test-789"
        assert d["content"] == "Test content"
        assert d["category"] == "troubleshooting"
        assert d["tags"] == ["redis", "cluster"]
        assert d["confidence"] == 0.92

    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "id": "dict-123",
            "content": "From dict",
            "category": "security",
            "tags": ["docker"],
            "confidence": 0.75,
            "created_at": "2026-01-01T00:00:00",
            "last_used": "2026-01-02T00:00:00",
            "use_count": 5,
            "source": "imported"
        }

        exp = Experience.from_dict(data)

        assert exp.id == "dict-123"
        assert exp.content == "From dict"
        assert exp.category == "security"
        assert exp.tags == ["docker"]
        assert exp.confidence == 0.75
        assert exp.use_count == 5
        assert exp.source == "imported"

    def test_touch_updates_usage(self):
        """测试 touch 方法更新使用信息"""
        exp = Experience(
            id="touch-test",
            content="Test",
            category="deployment"
        )

        old_last_used = exp.last_used
        old_count = exp.use_count

        exp.touch()

        assert exp.use_count == old_count + 1
        # last_used should be updated


class TestExperienceLibrary:
    """测试 ExperienceLibrary 类"""

    @pytest.fixture
    def mock_chroma(self):
        """Mock ChromaDB"""
        with patch('src.agent.memory.chromadb.PersistentClient') as mock_client:
            mock_collection = MagicMock()
            mock_client.return_value.get_or_create_collection.return_value = mock_collection
            yield mock_collection

    @pytest.fixture
    def mock_embedding(self):
        """Mock EmbeddingService"""
        with patch('src.agent.memory.EmbeddingService') as mock_service:
            mock_service.return_value.get_embedding.return_value = [0.1] * 1536
            yield mock_service

    @pytest.fixture
    def library(self, mock_chroma, mock_embedding):
        """创建 ExperienceLibrary 实例"""
        # Reset singleton
        import src.agent.memory as mem
        mem._EXPERIENCE_LIBRARY = None

        lib = init_experience_library()
        lib.collection = mock_chroma
        lib.embedding_service = mock_embedding.return_value
        return lib

    def test_save_experience(self, library, mock_chroma):
        """测试保存经验"""
        mock_chroma.add.return_value = None

        exp_id = library.save(
            content="Test experience",
            category="deployment",
            tags=["test"],
            service_name="redis"
        )

        assert exp_id is not None
        mock_chroma.add.assert_called_once()

        # 验证调用参数
        call_args = mock_chroma.add.call_args
        assert len(call_args.kwargs['ids']) == 1
        assert call_args.kwargs['documents'][0] == "Test experience"

    def test_search_experience(self, library, mock_chroma):
        """测试搜索经验"""
        # Mock 返回结果
        mock_chroma.query.return_value = {
            'ids': [['exp-1', 'exp-2']],
            'documents': [['Content 1', 'Content 2']],
            'metadatas': [[
                {
                    'id': 'exp-1',
                    'content': 'Content 1',
                    'category': 'deployment',
                    'tags': '["redis"]',
                    'service_name': 'redis',
                    'confidence': 0.9,
                    'created_at': '2026-01-01',
                    'last_used': '2026-01-01',
                    'use_count': 0,
                    'source': 'user'
                },
                {
                    'id': 'exp-2',
                    'content': 'Content 2',
                    'category': 'deployment',
                    'tags': '[]',
                    'service_name': '',
                    'confidence': 0.85,
                    'created_at': '2026-01-01',
                    'last_used': '2026-01-01',
                    'use_count': 0,
                    'source': 'user'
                }
            ]]
        }

        results = library.search("redis deployment")

        assert len(results) == 2
        assert results[0].content == 'Content 1'
        assert results[0].category == 'deployment'

    def test_search_with_category_filter(self, library, mock_chroma):
        """测试带分类过滤的搜索"""
        mock_chroma.query.return_value = {
            'ids': [[]],
            'documents': [[]],
            'metadatas': [[]]
        }

        library.search("query", category="troubleshooting")

        # 验证 where 条件被传递
        call_args = mock_chroma.query.call_args
        assert 'where' in call_args.kwargs
        assert call_args.kwargs['where']['category'] == 'troubleshooting'

    def test_list_all(self, library, mock_chroma):
        """测试列出所有经验"""
        mock_chroma.get.return_value = {
            'ids': ['exp-1'],
            'documents': ['Content 1'],
            'metadatas': [{
                'id': 'exp-1',
                'content': 'Content 1',
                'category': 'deployment',
                'tags': '[]',
                'service_name': '',
                'confidence': 0.85,
                'created_at': '2026-01-01',
                'last_used': '2026-01-01',
                'use_count': 0,
                'source': 'user'
            }]
        }

        results = library.list_all()

        assert len(results) == 1
        assert results[0].id == 'exp-1'

    def test_delete_experience(self, library, mock_chroma):
        """测试删除经验"""
        mock_chroma.delete.return_value = None

        library.delete("exp-to-delete")

        mock_chroma.delete.assert_called_once_with(ids=["exp-to-delete"])

    def test_export_to_file(self, library, mock_chroma):
        """测试导出到文件"""
        mock_chroma.get.return_value = {
            'ids': ['exp-1'],
            'documents': ['Content'],
            'metadatas': [{
                'id': 'exp-1',
                'content': 'Content',
                'category': 'deployment',
                'tags': '["test"]',
                'service_name': 'redis',
                'confidence': 0.9,
                'created_at': '2026-01-01',
                'last_used': '2026-01-01',
                'use_count': 5,
                'source': 'user'
            }]
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name

        try:
            count = library.export_to_file(temp_path)

            assert count == 1

            # 验证文件内容
            with open(temp_path, 'r') as f:
                data = json.load(f)

            assert data['version'] == '1.0'
            assert len(data['experiences']) == 1
            assert data['experiences'][0]['content'] == 'Content'
        finally:
            os.unlink(temp_path)

    def test_import_from_file_merge(self, library, mock_chroma):
        """测试从文件导入（合并模式）"""
        # 准备导入文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
            json.dump({
                'version': '1.0',
                'experiences': [{
                    'id': 'imported-1',
                    'content': 'Imported content',
                    'category': 'deployment',
                    'tags': ['imported'],
                    'service_name': '',
                    'confidence': 0.85,
                    'created_at': '2026-01-01',
                    'last_used': '2026-01-01',
                    'use_count': 0,
                    'source': 'imported'
                }]
            }, f)

        try:
            mock_chroma.add.return_value = None
            # merge 模式会先调用 get 检查是否存在，返回空表示不存在
            mock_chroma.get.return_value = {'ids': [], 'documents': [], 'metadatas': []}

            count = library.import_from_file(temp_path, mode="merge")

            assert count == 1
            mock_chroma.add.assert_called_once()
        finally:
            os.unlink(temp_path)

    def test_stats(self, library, mock_chroma):
        """测试统计信息"""
        mock_chroma.get.return_value = {
            'ids': ['exp-1', 'exp-2', 'exp-3'],
            'documents': ['C1', 'C2', 'C3'],
            'metadatas': [
                {'category': 'deployment', 'tags': '["redis"]', 'source': 'user'},
                {'category': 'deployment', 'tags': '["mysql"]', 'source': 'user'},
                {'category': 'troubleshooting', 'tags': '["redis"]', 'source': 'builtin'}
            ]
        }

        stats = library.stats()

        assert stats['total'] == 3
        assert stats['by_category']['deployment'] == 2
        assert stats['by_category']['troubleshooting'] == 1
        assert stats['by_source']['user'] == 2
        assert stats['by_source']['builtin'] == 1


class TestExperienceLibrarySingleton:
    """测试单例模式"""

    def test_singleton_returns_same_instance(self):
        """测试单例返回相同实例"""
        import src.agent.memory as mem
        mem._EXPERIENCE_LIBRARY = None

        with patch('src.agent.memory.chromadb.PersistentClient'), \
             patch('src.agent.memory.EmbeddingService'):
            lib1 = init_experience_library()
            lib2 = init_experience_library()

            assert lib1 is lib2
