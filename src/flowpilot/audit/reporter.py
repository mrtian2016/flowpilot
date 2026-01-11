"""报告生成器 - 支持 Markdown 和 HTML 格式."""

import json
import re
from datetime import datetime, timedelta
from typing import Any

from ..utils.sensitive import mask_sensitive
from .logger import AuditLogger


class ReportGenerator:
    """报告生成器（支持 Markdown 和 HTML）."""

    def __init__(self, audit_logger: AuditLogger) -> None:
        """初始化报告生成器.

        Args:
            audit_logger: 审计日志记录器
        """
        self.audit_logger = audit_logger

    def generate_session_report(self, session_id: str, format: str = "markdown") -> str:
        """生成会话报告.

        Args:
            session_id: 会话 ID
            format: 输出格式（markdown/html）

        Returns:
            报告内容
        """
        details = self.audit_logger.get_session_details(session_id)
        if not details:
            return f"# 会话未找到\n\nSession ID: `{session_id}`"

        if format == "html":
            return self._generate_html_report(details)
        return self._generate_markdown_report(details)

    def _generate_markdown_report(self, details: dict) -> str:
        """生成 Markdown 报告."""
        lines = []
        lines.append(f"# FlowPilot 执行报告\n")
        lines.append(f"**Session ID:** `{details['session_id']}`\n")
        lines.append(f"**时间:** {details['timestamp']}")
        lines.append(f"**用户:** {details['user']}")
        lines.append(f"**主机:** {details['hostname']}")
        lines.append(f"**状态:** {details['status']}")
        if details.get('duration_sec'):
            lines.append(f"**总耗时:** {details['duration_sec']:.2f}s\n")

        lines.append("## 用户输入\n")
        lines.append(f"```\n{details['input']}\n```\n")

        if details.get('tool_calls'):
            lines.append("## 执行详情\n")
            for i, tc in enumerate(details['tool_calls'], 1):
                lines.append(f"### {i}. {tc['tool_name']}\n")
                lines.append(f"**状态:** {tc['status']}")
                if tc.get('exit_code') is not None:
                    lines.append(f"**退出码:** {tc['exit_code']}")
                if tc.get('duration_sec'):
                    lines.append(f"**耗时:** {tc['duration_sec']:.2f}s")
                lines.append("")
                lines.append("**参数:**")
                lines.append("```json")
                args_json = json.dumps(tc.get('tool_args', {}), indent=2, ensure_ascii=False)
                lines.append(mask_sensitive(args_json))
                lines.append("```\n")

        if details.get('final_output'):
            lines.append("## 最终结果\n")
            lines.append(f"```\n{mask_sensitive(details['final_output'])}\n```\n")

        lines.append("---")
        lines.append("*本报告由 FlowPilot 自动生成*")
        return "\n".join(lines)

    def _generate_html_report(self, details: dict) -> str:
        """生成 HTML 报告."""
        duration_html = ""
        if details.get('duration_sec'):
            duration_html = f"<div class='meta-item'><span class='meta-label'>总耗时:</span> {details['duration_sec']:.2f}s</div>"

        tools_html = ""
        if details.get('tool_calls'):
            tools_html = "<h2>⚙️ 执行详情</h2>\n"
            for i, tc in enumerate(details['tool_calls'], 1):
                args_json = mask_sensitive(json.dumps(tc.get('tool_args', {}), indent=2, ensure_ascii=False))
                exit_html = f"<div>退出码: {tc['exit_code']}</div>" if tc.get('exit_code') is not None else ""
                dur_html = f"<div>耗时: {tc['duration_sec']:.2f}s</div>" if tc.get('duration_sec') else ""
                tools_html += f"""<div class="tool-card">
                <div class="tool-name">{i}. {tc['tool_name']}</div>
                <div>状态: {tc['status']}</div>{exit_html}{dur_html}
                <pre><code>{args_json}</code></pre>
            </div>"""

        output_html = ""
        if details.get('final_output'):
            output_html = f"<h2>✅ 最终结果</h2><pre><code>{mask_sensitive(details['final_output'])}</code></pre>"

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>FlowPilot 报告 - {details['session_id']}</title>
    <style>
        body {{ font-family: system-ui; background: #1a1a2e; color: #e0e0e0; padding: 2rem; }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        h1 {{ color: #00d4ff; border-bottom: 2px solid #00d4ff; padding-bottom: 0.5rem; }}
        h2 {{ color: #7c3aed; margin-top: 1.5rem; }}
        .meta {{ background: rgba(255,255,255,0.05); padding: 1rem; border-radius: 8px; }}
        .meta-item {{ margin: 0.5rem 0; }}
        .meta-label {{ color: #9ca3af; }}
        pre {{ background: #0f172a; padding: 1rem; border-radius: 8px; overflow-x: auto; }}
        code {{ color: #22d3ee; }}
        .tool-card {{ background: rgba(124,58,237,0.1); border: 1px solid #7c3aed; border-radius: 8px; padding: 1rem; margin: 1rem 0; }}
        .tool-name {{ color: #a78bfa; font-weight: bold; }}
    </style>
</head>
<body>
<div class="container">
    <h1>🚀 FlowPilot 执行报告</h1>
    <div class="meta">
        <div class="meta-item"><span class="meta-label">Session ID:</span> <code>{details['session_id']}</code></div>
        <div class="meta-item"><span class="meta-label">时间:</span> {details['timestamp']}</div>
        <div class="meta-item"><span class="meta-label">用户:</span> {details['user']}</div>
        <div class="meta-item"><span class="meta-label">状态:</span> {details['status']}</div>
        {duration_html}
    </div>
    <h2>📝 用户输入</h2>
    <pre><code>{details['input']}</code></pre>
    {tools_html}
    {output_html}
    <div style="margin-top:2rem;color:#6b7280;font-size:0.85rem;">本报告由 FlowPilot 自动生成</div>
</div>
</body>
</html>"""

    def generate_history_summary(self, limit: int = 10, since: str | None = None) -> str:
        """生成历史记录摘要."""
        sessions = self.audit_logger.get_recent_sessions(limit)
        if since:
            sessions = self._filter_by_time(sessions, since)

        lines = ["# FlowPilot 执行历史\n"]
        lines.append("| 时间 | 用户 | 输入 | 状态 | 耗时 |")
        lines.append("|------|------|------|------|------|")

        for sess in sessions:
            ts = sess['timestamp'][:19] if sess.get('timestamp') else "N/A"
            user = sess.get('user', 'N/A')
            inp = sess.get('input', '')[:50] + ("..." if len(sess.get('input', '')) > 50 else "")
            status = sess.get('status', 'N/A')
            dur = f"{sess['duration_sec']:.1f}s" if sess.get('duration_sec') else "N/A"
            lines.append(f"| {ts} | {user} | {inp} | {status} | {dur} |")

        return "\n".join(lines)

    def generate_statistics(self, since: str = "7d") -> dict[str, Any]:
        """生成使用统计."""
        sessions = self.audit_logger.get_recent_sessions(limit=1000)
        sessions = self._filter_by_time(sessions, since)

        if not sessions:
            return {"total": 0, "success": 0, "error": 0, "success_rate": 0}

        total = len(sessions)
        success = sum(1 for s in sessions if s.get('status') == 'completed')
        error = total - success

        tool_counts: dict[str, int] = {}
        for sess in sessions:
            details = self.audit_logger.get_session_details(sess['session_id'])
            if details and details.get('tool_calls'):
                for tc in details['tool_calls']:
                    name = tc.get('tool_name', 'unknown')
                    tool_counts[name] = tool_counts.get(name, 0) + 1

        return {
            "period": since,
            "total": total,
            "success": success,
            "error": error,
            "success_rate": round(success / total * 100, 1) if total > 0 else 0,
            "top_tools": sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)[:5],
        }

    def _filter_by_time(self, sessions: list[dict], since: str) -> list[dict]:
        """按时间过滤会话."""
        match = re.match(r"(\d+)([dhm])", since.lower())
        if not match:
            return sessions

        value = int(match.group(1))
        unit = match.group(2)

        if unit == "m":
            delta = timedelta(minutes=value)
        elif unit == "h":
            delta = timedelta(hours=value)
        elif unit == "d":
            delta = timedelta(days=value)
        else:
            return sessions

        cutoff = datetime.now() - delta
        filtered = []
        for sess in sessions:
            try:
                ts = datetime.fromisoformat(sess['timestamp'][:19])
                if ts >= cutoff:
                    filtered.append(sess)
            except (ValueError, TypeError):
                continue
        return filtered
