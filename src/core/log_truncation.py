"""
日志截断模块

实现日志的智能滑动窗口截断，避免大量日志导致 LLM 上下文溢出。

核心功能：
1. 基于字符/Token 限制的截断
2. 保留关键信息（错误、警告）
3. 滑动窗口策略（保留首尾）
4. 截断标记和统计信息
"""

import re
from typing import List, Tuple, Optional
from dataclasses import dataclass

from src.core.logger import logger


@dataclass
class TruncationResult:
    """截断结果"""
    content: str           # 截断后的内容
    original_lines: int    # 原始行数
    truncated_lines: int   # 被截断的行数
    truncated: bool        # 是否发生了截断
    message: str           # 截断说明


class LogTruncator:
    """
    日志截断器

    使用滑动窗口策略截断大日志，保留关键信息。
    """

    # 默认配置
    DEFAULT_MAX_CHARS = 8000        # 默认最大字符数（约 2000 tokens）
    DEFAULT_HEAD_LINES = 10         # 保留头部行数
    DEFAULT_TAIL_LINES = 50         # 保留尾部行数
    DEFAULT_MAX_ERROR_LINES = 20    # 最大错误行数
    DEFAULT_MAX_WARNING_LINES = 10  # 最大警告行数

    # 错误模式
    ERROR_PATTERNS = [
        r"\berror\b",
        r"\bexception\b",
        r"\bfailed\b",
        r"\bfatal\b",
        r"\bcritical\b",
        r"\bpanic\b",
    ]

    # 警告模式
    WARNING_PATTERNS = [
        r"\bwarn(?:ing)?\b",
        r"\bdeprecated\b",
        r"\bcaution\b",
    ]

    def __init__(
        self,
        max_chars: int = DEFAULT_MAX_CHARS,
        head_lines: int = DEFAULT_HEAD_LINES,
        tail_lines: int = DEFAULT_TAIL_LINES,
        max_error_lines: int = DEFAULT_MAX_ERROR_LINES,
        max_warning_lines: int = DEFAULT_MAX_WARNING_LINES
    ):
        """
        初始化日志截断器

        参数:
            max_chars: 最大字符数限制
            head_lines: 保留的头部行数
            tail_lines: 保留的尾部行数
            max_error_lines: 最大错误行数
            max_warning_lines: 最大警告行数
        """
        self.max_chars = max_chars
        self.head_lines = head_lines
        self.tail_lines = tail_lines
        self.max_error_lines = max_error_lines
        self.max_warning_lines = max_warning_lines

        # 编译正则表达式（使用 IGNORECASE 标志）
        self.error_regex = re.compile("|".join(self.ERROR_PATTERNS), re.IGNORECASE)
        self.warning_regex = re.compile("|".join(self.WARNING_PATTERNS), re.IGNORECASE)

    def truncate(self, logs: str) -> TruncationResult:
        """
        截断日志

        使用滑动窗口策略：
        1. 保留头部 N 行（上下文）
        2. 保留尾部 M 行（最新状态）
        3. 提取并保留错误/警告行
        4. 如果总长度仍超限，优先截断中间部分

        参数:
            logs: 原始日志内容

        返回:
            TruncationResult 截断结果
        """
        if not logs:
            return TruncationResult(
                content="",
                original_lines=0,
                truncated_lines=0,
                truncated=False,
                message="日志为空"
            )

        lines = logs.split("\n")
        original_lines = len(lines)

        # 如果原始内容在限制内，直接返回
        if len(logs) <= self.max_chars:
            return TruncationResult(
                content=logs,
                original_lines=original_lines,
                truncated_lines=0,
                truncated=False,
                message="日志未超出限制"
            )

        logger.info(f"Log truncation needed: {len(logs)} chars > {self.max_chars}")

        # 提取关键行
        head_lines = lines[:self.head_lines]
        tail_lines = lines[-self.tail_lines:] if len(lines) > self.tail_lines else []

        # 提取错误和警告行
        error_lines = self._extract_errors(lines)
        warning_lines = self._extract_warnings(lines)

        # 构建截断后的内容
        parts = []
        parts.append(f"[Log Truncation / 日志截断]")
        parts.append(f"Original: {original_lines} lines, {len(logs)} chars")
        parts.append("")

        # 添加头部
        if head_lines:
            parts.append(f"--- Head ({len(head_lines)} lines) ---")
            parts.extend(head_lines)
            parts.append("")

        # 添加错误行
        if error_lines:
            parts.append(f"--- Errors ({len(error_lines)} lines) ---")
            parts.extend(error_lines[:self.max_error_lines])
            if len(error_lines) > self.max_error_lines:
                parts.append(f"... and {len(error_lines) - self.max_error_lines} more error lines")
            parts.append("")

        # 添加警告行
        if warning_lines:
            parts.append(f"--- Warnings ({len(warning_lines)} lines) ---")
            parts.extend(warning_lines[:self.max_warning_lines])
            if len(warning_lines) > self.max_warning_lines:
                parts.append(f"... and {len(warning_lines) - self.max_warning_lines} more warning lines")
            parts.append("")

        # 添加截断标记
        middle_start = self.head_lines
        middle_end = len(lines) - self.tail_lines
        if middle_end > middle_start:
            parts.append(f"... [truncated {middle_end - middle_start} middle lines] ...")
            parts.append("")

        # 添加尾部
        if tail_lines:
            parts.append(f"--- Tail ({len(tail_lines)} lines) ---")
            parts.extend(tail_lines)

        content = "\n".join(parts)

        # 如果仍然超限，强制截断尾部
        if len(content) > self.max_chars:
            content = content[:self.max_chars - 100]
            content += "\n\n... [log truncated due to size limit]"

        truncated_lines = original_lines - len(content.split("\n"))

        return TruncationResult(
            content=content,
            original_lines=original_lines,
            truncated_lines=max(0, truncated_lines),
            truncated=True,
            message=f"Truncated from {original_lines} lines, kept head/tail/errors/warnings"
        )

    def _extract_errors(self, lines: List[str]) -> List[str]:
        """提取包含错误的行"""
        error_lines = []
        for line in lines:
            if self.error_regex.search(line):
                # 限制单行长度
                error_lines.append(line[:500] if len(line) > 500 else line)
        return error_lines

    def _extract_warnings(self, lines: List[str]) -> List[str]:
        """提取包含警告的行"""
        warning_lines = []
        for line in lines:
            if self.warning_regex.search(line):
                warning_lines.append(line[:500] if len(line) > 500 else line)
        return warning_lines


def truncate_logs(
    logs: str,
    max_chars: int = LogTruncator.DEFAULT_MAX_CHARS
) -> TruncationResult:
    """
    便捷函数：截断日志

    参数:
        logs: 日志内容
        max_chars: 最大字符数

    返回:
        TruncationResult
    """
    truncator = LogTruncator(max_chars=max_chars)
    return truncator.truncate(logs)


def truncate_for_llm(
    logs: str,
    max_tokens: int = 2000
) -> str:
    """
    为 LLM 优化日志截断

    按 token 估算进行截断（约 4 字符 = 1 token）

    参数:
        logs: 日志内容
        max_tokens: 最大 token 数

    返回:
        截断后的日志字符串
    """
    # 估算字符数（1 token ≈ 4 字符对于中文/混合内容）
    max_chars = max_tokens * 3

    result = truncate_logs(logs, max_chars=max_chars)
    return result.content
