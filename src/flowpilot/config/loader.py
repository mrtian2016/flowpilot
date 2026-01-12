"""配置加载器."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from sqlalchemy.orm import Session

# Import DB modules
from flowpilot.core.db import DB_FILE, SessionLocal, init_db
from flowpilot.core.models import (
    Host as DBHost,
)
from flowpilot.core.models import (
    JumpConfig as DBJumpConfig,
)
from flowpilot.core.models import (
    LLMConfig as DBLLMConfig,
)
from flowpilot.core.models import (
    PolicyRule as DBPolicyRule,
)
from flowpilot.core.models import (
    Service as DBService,
)

from .schema import (
    FlowPilotConfig,
    HostConfig,
    JumpConfig,
    LLMConfig,
    LLMProviderConfig,
    PolicyCondition,
    PolicyRule,
    RoutingRule,
    ServiceConfig,
)


class ConfigLoader:
    """配置加载器，支持 YAML + SQLite 混合模式 (DB 覆盖 YAML)."""

    DEFAULT_CONFIG_DIR = Path.home() / ".flowpilot"
    DEFAULT_CONFIG_FILE = "config.yaml"

    def __init__(self, config_path: Path | str | None = None) -> None:
        """初始化配置加载器.

        Args:
           config_path: 自定义配置文件路径
        """
        if config_path:
            self.config_path = Path(config_path)
        else:
            # 优先检查当前目录
            cwd_config = Path.cwd() / self.DEFAULT_CONFIG_FILE
            if cwd_config.exists():
                self.config_path = cwd_config
            else:
                self.config_path = self.DEFAULT_CONFIG_DIR / self.DEFAULT_CONFIG_FILE

        # 确保 DB 初始化
        if not DB_FILE.exists():
            init_db()

        # 加载 .env 文件
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
        """加载并合并配置 (YAML + DB)."""
        # 1. 加载 YAML 配置
        yaml_config = self._load_yaml()

        # 2. 加载 DB 配置
        with SessionLocal() as db:
            db_config = self._db_to_config(db)

        # 3. 合并配置 (DB 覆盖 YAML)
        return self._merge_configs(yaml_config, db_config)

    def _load_yaml(self) -> FlowPilotConfig | None:
        """加载 YAML 配置文件."""
        if not self.config_path.exists():
            return None

        try:
            content = self.config_path.read_text(encoding="utf-8")
            data = yaml.safe_load(content)
            if not data:
                return None
            return FlowPilotConfig(**data)
        except Exception as e:
            # YAML 加载失败不应阻断 DB 加载，但应警告
            print(f"⚠️  YAML 配置文件加载失败: {e}")
            return None

    def _merge_configs(
        self, base: FlowPilotConfig | None, override: FlowPilotConfig
    ) -> FlowPilotConfig:
        """合并配置，override 覆盖 base."""
        if base is None:
            return override

        # 1. Host 合并 (Dict merge)
        hosts = base.hosts.copy()
        hosts.update(override.hosts)

        # 2. Jumps 合并 (Dict merge)
        jumps = base.jumps.copy()
        jumps.update(override.jumps)

        # 3. Services 合并 (Dict merge)
        services = base.services.copy()
        services.update(override.services)

        # 4. LLM Config 合并
        # 如果 DB 中 default_provider 为默认 'claude' 且无 providers，认为 DB 未配置 LLM
        # 这里逻辑稍微复杂，简单起见：如果 DB 配置了 providers，则完全使用 DB 的 LLM 配置，否则优先使用 YAML
        # 但为了支持部分覆盖，我们也可以做深层合并。
        # 这里采用策略：如果 DB 有 providers，则合并 providers；default_provider 优先 DB
        llm = base.llm
        if override.llm.providers:
            providers = llm.providers.copy()
            providers.update(override.llm.providers)

            # 合并 routing rules
            routing = llm.routing + override.llm.routing

            # 只有当 DB 设置了非默认值时才覆盖 default_provider (这很难判断，假设 DB 总是权威)
            # 或者简单点：如果 DB 有 provider，就信任 DB 的 default_provider
            default_provider = override.llm.default_provider

            llm = LLMConfig(default_provider=default_provider, providers=providers, routing=routing)

        # 5. Policies 合并 (按 name 去重，override 覆盖 base)
        policies_dict = {p.name: p for p in base.policies}
        for p in override.policies:
            policies_dict[p.name] = p
        policies = list(policies_dict.values())

        return FlowPilotConfig(
            llm=llm, hosts=hosts, jumps=jumps, services=services, policies=policies
        )

    def _db_to_config(self, db: Session) -> FlowPilotConfig:
        """Convert DB models to Pydantic Schema."""

        # 1. LLM Config
        db_llm = db.query(DBLLMConfig).first()
        if not db_llm:
            # Default empty config if not found
            llm_config = LLMConfig(default_provider="claude", providers={}, routing=[])
        else:
            providers = {}
            for p in db_llm.providers:
                providers[p.name] = LLMProviderConfig(
                    model=p.model,
                    api_key_env=p.api_key_env,
                    max_tokens=p.max_tokens,
                    temperature=p.temperature,
                )

            routing = []
            for r in db_llm.routing_rules:
                routing.append(
                    RoutingRule(
                        scenario=r.scenario,
                        provider=r.provider,
                        model=r.model,
                        condition=r.condition,
                    )
                )

            llm_config = LLMConfig(
                default_provider=db_llm.default_provider, providers=providers, routing=routing
            )

        # 2. Hosts
        hosts = {}
        for h in db.query(DBHost).all():
            hosts[h.name] = HostConfig(
                env=h.env,
                user=h.user,
                addr=h.addr,
                port=h.port,
                jump=h.jump,
                tags=[t.name for t in h.tags],
                ssh_key=h.ssh_key,
                group=h.group if hasattr(h, "group") else None,  # handle optional attribute
                description=h.description,
            )

        # 3. Jumps
        jumps = {}
        for j in db.query(DBJumpConfig).all():
            jumps[j.name] = JumpConfig(addr=j.addr, user=j.user, port=j.port)

        # 4. Services
        services = {}
        for s in db.query(DBService).all():
            # config_json contains the rest of the fields
            services[s.name] = ServiceConfig(description=s.description, **s.config_json)

        # 5. Policies
        policies = []
        for p in db.query(DBPolicyRule).all():
            policies.append(
                PolicyRule(
                    name=p.name,
                    condition=PolicyCondition(**p.condition) if p.condition else PolicyCondition(),
                    effect=p.effect,
                    message=p.message,
                )
            )

        return FlowPilotConfig(
            llm=llm_config, hosts=hosts, jumps=jumps, services=services, policies=policies
        )

    def validate(self) -> tuple[bool, str]:
        """校验配置."""
        try:
            self.load()
            return True, "✅ 配置加载正常 (YAML + DB)"
        except Exception as e:
            return False, f"❌ 配置加载失败: {e}"

    @staticmethod
    def get_api_key(env_var: str) -> str | None:
        """从环境变量获取 API Key."""
        return os.getenv(env_var)


def load_config(config_path: Path | str | None = None) -> FlowPilotConfig:
    """快捷函数：加载配置."""
    loader = ConfigLoader(config_path)
    return loader.load()
