"""命令分类器 - 判断操作类型."""

import re
from enum import Enum


class ActionType(str, Enum):
    """操作类型枚举."""

    READ = "read"  # 只读操作
    WRITE = "write"  # 写操作（修改数据）
    DESTRUCTIVE = "destructive"  # 破坏性操作（不可逆）


# 破坏性操作关键词（高风险）
DESTRUCTIVE_KEYWORDS = [
    r"rm\s+-rf\s+/",  # 删除根目录
    r"mkfs",  # 格式化文件系统
    r"dd\s+if=",  # 磁盘克隆/覆盖
    r"shutdown",  # 关机
    r"reboot",  # 重启
    r"halt",  # 停机
    r"init\s+0",  # 关机
    r"init\s+6",  # 重启
    r"systemctl\s+poweroff",  # 关机
    r"systemctl\s+reboot",  # 重启
    r"\>\/dev\/sd[a-z]",  # 直接写磁盘设备
    r"wipefs",  # 擦除文件系统签名
    r"fdisk.*-w",  # 写入分区表
]

# 写操作关键词（中风险）
WRITE_KEYWORDS = [
    r"rm\s+",  # 删除文件
    r"mv\s+",  # 移动/重命名
    r"cp\s+.*\s+/",  # 复制到系统目录
    r"\>",  # 重定向（覆盖）
    r"\>\>",  # 追加
    r"systemctl\s+stop",  # 停止服务
    r"systemctl\s+disable",  # 禁用服务
    r"kill\s+-9",  # 强制结束进程
    r"pkill",  # 批量结束进程
    r"chmod",  # 修改权限
    r"chown",  # 修改所有者
    r"service\s+\w+\s+stop",  # 停止服务
    r"docker\s+rm",  # 删除容器
    r"docker\s+stop",  # 停止容器
    r"kubectl\s+delete",  # 删除 K8s 资源
    r"sed\s+-i",  # 原地编辑文件
    r"truncate",  # 截断文件
]


def classify_command(command: str) -> ActionType:
    """分类命令类型.

    Args:
        command: 要执行的命令

    Returns:
        操作类型
    """
    command_lower = command.lower().strip()

    # 检查破坏性操作
    for pattern in DESTRUCTIVE_KEYWORDS:
        if re.search(pattern, command_lower, re.IGNORECASE):
            return ActionType.DESTRUCTIVE

    # 检查写操作
    for pattern in WRITE_KEYWORDS:
        if re.search(pattern, command_lower, re.IGNORECASE):
            return ActionType.WRITE

    # 默认为只读操作
    return ActionType.READ


def is_destructive(command: str) -> bool:
    """判断是否为破坏性操作.

    Args:
        command: 命令

    Returns:
        是否为破坏性操作
    """
    return classify_command(command) == ActionType.DESTRUCTIVE


def is_write_operation(command: str) -> bool:
    """判断是否为写操作.

    Args:
        command: 命令

    Returns:
        是否为写操作（含破坏性）
    """
    action_type = classify_command(command)
    return action_type in [ActionType.WRITE, ActionType.DESTRUCTIVE]


def get_risk_level(command: str, env: str = "dev") -> str:
    """获取操作风险级别.

    Args:
        command: 命令
        env: 环境（dev/staging/prod）

    Returns:
        风险级别: low/medium/high/critical
    """
    action_type = classify_command(command)

    # 破坏性操作在生产环境为 critical
    if action_type == ActionType.DESTRUCTIVE:
        return "critical" if env == "prod" else "high"

    # 写操作在生产环境为 high
    if action_type == ActionType.WRITE:
        return "high" if env == "prod" else "medium"

    # 读操作为 low
    return "low"
