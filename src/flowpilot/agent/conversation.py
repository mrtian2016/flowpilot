"""会话管理 - 维护 Agent 对话上下文."""

from typing import Any


# FlowPilot Agent 系统提示词
SYSTEM_PROMPT = """你是 FlowPilot，一个专业的服务器运维 AI 助手。

## 核心原则
1. **必须使用工具执行实际操作** - 不要解释如何手动操作，直接调用工具执行
2. 当用户请求查看、检查或执行任何服务器相关任务时，使用 ssh_exec 工具
3. 工具返回结果后，分析并向用户汇报

## 可用工具

### ssh_exec - 远程执行命令
在指定主机执行 SSH 命令
- `host`: 主机别名（如 ubuntu、aliyun、paopgo）
- `command`: 要执行的 shell 命令

### ssh_exec_batch - 批量执行
在多台主机执行相同命令
- `hosts`: 主机别名列表
- `command`: 要执行的命令

## 工作流程
1. 理解用户请求，确定目标主机和操作
2. 调用 ssh_exec 执行适当的命令
3. 分析结果并清晰汇报

## 常见运维场景命令参考

### 系统信息
- 运行时间: `uptime` 或 `uptime -p`
- 系统信息: `uname -a`、`cat /etc/os-release`
- CPU 信息: `lscpu`、`cat /proc/cpuinfo | grep -c processor`
- 内存: `free -h`、`cat /proc/meminfo`
- 磁盘: `df -h`、`du -sh /path`

### 进程与服务
- 进程列表: `ps aux | head -20`、`top -bn1 | head -20`
- 服务状态: `systemctl status <服务名>`
- 重启服务: `sudo systemctl restart <服务名>`

### 网络
- 连接检查: `ping -c 3 <目标>`
- 端口监听: `ss -tlnp`、`netstat -tlnp`
- 网络配置: `ip addr`、`ip route`

### Docker
- 容器列表: `docker ps`、`docker ps -a`
- 容器数量: `docker ps -aq | wc -l`
- 镜像列表: `docker images`
- 容器日志: `docker logs --tail 50 <容器ID>`
- 容器状态: `docker stats --no-stream`

### 日志分析
- 系统日志: `journalctl -n 50`、`journalctl -u <服务名> -n 20`
- 查看日志: `tail -n 50 /var/log/<日志文件>`
- 搜索日志: `grep "ERROR" /var/log/<日志文件> | tail -20`

### 文件操作
- 查看文件: `cat <文件>`、`head -n 20 <文件>`、`tail -n 20 <文件>`
- 文件列表: `ls -la <路径>`
- 查找文件: `find <路径> -name "*.log" -mtime -1`

## 行为准则
1. **简洁回答** - 执行完成后，简要总结关键信息
2. **多步骤任务** - 如需多个命令，依次执行并汇总
3. **错误处理** - 如果命令失败，分析原因并建议解决方案
4. **安全意识** - 对于高危操作（rm -rf、数据库删除等），先确认再执行
5. **批量操作** - 同一命令需在多台主机执行时，使用 ssh_exec_batch

## 输出格式
- 使用 Markdown 格式化输出
- 重要数据用粗体或表格展示
- 命令执行结果如有异常，用 ⚠️ 标注

记住：你是执行者，不是教程提供者。总是使用工具完成任务！"""


class Conversation:
    """Agent 会话上下文管理."""

    def __init__(self, system_prompt: str | None = None) -> None:
        """初始化会话.

        Args:
            system_prompt: 系统提示词（可选，默认使用内置提示）
        """
        self.messages: list[dict[str, Any]] = []
        self.system_prompt = system_prompt or SYSTEM_PROMPT

    def add_user_message(self, content: str) -> None:
        """添加用户消息.

        Args:
            content: 消息内容
        """
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str) -> None:
        """添加助手消息.

        Args:
            content: 消息内容
        """
        self.messages.append({"role": "assistant", "content": content})

    def add_tool_result(self, tool_use_id: str, result: Any) -> None:
        """添加 Tool 执行结果.

        Args:
            tool_use_id: Tool Use ID
            result: 执行结果
        """
        # Claude 格式
        self.messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": str(result),
                    }
                ],
            }
        )

    def get_messages(self) -> list[dict[str, Any]]:
        """获取所有消息（包含系统提示）.

        Returns:
            消息列表
        """
        # 将系统提示作为第一条消息
        system_msg = {"role": "system", "content": self.system_prompt}
        return [system_msg] + self.messages

    def clear(self) -> None:
        """清空会话."""
        self.messages = []
