"""YAML 配置导入器."""

from pathlib import Path
import yaml
from sqlalchemy.orm import Session

from flowpilot.core.db import SessionLocal
from flowpilot.core.models import (
    LLMConfig,
    LLMProvider,
    RoutingRule,
    Host,
    JumpConfig,
    Service,
    PolicyRule,
    Tag,
)


def import_yaml_to_db(yaml_path: Path) -> None:
    """Import YAML configuration into the database."""
    if not yaml_path.exists():
        raise FileNotFoundError(f"Config file not found: {yaml_path}")

    with open(yaml_path, encoding="utf-8") as f:
        raw_config = yaml.safe_load(f)

    with SessionLocal() as db:
        _import_llm(db, raw_config.get("llm", {}))
        _import_hosts(db, raw_config.get("hosts", {}))
        _import_jumps(db, raw_config.get("jumps", {}))
        _import_services(db, raw_config.get("services", {}))
        _import_policies(db, raw_config.get("policies", []))
        
        db.commit()


def _get_or_create_tags(db: Session, tag_names: list[str]) -> list[Tag]:
    tags = []
    for name in tag_names:
        tag = db.query(Tag).filter_by(name=name).first()
        if not tag:
            tag = Tag(name=name)
            db.add(tag)
        tags.append(tag)
    return tags


def _import_llm(db: Session, llm_data: dict) -> None:
    """Import LLM config."""
    db.query(LLMConfig).delete()
    
    llm_config = LLMConfig(
        default_provider=llm_data.get("default_provider", "claude")
    )
    db.add(llm_config)
    db.flush()  # Get ID

    # Providers
    for name, p_data in llm_data.get("providers", {}).items():
        provider = LLMProvider(
            llm_config_id=llm_config.id,
            name=name,
            model=p_data["model"],
            api_key_env=p_data["api_key_env"],
            max_tokens=p_data.get("max_tokens", 4096),
            temperature=p_data.get("temperature", 0.7),
        )
        db.add(provider)

    # Routing
    for r_data in llm_data.get("routing", []):
        rule = RoutingRule(
            llm_config_id=llm_config.id,
            scenario=r_data["scenario"],
            provider=r_data["provider"],
            model=r_data.get("model"),
            condition=r_data.get("condition"),
        )
        db.add(rule)


def _import_hosts(db: Session, hosts_data: dict) -> None:
    """Import Hosts."""
    # Assuming update/overwrite logic: Clear existing with same name or just update?
    # For now, let's check existence
    for name, h_data in hosts_data.items():
        host = db.query(Host).filter_by(name=name).first()
        if not host:
            host = Host(name=name)
            db.add(host)
        
        host.env = h_data["env"]
        host.user = h_data["user"]
        host.addr = h_data["addr"]
        host.port = h_data.get("port", 22)
        host.jump = h_data.get("jump")
        host.ssh_key = h_data.get("ssh_key")
        host.description = h_data.get("description", "")
        host.group = h_data.get("group", "default")
        
        # Tags
        tag_names = h_data.get("tags", [])
        host.tags = _get_or_create_tags(db, tag_names)


def _import_jumps(db: Session, jumps_data: dict) -> None:
    """Import Jump Hosts."""
    for name, j_data in jumps_data.items():
        jump = db.query(JumpConfig).filter_by(name=name).first()
        if not jump:
            jump = JumpConfig(name=name)
            db.add(jump)
        
        jump.addr = j_data["addr"]
        jump.user = j_data["user"]
        jump.port = j_data.get("port", 22)


def _import_services(db: Session, services_data: dict) -> None:
    """Import Services."""
    for name, s_data in services_data.items():
        service = db.query(Service).filter_by(name=name).first()
        if not service:
            service = Service(name=name)
            db.add(service)
        
        service.description = s_data.get("description", "")
        
        # Remove description from json blob to avoid duplication if desired, 
        # but technically s_data is the source
        config = s_data.copy()
        if "description" in config:
            del config["description"]
            
        service.config_json = config


def _import_policies(db: Session, policies_data: list) -> None:
    """Import Policies."""
    # Policy names should be unique.
    for p_data in policies_data:
        name = p_data["name"]
        policy = db.query(PolicyRule).filter_by(name=name).first()
        if not policy:
            policy = PolicyRule(name=name)
            db.add(policy)
            
        policy.condition = p_data["condition"]
        policy.effect = p_data["effect"]
        policy.message = p_data["message"]
