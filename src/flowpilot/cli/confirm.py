"""确认流程 UI 组件."""

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

console = Console()


def display_confirmation_prompt(
    preview: dict,
    risk_level: str = "medium",
) -> bool:
    """显示增强的确认提示 UI.

    Args:
        preview: 预览信息字典
        risk_level: 风险级别（low/medium/high）

    Returns:
        是否确认执行
    """
    # 风险级别颜色
    risk_colors = {
        "low": "green",
        "medium": "yellow",
        "high": "red",
    }
    color = risk_colors.get(risk_level, "yellow")

    # 构建表格
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="bold")
    table.add_column("Value")

    for key, value in preview.items():
        if key == "risk_level":
            table.add_row(key, f"[{color}]{value}[/{color}]")
        elif key == "command":
            table.add_row(key, f"[bold cyan]{value}[/bold cyan]")
        elif key == "env" and value == "prod":
            table.add_row(key, f"[bold red]{value}[/bold red]")
        else:
            table.add_row(key, str(value))

    # 显示面板
    panel = Panel(
        table,
        title=f"[{color}]⚠️  需要确认[/{color}]",
        border_style=color,
    )
    console.print(panel)

    # 确认提示
    return Confirm.ask(f"[{color}]确认执行此操作?[/{color}]", default=False)


def display_batch_confirmation(
    operations: list[dict],
    total_hosts: int,
) -> bool:
    """显示批量操作确认.

    Args:
        operations: 操作列表
        total_hosts: 总主机数

    Returns:
        是否确认执行
    """
    console.print(f"\n[bold yellow]⚠️  批量操作确认[/bold yellow]")
    console.print(f"将在 [bold]{total_hosts}[/bold] 台主机上执行以下操作:\n")

    for i, op in enumerate(operations[:5], 1):
        console.print(f"  {i}. {op.get('host', 'N/A')}: {op.get('command', 'N/A')[:50]}...")

    if len(operations) > 5:
        console.print(f"  ... 还有 {len(operations) - 5} 个操作")

    return Confirm.ask("[yellow]确认执行所有操作?[/yellow]", default=False)


def display_success_summary(
    results: list[dict],
) -> None:
    """显示成功执行摘要.

    Args:
        results: 执行结果列表
    """
    success_count = sum(1 for r in results if r.get("status") == "success")
    error_count = len(results) - success_count

    if error_count == 0:
        console.print(f"\n[bold green]✅ 全部成功: {success_count} 个操作[/bold green]")
    else:
        console.print(f"\n[yellow]⚠️  完成: {success_count} 成功, {error_count} 失败[/yellow]")
