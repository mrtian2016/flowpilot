"""配置加载器."""

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import ValidationError

from .schema import FlowPilotConfig


class ConfigLoader:
    """配置加载器，支持 YAML + 环境变量."""

    DEFAULT_CONFIG_DIR = Path.home() / ".flowpilot"
    DEFAULT_CONFIG_FILE = "config.yaml"

    def __init__(self, config_path: Path | str | None = None) -> None:
        """初始化配置加载器.

        Args:
            config_path: 配置文件路径，默认为 ~/.flowpilot/config.yaml
        """
        if config_path:
            self.config_path = Path(config_path)
        else:
            self.config_path = self.DEFAULT_CONFIG_DIR / self.DEFAULT_CONFIG_FILE

        # 加载 .env 文件（优先级：项目根目录 > ~/.flowpilot）
        self._load_env()

    def _load_env(self) -> None:
        """加载环境变量."""
        # 1. 尝试从 ~/.flowpilot/.env 加载
        env_file = self.DEFAULT_CONFIG_DIR / ".env"
        if env_file.exists():
            load_dotenv(env_file)

        # 2. 尝试从当前工作目录加载（覆盖优先级更高）
        cwd_env = Path.cwd() / ".env"
        if cwd_env.exists():
            load_dotenv(cwd_env, override=True)

    def load(self) -> FlowPilotConfig:
        """加载并校验配置.

        Returns:
            解析后的配置对象

        Raises:
            FileNotFoundError: 配置文件不存在
            ValueError: 配置格式错误或校验失败
        """
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"配置文件不存在: {self.config_path}\n"
                f"请运行 'flowpilot init' 初始化配置，或手动创建配置文件。"
            )

        try:
            with open(self.config_path, encoding="utf-8") as f:
                raw_config = yaml.safe_load(f)

            if not isinstance(raw_config, dict):
                raise ValueError("配置文件格式错误：根节点必须是字典")

            # 使用 Pydantic 校验
            config = FlowPilotConfig(**raw_config)
            return config

        except yaml.YAMLError as e:
            raise ValueError(f"YAML 解析失败: {e}") from e
        except ValidationError as e:
            # 友好的错误提示
            errors = []
            for error in e.errors():
                loc = " -> ".join(str(x) for x in error["loc"])
                msg = error["msg"]
                errors.append(f"  - {loc}: {msg}")

            raise ValueError(
                f"配置校验失败，请检查以下字段:\n" + "\n".join(errors)
            ) from e

    def validate(self) -> tuple[bool, str]:
        """校验配置文件.

        Returns:
            (是否有效, 错误信息或成功提示)
        """
        try:
            self.load()
            return True, f"✅ 配置文件有效: {self.config_path}"
        except FileNotFoundError as e:
            return False, f"❌ {e}"
        except ValueError as e:
            return False, f"❌ {e}"

    @staticmethod
    def get_api_key(env_var: str) -> str | None:
        """从环境变量获取 API Key.

        Args:
            env_var: 环境变量名

        Returns:
            API Key 或 None
        """
        return os.getenv(env_var)


def load_config(config_path: Path | str | None = None) -> FlowPilotConfig:
    """快捷函数：加载配置.

    Args:
        config_path: 配置文件路径

    Returns:
        配置对象
    """
    loader = ConfigLoader(config_path)
    return loader.load()
