"""
人工确认交互模块

提供终端交互式确认界面。
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from typing import Optional, List

from .dry_run import ExecutionPlan, ExecutionStep
from .risk_guard import RiskLevel, RiskDecision


console = Console()


class HITLController:
    """
    人工确认控制器 (Human-in-the-Loop)

    提供终端交互式确认界面，支持：
    - 执行计划展示
    - 风险等级高亮
    - 用户确认/拒绝
    """

    # 风险等级图标和颜色
    RISK_ICONS = {
        RiskLevel.READONLY: ("📖", "green"),
        RiskLevel.LOW: ("🟢", "green"),
        RiskLevel.MEDIUM: ("🟡", "yellow"),
        RiskLevel.HIGH: ("🔴", "red"),
        RiskLevel.CRITICAL: ("⛔", "red bold"),
    }

    @classmethod
    def confirm(cls, plan: ExecutionPlan) -> bool:
        """
        展示执行计划并等待用户确认

        Args:
            plan: 执行计划

        Returns:
            True: 用户确认执行
            False: 用户拒绝
        """
        # 标题
        console.print()
        console.print(Panel(
            f"[bold]计划 ID:[/bold] {plan.plan_id}",
            title="📋 执行计划预览",
            border_style="blue"
        ))

        # 整体风险
        icon, color = cls.RISK_ICONS.get(plan.total_risk, ("⚪", "white"))
        console.print(f"整体风险: [{color}]{icon} {plan.total_risk.value.upper()}[/{color}]")
        console.print(f"摘要: {plan.summary}")
        console.print()

        # 检查是否有 DENY 的步骤
        denied_steps = [s for s in plan.steps if s.risk_assessment.decision == RiskDecision.DENY]
        if denied_steps:
            console.print("[red bold]⛔ 以下操作被拒绝:[/red bold]")
            for step in denied_steps:
                console.print(f"  ⛔ {step.preview_text}")
                console.print(f"     [dim]{step.risk_assessment.reason}[/dim]")
            console.print("\n[yellow]请修改操作后重试[/yellow]")
            return False

        # 步骤列表
        cls._print_steps(plan.steps)

        # 回滚提示
        if plan.rollback_hint:
            console.print(f"\n[dim]{plan.rollback_hint}[/dim]")

        # 等待确认
        return cls._wait_confirmation(len(plan.steps))

    @classmethod
    def _print_steps(cls, steps: List[ExecutionStep]):
        """打印步骤列表"""
        console.print("[bold]操作步骤:[/bold]")

        for step in steps:
            icon, color = cls.RISK_ICONS.get(step.risk_assessment.risk_level, ("⚪", "white"))
            console.print(f"  {icon} [{color}]{step.preview_text}[/{color}]")

            # 高风险显示原因
            if step.risk_assessment.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                console.print(f"     [dim]⚠️  {step.risk_assessment.reason}[/dim]")

    @classmethod
    def _wait_confirmation(cls, step_count: int) -> bool:
        """等待用户确认"""
        console.print(f"\n[bold]是否执行以上 {step_count} 个操作?[/bold] [y/N]: ", end="")

        try:
            choice = input().strip().lower()
            return choice in ('y', 'yes', '是')
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]已取消[/yellow]")
            return False

    @classmethod
    def confirm_single(cls, tool_name: str, reason: str, preview: str = None) -> bool:
        """
        单操作确认（简化版）

        Args:
            tool_name: 工具名称
            reason: 确认原因
            preview: 操作预览（可选）

        Returns:
            True: 用户确认
            False: 用户拒绝
        """
        console.print(f"\n[yellow]⚠️  操作需要确认[/yellow]")
        console.print(f"操作: {tool_name}")

        if preview:
            console.print(f"预览: {preview}")

        console.print(f"原因: {reason}")
        console.print(f"\n是否执行? [y/N]: ", end="")

        try:
            choice = input().strip().lower()
            return choice in ('y', 'yes', '是')
        except (EOFError, KeyboardInterrupt):
            return False

    @classmethod
    def confirm_dangerous(cls, operation: str, impact: str, rollback: str = None) -> bool:
        """
        危险操作确认（带影响评估）

        Args:
            operation: 操作描述
            impact: 影响评估
            rollback: 回滚方案（可选）

        Returns:
            True: 用户确认
            False: 用户拒绝
        """
        console.print("\n[red bold]⚠️  危险操作确认[/red bold]")
        console.print(f"\n操作: {operation}")
        console.print(f"影响: {impact}")

        if rollback:
            console.print(f"回滚: {rollback}")

        console.print(f"\n[bold red]确认执行此危险操作?[/bold red] [yes/N]: ", end="")

        try:
            choice = input().strip().lower()
            return choice == 'yes'
        except (EOFError, KeyboardInterrupt):
            return False
