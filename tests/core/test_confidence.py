"""
置信度评估模块单元测试
"""

import pytest
from src.core.confidence import (
    ConfidenceEvaluator,
    ConfidenceResult,
    AlternativeAction
)


class TestConfidenceEvaluator:
    """置信度评估器测试"""

    def test_parse_confidence_from_tag(self):
        """从标签解析置信度"""
        response = """
        基于日志分析，我认为问题是内存不足。
        <confidence>0.75</confidence>
        <reasoning>容器 OOMKilled，内存使用率达到 95%</reasoning>
        """

        result = ConfidenceEvaluator.parse_confidence(response)

        assert result.score == 0.75
        assert "OOMKilled" in result.reasoning

    def test_parse_high_confidence(self):
        """解析高置信度"""
        response = "<confidence>0.95</confidence>"
        result = ConfidenceEvaluator.parse_confidence(response)

        assert result.score == 0.95
        assert ConfidenceEvaluator.get_confidence_level(result.score) == "非常高"

    def test_parse_low_confidence(self):
        """解析低置信度"""
        response = "<confidence>0.45</confidence>"
        result = ConfidenceEvaluator.parse_confidence(response)

        assert result.score == 0.45
        assert ConfidenceEvaluator.is_low_confidence(result.score)
        assert ConfidenceEvaluator.is_very_low_confidence(result.score)

    def test_no_confidence_tag_defaults_high(self):
        """无置信度标签时默认高置信度"""
        response = "我将重启容器来解决问题。"
        result = ConfidenceEvaluator.parse_confidence(response)

        # 默认 0.85（兼容旧版 AI）
        assert result.score == 0.85

    def test_confidence_clamped_to_range(self):
        """置信度应在 0-1 范围内"""
        # 超过 1
        response = "<confidence>1.5</confidence>"
        result = ConfidenceEvaluator.parse_confidence(response)
        assert result.score == 1.0

        # 低于 0
        response = "<confidence>-0.5</confidence>"
        result = ConfidenceEvaluator.parse_confidence(response)
        assert result.score == 0.0

    def test_parse_reasoning(self):
        """解析推理过程"""
        response = """
        <confidence>0.80</confidence>
        <reasoning>
        1. 日志显示内存泄漏
        2. 容器重启 3 次
        3. 建议增加内存限制
        </reasoning>
        """

        result = ConfidenceEvaluator.parse_confidence(response)

        assert "内存泄漏" in result.reasoning
        assert "增加内存限制" in result.reasoning

    def test_parse_alternatives_json(self):
        """解析 JSON 格式的替代方案"""
        response = """
        <confidence>0.65</confidence>
        <alternatives>
        {"tool": "increase_memory", "confidence": 0.85, "description": "增加内存限制"}
        {"tool": "check_memory_leak", "confidence": 0.80, "description": "检查内存泄漏"}
        </alternatives>
        """

        result = ConfidenceEvaluator.parse_confidence(response)

        assert len(result.alternatives) == 2
        assert result.alternatives[0].tool_name == "increase_memory"
        assert result.alternatives[0].confidence == 0.85

    def test_is_low_confidence(self):
        """测试低置信度判断"""
        assert ConfidenceEvaluator.is_low_confidence(0.79) is True
        assert ConfidenceEvaluator.is_low_confidence(0.80) is False
        assert ConfidenceEvaluator.is_low_confidence(0.85) is False

    def test_is_very_low_confidence(self):
        """测试极低置信度判断"""
        assert ConfidenceEvaluator.is_very_low_confidence(0.49) is True
        assert ConfidenceEvaluator.is_very_low_confidence(0.50) is False

    def test_adjust_for_risk_readonly(self):
        """只读操作不降低置信度"""
        adjusted = ConfidenceEvaluator.adjust_for_risk(0.85, "readonly")
        assert adjusted == 0.85

    def test_adjust_for_risk_medium(self):
        """中风险操作降低置信度"""
        adjusted = ConfidenceEvaluator.adjust_for_risk(0.85, "medium")
        assert adjusted == 0.80

    def test_adjust_for_risk_high(self):
        """高风险操作大幅降低置信度"""
        adjusted = ConfidenceEvaluator.adjust_for_risk(0.85, "high")
        assert adjusted == 0.75

    def test_adjust_for_risk_critical(self):
        """危险操作大幅降低置信度"""
        adjusted = ConfidenceEvaluator.adjust_for_risk(0.85, "critical")
        assert adjusted == 0.65

    def test_adjust_clamped_to_range(self):
        """调整后置信度应在 0-1 范围内"""
        adjusted = ConfidenceEvaluator.adjust_for_risk(0.05, "critical")
        assert adjusted == 0.0  # 不会低于 0

    def test_get_confidence_level(self):
        """测试置信度等级描述"""
        assert ConfidenceEvaluator.get_confidence_level(0.95) == "非常高"
        assert ConfidenceEvaluator.get_confidence_level(0.85) == "高"
        assert ConfidenceEvaluator.get_confidence_level(0.70) == "中等"
        assert ConfidenceEvaluator.get_confidence_level(0.50) == "较低"
        assert ConfidenceEvaluator.get_confidence_level(0.30) == "很低"


class TestConfidenceIntegration:
    """置信度集成测试"""

    def test_full_response_parsing(self):
        """完整响应解析"""
        response = """
        根据日志分析，容器因内存不足被 OOMKilled。

        <confidence>0.72</confidence>

        <reasoning>
        1. 日志显示 "OOMKilled" 错误
        2. 内存使用率峰值 2GB，限制 1.5GB
        3. 重启容器可能暂时解决问题，但根本原因未解决
        </reasoning>

        <alternatives>
        {"tool": "update_memory_limit", "args": {"limit": "2.5GB"}, "confidence": 0.88, "description": "增加内存限制到 2.5GB"}
        {"tool": "analyze_memory_usage", "args": {}, "confidence": 0.82, "description": "分析内存使用模式，查找泄漏"}
        </alternatives>
        """

        result = ConfidenceEvaluator.parse_confidence(response)

        assert result.score == 0.72
        assert ConfidenceEvaluator.is_low_confidence(result.score)
        assert len(result.alternatives) == 2
        assert result.alternatives[0].tool_name == "update_memory_limit"
        assert result.alternatives[0].confidence == 0.88
