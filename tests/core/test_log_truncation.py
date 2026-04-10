"""
日志截断模块测试
"""

import pytest
from src.core.log_truncation import (
    LogTruncator,
    TruncationResult,
    truncate_logs,
    truncate_for_llm
)


class TestLogTruncator:
    """测试 LogTruncator 类"""

    @pytest.fixture
    def truncator(self):
        """创建截断器实例"""
        return LogTruncator(
            max_chars=1000,
            head_lines=5,
            tail_lines=10,
            max_error_lines=5,
            max_warning_lines=3
        )

    def test_empty_logs(self, truncator):
        """测试空日志"""
        result = truncator.truncate("")

        assert result.original_lines == 0
        assert result.truncated is False
        assert result.content == ""

    def test_small_logs_not_truncated(self, truncator):
        """测试小日志不截断"""
        logs = "line 1\nline 2\nline 3"
        result = truncator.truncate(logs)

        assert result.original_lines == 3
        assert result.truncated is False
        assert result.content == logs

    def test_large_logs_truncated(self, truncator):
        """测试大日志被截断"""
        # 生成超长日志
        lines = [f"Log line {i} with some content to make it longer" for i in range(100)]
        logs = "\n".join(lines)

        result = truncator.truncate(logs)

        assert result.original_lines == 100
        assert result.truncated is True
        assert len(result.content) <= 1200  # 允许一些元数据开销
        assert "Head" in result.content
        assert "Tail" in result.content

    def test_error_extraction(self, truncator):
        """测试错误行提取（需要触发截断）"""
        # 生成足够长的日志以触发截断
        lines = [f"Normal line {i} with some padding content" for i in range(50)]
        lines.insert(10, "ERROR: Something went wrong")
        lines.insert(25, "Exception: Another error")
        lines.insert(40, "FATAL: Critical failure")
        logs = "\n".join(lines)

        result = truncator.truncate(logs)

        # 触发截断后，错误应该被提取到专门区域
        assert result.truncated is True
        assert "ERROR" in result.content
        assert "Exception" in result.content
        assert "FATAL" in result.content
        assert "Errors" in result.content

    def test_warning_extraction(self, truncator):
        """测试警告行提取"""
        logs = """
Normal line 1
WARNING: This is a warning
Normal line 2
WARN: Another warning
Normal line 3
Deprecated: Old feature
        """.strip()

        result = truncator.truncate(logs)

        assert "WARNING" in result.content or "Warnings" in result.content

    def test_head_tail_preserved(self, truncator):
        """测试首尾行被保留"""
        lines = [f"Line number {i}" for i in range(50)]
        logs = "\n".join(lines)

        result = truncator.truncate(logs)

        # 首行应该被保留
        assert "Line number 0" in result.content
        # 尾行应该被保留
        assert "Line number 49" in result.content

    def test_truncation_result_dataclass(self):
        """测试 TruncationResult 数据类"""
        result = TruncationResult(
            content="test",
            original_lines=100,
            truncated_lines=50,
            truncated=True,
            message="test message"
        )

        assert result.content == "test"
        assert result.original_lines == 100
        assert result.truncated_lines == 50
        assert result.truncated is True
        assert result.message == "test message"

    def test_convenience_function(self):
        """测试便捷函数"""
        logs = "\n".join([f"Line {i}" for i in range(100)])
        result = truncate_logs(logs, max_chars=500)

        assert result.truncated is True
        assert len(result.content) <= 600

    def test_truncate_for_llm(self):
        """测试 LLM 优化截断"""
        logs = "\n".join([f"这是一行中文日志内容 {i}" for i in range(200)])
        result = truncate_for_llm(logs, max_tokens=500)

        # 结果应该是字符串
        assert isinstance(result, str)
        # 长度应该受限
        assert len(result) <= 2000

    def test_long_line_handling(self, truncator):
        """测试超长单行处理"""
        # 创建一个超长行
        long_line = "ERROR: " + "x" * 1000
        logs = f"Line 1\n{long_line}\nLine 3"

        result = truncator.truncate(logs)

        # 应该被截断但没有崩溃
        assert result.truncated is False or "ERROR" in result.content

    def test_mixed_content(self, truncator):
        """测试混合内容（错误、警告、正常）"""
        logs = """
2024-01-01 INFO: Starting service
2024-01-01 WARNING: Low memory
2024-01-01 ERROR: Connection failed
2024-01-01 INFO: Retrying...
2024-01-01 FATAL: Service crashed
2024-01-01 WARN: Cleanup needed
        """.strip()

        result = truncator.truncate(logs)

        # 错误应该被提取
        assert "ERROR" in result.content or "Errors" in result.content
        # 警告应该被提取
        assert "WARNING" in result.content or "WARN" in result.content or "Warnings" in result.content


class TestLogTruncatorEdgeCases:
    """边界情况测试"""

    def test_exact_limit(self):
        """测试刚好在限制边界"""
        truncator = LogTruncator(max_chars=100)
        logs = "x" * 100

        result = truncator.truncate(logs)

        assert result.truncated is False

    def test_one_over_limit(self):
        """测试刚好超出限制"""
        truncator = LogTruncator(max_chars=100)
        logs = "x" * 101

        result = truncator.truncate(logs)

        assert result.truncated is True

    def test_only_errors(self):
        """测试只有错误行"""
        truncator = LogTruncator(max_chars=500)
        logs = "\n".join([f"ERROR: Error number {i}" for i in range(50)])

        result = truncator.truncate(logs)

        # 应该包含错误部分
        assert "Errors" in result.content or "ERROR" in result.content

    def test_single_line(self):
        """测试单行日志"""
        truncator = LogTruncator(max_chars=1000)
        logs = "Single line log"

        result = truncator.truncate(logs)

        assert result.truncated is False
        assert result.content == logs
