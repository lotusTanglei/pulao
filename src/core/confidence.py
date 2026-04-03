"""
置信度评估模块

评估 AI 工具调用的置信度，低置信度时强制人工确认。
"""

from dataclasses import dataclass
from typing import List, Optional
import re


@dataclass
class ConfidenceResult:
    """置信度评估结果"""
    score: float                    # 0.0 - 1.0
    reasoning: str                  # AI 的推理过程
    alternatives: List['AlternativeAction']  # 替代方案
    raw_response: Optional[str]     # AI 原始响应（用于调试）


@dataclass
class AlternativeAction:
    """替代操作"""
    tool_name: str
    arguments: dict
    confidence: float
    description: str                # 为什么这个替代方案更好


class ConfidenceEvaluator:
    """
    置信度评估器

    从 AI 响应中解析置信度，评估工具调用的可靠性。
    """

    # 置信度阈值
    LOW_CONFIDENCE_THRESHOLD = 0.8
    VERY_LOW_THRESHOLD = 0.5

    # 置信度解析正则（支持负数）
    CONFIDENCE_PATTERN = re.compile(
        r'<confidence>\s*(-?\d+\.?\d*)\s*</confidence>',
        re.IGNORECASE | re.DOTALL
    )

    REASONING_PATTERN = re.compile(
        r'<reasoning>\s*(.*?)\s*</reasoning>',
        re.IGNORECASE | re.DOTALL
    )

    ALTERNATIVES_PATTERN = re.compile(
        r'<alternatives>\s*(.*?)\s*</alternatives>',
        re.IGNORECASE | re.DOTALL
    )

    @classmethod
    def parse_confidence(cls, ai_response: str) -> ConfidenceResult:
        """
        从 AI 响应中解析置信度

        Args:
            ai_response: AI 的原始响应文本

        Returns:
            ConfidenceResult: 包含置信度、推理和替代方案
        """
        # 解析置信度分数
        confidence_match = cls.CONFIDENCE_PATTERN.search(ai_response)
        if confidence_match:
            try:
                score = float(confidence_match.group(1))
                # 确保在 0-1 范围内
                score = max(0.0, min(1.0, score))
            except ValueError:
                score = 0.5  # 解析失败，默认中等置信度
        else:
            # 没有置信度标签，默认高置信度（兼容旧版 AI）
            score = 0.85

        # 解析推理过程
        reasoning_match = cls.REASONING_PATTERN.search(ai_response)
        reasoning = reasoning_match.group(1).strip() if reasoning_match else "AI 未提供推理过程"

        # 解析替代方案
        alternatives = cls._parse_alternatives(ai_response)

        return ConfidenceResult(
            score=score,
            reasoning=reasoning,
            alternatives=alternatives,
            raw_response=ai_response
        )

    @classmethod
    def _parse_alternatives(cls, text: str) -> List[AlternativeAction]:
        """解析替代方案"""
        alternatives = []

        alt_match = cls.ALTERNATIVES_PATTERN.search(text)
        if not alt_match:
            return alternatives

        alt_text = alt_match.group(1)

        # 尝试解析 JSON 格式的替代方案
        import json
        try:
            # 使用更健壮的 JSON 提取：逐个字符解析，跟踪花括号深度
            i = 0
            while i < len(alt_text):
                if alt_text[i] == '{':
                    depth = 0
                    start = i
                    while i < len(alt_text):
                        if alt_text[i] == '{':
                            depth += 1
                        elif alt_text[i] == '}':
                            depth -= 1
                            if depth == 0:
                                # 找到完整的 JSON 对象
                                json_str = alt_text[start:i+1]
                                try:
                                    alt_data = json.loads(json_str)
                                    alternatives.append(AlternativeAction(
                                        tool_name=alt_data.get("tool") or alt_data.get("action") or "unknown",
                                        arguments=alt_data.get("args") or alt_data.get("arguments") or {},
                                        confidence=float(alt_data.get("confidence", 0.5)),
                                        description=alt_data.get("description") or alt_data.get("reason") or ""
                                    ))
                                except (json.JSONDecodeError, ValueError, TypeError):
                                    pass
                                break
                        i += 1
                i += 1
        except Exception:
            pass

        return alternatives

    @classmethod
    def is_low_confidence(cls, score: float) -> bool:
        """判断是否为低置信度"""
        return score < cls.LOW_CONFIDENCE_THRESHOLD

    @classmethod
    def is_very_low_confidence(cls, score: float) -> bool:
        """判断是否为极低置信度"""
        return score < cls.VERY_LOW_THRESHOLD

    @classmethod
    def get_confidence_level(cls, score: float) -> str:
        """获取置信度等级描述"""
        if score >= 0.9:
            return "非常高"
        elif score >= 0.8:
            return "高"
        elif score >= 0.6:
            return "中等"
        elif score >= 0.4:
            return "较低"
        else:
            return "很低"

    @classmethod
    def adjust_for_risk(cls, base_confidence: float, risk_level: str) -> float:
        """
        根据风险等级调整置信度

        高风险操作降低置信度，促使更多确认
        """
        risk_penalties = {
            "readonly": 0.0,
            "low": 0.0,
            "medium": -0.05,
            "high": -0.10,
            "critical": -0.20,
        }

        penalty = risk_penalties.get(risk_level, 0.0)
        adjusted = base_confidence + penalty

        return round(max(0.0, min(1.0, adjusted)), 2)
