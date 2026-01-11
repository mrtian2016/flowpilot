"""命令别名系统 - 快捷命令定义."""

from pathlib import Path
from typing import Any

import yaml

# 默认别名配置路径
ALIASES_FILE = Path.home() / ".flowpilot" / "aliases.yaml"

# 内置别名
BUILTIN_ALIASES: dict[str, str] = {
    "status": "查看服务器状态",
    "disk": "检查磁盘使用情况",
    "mem": "检查内存使用情况",
    "cpu": "检查 CPU 使用情况",
    "uptime": "查看运行时间",
    "logs": "查看最近的系统日志",
    "docker": "查看 Docker 容器状态",
    "restart": "重启服务",
    "top": "查看系统负载和进程",
}


class AliasManager:
    """命令别名管理器."""

    def __init__(self, aliases_file: Path | None = None) -> None:
        """初始化别名管理器.

        Args:
            aliases_file: 别名配置文件路径
        """
        self.aliases_file = aliases_file or ALIASES_FILE
        self._user_aliases: dict[str, str] = {}
        self._load_aliases()

    def _load_aliases(self) -> None:
        """加载用户别名."""
        if self.aliases_file.exists():
            try:
                with open(self.aliases_file, encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    self._user_aliases = data.get("aliases", {})
            except Exception:
                pass

    def save_aliases(self) -> None:
        """保存用户别名."""
        self.aliases_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.aliases_file, "w", encoding="utf-8") as f:
            yaml.dump({"aliases": self._user_aliases}, f, allow_unicode=True)

    def get(self, alias: str) -> str | None:
        """获取别名对应的命令.

        Args:
            alias: 别名

        Returns:
            完整命令或 None
        """
        # 用户别名优先
        if alias in self._user_aliases:
            return self._user_aliases[alias]
        # 内置别名
        if alias in BUILTIN_ALIASES:
            return BUILTIN_ALIASES[alias]
        return None

    def add(self, alias: str, command: str) -> None:
        """添加用户别名.

        Args:
            alias: 别名
            command: 完整命令
        """
        self._user_aliases[alias] = command
        self.save_aliases()

    def remove(self, alias: str) -> bool:
        """移除用户别名.

        Args:
            alias: 别名

        Returns:
            是否成功移除
        """
        if alias in self._user_aliases:
            del self._user_aliases[alias]
            self.save_aliases()
            return True
        return False

    def list_all(self) -> dict[str, dict[str, str]]:
        """列出所有别名.

        Returns:
            {builtin: {...}, user: {...}}
        """
        return {
            "builtin": BUILTIN_ALIASES.copy(),
            "user": self._user_aliases.copy(),
        }

    def expand(self, input_text: str) -> str:
        """展开输入中的别名.

        如果输入以别名开头，则展开为完整命令.

        Args:
            input_text: 用户输入

        Returns:
            展开后的文本
        """
        parts = input_text.strip().split(maxsplit=1)
        if not parts:
            return input_text

        first_word = parts[0].lower()
        expanded = self.get(first_word)

        if expanded:
            # 替换别名，保留后续参数
            if len(parts) > 1:
                return f"{expanded} {parts[1]}"
            return expanded

        return input_text
