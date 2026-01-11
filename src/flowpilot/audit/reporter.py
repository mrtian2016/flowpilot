"""Markdown 报告生成器."""

from typing import Any

from ..utils.sensitive import mask_sensitive
from .logger import AuditLogger


class ReportGenerator:
    """Markdown 报告生成器."""

    def __init__(self, audit_logger: AuditLogger) -> None:
        """初始化报告生成器.

        Args:
            audit_logger: 审计日志记录器
        """
        self.audit_logger = audit_logger

    def generate_session_report(self, session_id: str) -> str:
        """生成会话报告（Markdown 格式）.

        Args:
            session_id: 会话 ID

        Returns:
            Markdown 报告
        """
        details = self.audit_logger.get_session_details(session_id)
        if not details:
            return f"# 会话未找到\n\nSession ID: `{session_id}`"

        # 生成报告
        lines = []
        lines.append(f"# FlowPilot 执行报告\n")
        lines.append(f"**Session ID:** `{details['session_id']}`\n")
        lines.append(f"**时间:** {details['timestamp']}")
        lines.append(f"**用户:** {details['user']}")
        lines.append(f"**主机:** {details['hostname']}")
        lines.append(f"**状态:** {details['status']}")
        if details['duration_sec']:
            lines.append(f"**总耗时:** {details['duration_sec']:.2f}s\n")

        # 用户输入
        lines.append("## 用户输入\n")
        lines.append(f"```\n{details['input']}\n```\n")

        # Tool 调用
        if details['tool_calls']:
            lines.append("## 执行详情\n")
            for i, tc in enumerate(details['tool_calls'], 1):
                lines.append(f"### {i}. {tc['tool_name']}\n")
                lines.append(f"**状态:** {tc['status']}")
                if tc['exit_code'] is not None:
                    lines.append(f"**退出码:** {tc['exit_code']}")
                if tc['duration_sec']:
                    lines.append(f"**耗时:** {tc['duration_sec']:.2f}s")
                lines.append("")

                # 参数（脱敏）
                lines.append("**参数:**")
                lines.append("```json")
                import json
                args_json = json.dumps(tc['tool_args'], indent=2, ensure_ascii=False)
                args_json = mask_sensitive(args_json)
                lines.append(args_json)
                lines.append("```\n")

        # 最终输出
        if details['final_output']:
            lines.append("## 最终结果\n")
            output = mask_sensitive(details['final_output'])
            lines.append(f"```\n{output}\n```\n")

        # 底部
        lines.append("---")
        lines.append("*本报告由 FlowPilot 自动生成*")

        return "\n".join(lines)

    def generate_history_summary(self, limit: int = 10) -> str:
        """生成历史记录摘要.

        Args:
            limit: 记录数量

        Returns:
            Markdown 表格
        """
        sessions = self.audit_logger.get_recent_sessions(limit)

        lines = []
        lines.append("# FlowPilot 执行历史\n")
        lines.append("| 时间 | 用户 | 输入 | 状态 | 耗时 |")
        lines.append("|------|------|------|------|------|")

        for sess in sessions:
            timestamp = sess['timestamp'][:19] if sess['timestamp'] else "N/A"
            user = sess['user']
            input_text = sess['input'][:50] + "..." if len(sess['input']) > 50 else sess['input']
            status = sess['status']
            duration = f"{sess['duration_sec']:.1f}s" if sess['duration_sec'] else "N/A"

            lines.append(f"| {timestamp} | {user} | {input_text} | {status} | {duration} |")

        return "\n".join(lines)
