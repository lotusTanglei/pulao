"""
规则存储模块

管理风险评估规则，支持内置规则和用户自定义规则的合并。
"""

from typing import Dict, List
from pathlib import Path
import yaml


# 内置规则
BUILTIN_RULES = {
    "deny": [
        {"pattern": "rm -rf /", "reason": "禁止删除根目录"},
        {"pattern": "rm -rf /*", "reason": "禁止删除根目录"},
        {"pattern": "mkfs", "reason": "禁止格式化磁盘"},
        {"pattern": "dd if=", "reason": "禁止裸设备写入"},
        {"pattern": ":(){ :|:& };:", "reason": "禁止 Fork 炸弹"},
        {"pattern": "chmod -R 777", "reason": "禁止全开放权限"},
        {"pattern": "DROP DATABASE", "reason": "禁止删除数据库"},
        {"pattern": "DROP TABLE", "reason": "禁止删除表"},
    ],
    "confirm": [
        {"pattern": "restart_*", "reason": "重启服务会导致短暂不可用"},
        {"pattern": "stop_*", "reason": "停止服务会影响可用性"},
        {"pattern": "deploy_*", "reason": "部署会改变服务状态"},
        {"pattern": "rollback_*", "reason": "回滚操作影响较大"},
        {"pattern": "execute_command", "reason": "Shell 命令需要确认"},
        {"pattern": "push_changes", "reason": "推送变更到远程仓库"},
    ],
    "allow": [
        {"pattern": "get_*", "reason": "只读操作"},
        {"pattern": "list_*", "reason": "只读操作"},
        {"pattern": "check_*", "reason": "只读操作"},
        {"pattern": "search_*", "reason": "只读操作"},
        {"pattern": "query_*", "reason": "只读操作"},
        {"pattern": "diagnose", "reason": "诊断操作"},
        {"pattern": "system_status", "reason": "只读操作"},
        {"pattern": "kb_stats", "reason": "只读操作"},
        {"pattern": "git_status", "reason": "只读操作"},
        {"pattern": "gitops_status", "reason": "只读操作"},
        {"pattern": "view_changelog", "reason": "只读操作"},
    ],
}


class PolicyStore:
    """
    规则存储

    管理风险评估规则，支持：
    - 内置规则
    - 用户自定义规则（覆盖内置规则）
    """

    POLICY_FILE = Path.home() / ".pulao" / "policies.yaml"

    def __init__(self):
        self._user_rules: Dict[str, List[dict]] = {}
        self._load_user_rules()

    def _load_user_rules(self):
        """加载用户自定义规则"""
        if self.POLICY_FILE.exists():
            try:
                with open(self.POLICY_FILE, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    self._user_rules = data.get("rules", {})
            except Exception:
                self._user_rules = {}

    def get_rules(self) -> Dict[str, List[dict]]:
        """
        获取合并后的规则

        合并顺序：用户规则覆盖内置规则的同名 pattern
        """
        merged = {
            "deny": list(BUILTIN_RULES.get("deny", [])),
            "confirm": list(BUILTIN_RULES.get("confirm", [])),
            "allow": list(BUILTIN_RULES.get("allow", [])),
        }

        # 用户规则覆盖
        for category, rules in self._user_rules.items():
            if category not in merged:
                merged[category] = []

            for rule in rules:
                # 移除同 pattern 的内置规则
                pattern = rule.get("pattern", "")
                merged[category] = [r for r in merged[category] if r.get("pattern") != pattern]
                # 添加用户规则
                merged[category].append(rule)

        return merged
