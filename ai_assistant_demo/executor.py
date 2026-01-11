"""AI 助手工具执行器模块"""
import time
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from app.models.rule import RuleConfig
from app.models.proxy_group import ProxyGroupConfig
from app.models.proxy import ProxyConfig
from app.models.host import HostConfig
from app.models.general import GeneralConfig
from app.models.ai_audit_log import AIAuditLog
from app.models.config_version import ConfigVersion
from app.models.wireguard import WireGuardConfig
from app.models.wireguard_peer_service import WireGuardPeerService
from app.models.rule_set import RuleSet, RuleSetItem
from app.models.device import Device
from app.utils.transaction import with_transaction


class ToolExecutor:
    """工具执行器，处理 AI 的工具调用"""

    def __init__(self, db: Session, current_user):
        self.db = db
        self.current_user = current_user  # 用于审计日志
        self._cache_data = None  # 配置上下文缓存
        self._cache_timestamp = 0  # 缓存时间戳
        self.CACHE_TTL = 60  # 缓存有效期（秒）

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """执行工具调用（带审计日志）"""
        start_time = time.time()
        result = None

        handler = getattr(self, f"_handle_{tool_name}", None)
        if not handler:
            result = {"success": False, "message": f"未知的工具: {tool_name}"}
        else:
            try:
                result = handler(arguments)
            except Exception as e:
                logger.error(f"工具执行失败: {tool_name}, 错误: {e}", exc_info=True)
                result = {"success": False, "message": f"执行失败: {str(e)}"}

        # 计算执行时间
        execution_time_ms = int((time.time() - start_time) * 1000)

        # 记录审计日志
        try:
            audit_log = AIAuditLog(
                user_id=self.current_user.id,
                tool_name=tool_name,
                arguments=arguments,
                result=result,
                success=result.get("success", False),
                error_message=None if result.get("success") else result.get("message"),
                execution_time_ms=execution_time_ms
            )
            self.db.add(audit_log)
            self.db.commit()
        except Exception as e:
            logger.error(f"审计日志记录失败: {e}", exc_info=True)
            # 审计日志失败不应该影响工具执行结果

        return result

    def _model_to_dict(self, obj) -> dict:
        """将 SQLAlchemy 模型对象转换为字典（用于版本记录）"""
        if obj is None:
            return None

        result = {}
        for column in obj.__table__.columns:
            value = getattr(obj, column.name)
            # 处理特殊类型
            if hasattr(value, 'isoformat'):  # datetime
                result[column.name] = value.isoformat()
            else:
                result[column.name] = value
        return result

    def _save_version(
        self,
        resource_type: str,
        resource_id: int,
        operation_type: str,
        before_data: dict | None = None,
        after_data: dict | None = None
    ):
        """保存配置版本记录"""
        try:
            version = ConfigVersion(
                user_id=self.current_user.id,
                resource_type=resource_type,
                resource_id=resource_id,
                operation_type=operation_type,
                before_data=before_data,
                after_data=after_data
            )
            self.db.add(version)
            self.db.commit()
            logger.debug(f"版本记录已保存: {resource_type} ID {resource_id}, 操作: {operation_type}")
        except Exception as e:
            logger.error(f"保存版本记录失败: {e}", exc_info=True)
            # 版本记录失败不应该影响主操作

    def _handle_create_rule(self, args: dict[str, Any]) -> dict[str, Any]:
        """创建规则"""
        rule_type = args.get("rule_type")
        value = args.get("value")
        policy = args.get("policy")
        comment = args.get("comment", "")

        if not all([rule_type, value, policy]):
            return {"success": False, "message": "缺少必要参数: rule_type, value, policy"}

        # 获取当前最大排序值
        max_order = self.db.query(RuleConfig).filter(
            RuleConfig.device_id.is_(None)
        ).count()

        config = RuleConfig(
            device_id=None,
            rule_type=rule_type,
            value=value,
            policy=policy,
            comment=comment,
            sort_order=max_order,
        )
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)

        # 保存版本记录
        self._save_version(
            resource_type="rule",
            resource_id=config.id,
            operation_type="create",
            before_data=None,
            after_data=self._model_to_dict(config)
        )

        return {
            "success": True,
            "message": f"成功创建规则: {rule_type},{value},{policy}",
            "data": {
                "id": config.id,
                "rule_type": config.rule_type,
                "value": config.value,
                "policy": config.policy,
            }
        }

    def _handle_list_rules(self, args: dict[str, Any]) -> dict[str, Any]:
        """查询规则列表"""
        keyword = args.get("keyword", "").lower()
        limit = args.get("limit", 20)

        query = self.db.query(RuleConfig).filter(RuleConfig.device_id.is_(None))

        # 如果有关键词，使用数据库 LIKE 查询（性能优化）
        if keyword:
            search_pattern = f"%{keyword}%"
            query = query.filter(
                (RuleConfig.value.like(search_pattern)) |
                (RuleConfig.policy.like(search_pattern)) |
                (RuleConfig.comment.like(search_pattern))
            )

        rules = query.order_by(RuleConfig.sort_order).limit(limit).all()

        if not rules:
            return {
                "success": True,
                "message": f"未找到包含 '{keyword}' 的规则" if keyword else "暂无规则",
                "data": []
            }

        # 构建详细的规则信息
        rules_info = []
        for r in rules:
            rules_info.append({
                "id": r.id,
                "rule_type": r.rule_type,
                "value": r.value,
                "policy": r.policy,
                "comment": r.comment,
            })

        # 构建更清晰的表格样式文本
        lines = [f"📋 查询到 {len(rules)} 条规则" + (f"（关键词: {keyword}）" if keyword else "") + "：", ""]
        for r in rules:
            # 显示完整的 value（便于 AI 提取 IP/域名）
            line = f"#{r.id}  {r.rule_type}  →  {r.policy}"
            lines.append(line)
            lines.append(f"    value: {r.value}")
            if r.comment:
                lines.append(f"    💬 {r.comment}")
            lines.append("")  # 空行分隔

        return {
            "success": True,
            "message": "\n".join(lines),
            "data": rules_info
        }


    def _handle_delete_rule(self, args: dict[str, Any]) -> dict[str, Any]:
        """删除规则"""
        rule_id = args.get("rule_id")
        if not rule_id:
            return {"success": False, "message": "缺少 rule_id 参数"}

        config = self.db.query(RuleConfig).filter(
            RuleConfig.id == rule_id,
            RuleConfig.device_id.is_(None)
        ).first()

        if not config:
            return {"success": False, "message": f"规则 ID {rule_id} 不存在"}

        # 保存版本记录（删除前）
        before_data = self._model_to_dict(config)

        self.db.delete(config)
        self.db.commit()

        # 保存版本记录
        self._save_version(
            resource_type="rule",
            resource_id=rule_id,
            operation_type="delete",
            before_data=before_data,
            after_data=None
        )

        return {"success": True, "message": f"成功删除规则 ID {rule_id}"}

    def _handle_list_proxy_groups(self, args: dict[str, Any]) -> dict[str, Any]:
        """获取策略组列表"""
        groups = (
            self.db.query(ProxyGroupConfig)
            .filter(ProxyGroupConfig.device_id.is_(None))
            .all()
        )
        # 添加内置策略
        result = [
            {"name": "DIRECT", "type": "内置", "description": "直接连接"},
            {"name": "REJECT", "type": "内置", "description": "拒绝连接"},
        ]
        result.extend([
            {"name": g.name, "type": g.group_type, "description": g.name}
            for g in groups
        ])
        return {
            "success": True,
            "message": f"共 {len(result)} 个可用策略",
            "data": result
        }

    def _handle_update_rule(self, args: dict[str, Any]) -> dict[str, Any]:
        """修改规则"""
        rule_id = args.get("rule_id")
        if not rule_id:
            return {"success": False, "message": "缺少 rule_id 参数"}

        config = self.db.query(RuleConfig).filter(
            RuleConfig.id == rule_id,
            RuleConfig.device_id.is_(None)
        ).first()

        if not config:
            return {"success": False, "message": f"规则 ID {rule_id} 不存在"}

        # 保存更新前的数据
        before_data = self._model_to_dict(config)
        update_fields = []

        # 更新策略
        if "policy" in args and args["policy"]:
            config.policy = args["policy"]
            update_fields.append("策略")
        # 更新注释
        if "comment" in args:
            config.comment = args["comment"]
            update_fields.append("注释")
        # 更新排序
        if "sort_order" in args and args["sort_order"] is not None:
            config.sort_order = args["sort_order"]
            update_fields.append("排序")

        if not update_fields:
            return {"success": False, "message": "❌ 未提供任何要更新的字段"}

        self.db.commit()
        self.db.refresh(config)

        # 保存版本记录
        self._save_version(
            resource_type="rule",
            resource_id=rule_id,
            operation_type="update",
            before_data=before_data,
            after_data=self._model_to_dict(config)
        )

        return {
            "success": True,
            "message": f"成功更新规则 ID {rule_id} ({', '.join(update_fields)}): {config.rule_type},{config.value},{config.policy}",
            "data": {
                "id": config.id,
                "rule_type": config.rule_type,
                "value": config.value,
                "policy": config.policy,
                "comment": config.comment,
                "sort_order": config.sort_order,
            }
        }

    def _handle_list_proxies(self, args: dict[str, Any]) -> dict[str, Any]:
        """查询代理节点列表"""
        keyword = args.get("keyword", "").lower()

        proxies = (
            self.db.query(ProxyConfig)
            .filter(ProxyConfig.device_id.is_(None), ProxyConfig.is_active == True)
            .all()
        )

        if keyword:
            proxies = [p for p in proxies if keyword in p.name.lower()]

        if not proxies:
            return {
                "success": True,
                "message": "未找到代理节点" if not keyword else f"未找到包含 '{keyword}' 的代理",
                "data": []
            }

        proxy_info = [
            {
                "name": p.name,
                "protocol": p.protocol,
                "server": f"{p.server}:{p.port}" if p.server else "外部引用",
            }
            for p in proxies[:20]
        ]

        return {
            "success": True,
            "message": f"共 {len(proxies)} 个代理节点",
            "data": proxy_info
        }

    def _handle_list_hosts(self, args: dict[str, Any]) -> dict[str, Any]:
        """查询主机映射列表"""
        keyword = args.get("keyword", "").lower()

        hosts = (
            self.db.query(HostConfig)
            .filter(HostConfig.device_id.is_(None), HostConfig.is_active == True)
            .all()
        )

        if keyword:
            hosts = [h for h in hosts if keyword in h.hostname.lower() or keyword in (h.target or "").lower()]

        if not hosts:
            return {"success": True, "message": "暂无主机映射", "data": []}

        lines = [f"📍 共 {len(hosts)} 条主机映射：", ""]
        for h in hosts[:15]:
            lines.append(f"#{h.id}  {h.hostname}  →  {h.target}")
            if h.description:
                lines.append(f"    💬 {h.description}")
            lines.append("")

        return {"success": True, "message": "\n".join(lines), "data": [{"id": h.id, "hostname": h.hostname, "target": h.target} for h in hosts]}

    def _handle_create_host(self, args: dict[str, Any]) -> dict[str, Any]:
        """创建主机映射"""
        hostname = args.get("hostname")
        target = args.get("target")
        description = args.get("description", "")

        if not hostname or not target:
            return {"success": False, "message": "缺少 hostname 或 target 参数"}

        host = HostConfig(
            device_id=None,
            hostname=hostname,
            target=target,
            description=description,
        )
        self.db.add(host)
        self.db.commit()
        self.db.refresh(host)

        # 保存版本记录
        self._save_version(
            resource_type="host",
            resource_id=host.id,
            operation_type="create",
            before_data=None,
            after_data=self._model_to_dict(host)
        )

        return {
            "success": True,
            "message": f"✅ 成功创建主机映射：{hostname} → {target}",
            "data": {"id": host.id, "hostname": host.hostname, "target": host.target}
        }

    def _handle_delete_host(self, args: dict[str, Any]) -> dict[str, Any]:
        """删除主机映射"""
        host_id = args.get("host_id")
        if not host_id:
            return {"success": False, "message": "缺少 host_id 参数"}

        host = self.db.query(HostConfig).filter(HostConfig.id == host_id).first()
        if not host:
            return {"success": False, "message": f"主机映射 ID {host_id} 不存在"}

        # 保存版本记录（删除前）
        before_data = self._model_to_dict(host)
        hostname = host.hostname

        self.db.delete(host)
        self.db.commit()

        # 保存版本记录
        self._save_version(
            resource_type="host",
            resource_id=host_id,
            operation_type="delete",
            before_data=before_data,
            after_data=None
        )

        return {"success": True, "message": f"✅ 成功删除主机映射：{hostname}"}

    def _handle_list_general_configs(self, args: dict[str, Any]) -> dict[str, Any]:
        """查询通用配置列表"""
        keyword = args.get("keyword", "").lower()

        configs = (
            self.db.query(GeneralConfig)
            .filter(GeneralConfig.device_id.is_(None), GeneralConfig.is_active == True)
            .order_by(GeneralConfig.sort_order)
            .all()
        )

        if keyword:
            configs = [c for c in configs if keyword in c.key.lower() or keyword in (c.value or "").lower()]

        if not configs:
            return {"success": True, "message": "暂无通用配置", "data": []}

        lines = [f"⚙️ 共 {len(configs)} 项通用配置：", ""]
        for c in configs[:20]:
            value = c.value[:50] + "..." if len(c.value or "") > 50 else c.value
            lines.append(f"#{c.id}  {c.key} = {value}")
            lines.append("")

        return {"success": True, "message": "\n".join(lines), "data": [{"id": c.id, "key": c.key, "value": c.value} for c in configs]}

    def _handle_update_general_config(self, args: dict[str, Any]) -> dict[str, Any]:
        """修改通用配置"""
        key = args.get("key")
        value = args.get("value")

        if not key or value is None:
            return {"success": False, "message": "缺少 key 或 value 参数"}

        config = self.db.query(GeneralConfig).filter(
            GeneralConfig.device_id.is_(None),
            GeneralConfig.key == key
        ).first()

        if not config:
            # 创建新配置
            config = GeneralConfig(device_id=None, key=key, value=value)
            self.db.add(config)
            self.db.commit()
            self.db.refresh(config)

            # 保存版本记录
            self._save_version(
                resource_type="general_config",
                resource_id=config.id,
                operation_type="create",
                before_data=None,
                after_data=self._model_to_dict(config)
            )

            return {"success": True, "message": f"✅ 成功创建配置：{key} = {value}"}
        else:
            # 更新现有配置
            before_data = self._model_to_dict(config)
            old_value = config.value
            config.value = value
            self.db.commit()
            self.db.refresh(config)

            # 保存版本记录
            self._save_version(
                resource_type="general_config",
                resource_id=config.id,
                operation_type="update",
                before_data=before_data,
                after_data=self._model_to_dict(config)
            )

            return {"success": True, "message": f"✅ 成功更新配置：{key}\n旧值：{old_value}\n新值：{value}"}

    def _handle_get_config_summary(self, args: dict[str, Any]) -> dict[str, Any]:
        """获取配置摘要"""
        return {
            "success": True,
            "message": self.get_config_context(),
            "data": {}
        }

    def _handle_batch_replace_policy(self, args: dict[str, Any]) -> dict[str, Any]:
        """批量替换规则中的策略"""
        old_policy = args.get("old_policy")
        new_policy = args.get("new_policy")
        dry_run = args.get("dry_run", False)

        if not old_policy or not new_policy:
            return {"success": False, "message": "缺少 old_policy 或 new_policy 参数"}

        # 查找所有使用旧策略的规则
        rules = (
            self.db.query(RuleConfig)
            .filter(
                RuleConfig.device_id.is_(None),
                RuleConfig.policy == old_policy
            )
            .all()
        )

        if not rules:
            return {
                "success": True,
                "message": f"未找到使用策略 '{old_policy}' 的规则",
                "data": {"affected_count": 0}
            }

        # 预览或执行
        if dry_run:
            lines = [f"🔍 预览：将替换 {len(rules)} 条规则的策略（{old_policy} → {new_policy}）：", ""]
            for r in rules[:20]:
                value = r.value[:40] + "..." if len(r.value or "") > 40 else r.value
                lines.append(f"  [ID:{r.id}] {r.rule_type}, {value}")
            if len(rules) > 20:
                lines.append(f"  ... 还有 {len(rules) - 20} 条规则")
            return {
                "success": True,
                "message": "\n".join(lines),
                "data": {"affected_count": len(rules), "preview": True}
            }
        else:
            # 执行批量更新
            for rule in rules:
                rule.policy = new_policy
            self.db.commit()

            return {
                "success": True,
                "message": f"✅ 成功将 {len(rules)} 条规则的策略从 '{old_policy}' 替换为 '{new_policy}'",
                "data": {"affected_count": len(rules)}
            }

    def _handle_create_proxy_group(self, args: dict[str, Any]) -> dict[str, Any]:
        """创建代理组"""
        name = args.get("name")
        group_type = args.get("group_type")
        members = args.get("members", [])
        description = args.get("description", "")

        if not name or not group_type:
            return {"success": False, "message": "❌ 缺少必要参数: name, group_type"}

        # 检查名称是否已存在
        existing = (
            self.db.query(ProxyGroupConfig)
            .filter(ProxyGroupConfig.device_id.is_(None), ProxyGroupConfig.name == name)
            .first()
        )
        if existing:
            return {"success": False, "message": f"❌ 代理组 '{name}' 已存在"}

        # 获取当前最大排序值
        max_order = self.db.query(ProxyGroupConfig).filter(
            ProxyGroupConfig.device_id.is_(None)
        ).count()

        config = ProxyGroupConfig(
            device_id=None,
            name=name,
            group_type=group_type,
            members=members,
            description=description,
            sort_order=max_order,
        )
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)

        # 保存版本记录
        self._save_version(
            resource_type="proxy_group",
            resource_id=config.id,
            operation_type="create",
            before_data=None,
            after_data=self._model_to_dict(config)
        )

        return {
            "success": True,
            "message": f"✅ 成功创建代理组: {name} ({group_type})",
            "data": {
                "id": config.id,
                "name": config.name,
                "group_type": config.group_type,
                "members": config.members,
            }
        }

    def _handle_update_proxy_group(self, args: dict[str, Any]) -> dict[str, Any]:
        """更新代理组"""
        group_id = args.get("group_id")
        if not group_id:
            return {"success": False, "message": "❌ 缺少 group_id 参数"}

        config = (
            self.db.query(ProxyGroupConfig)
            .filter(ProxyGroupConfig.id == group_id, ProxyGroupConfig.device_id.is_(None))
            .first()
        )
        if not config:
            return {"success": False, "message": f"❌ 代理组 ID {group_id} 不存在"}

        # 检查名称冲突
        new_name = args.get("name")
        if new_name and new_name != config.name:
            existing = (
                self.db.query(ProxyGroupConfig)
                .filter(
                    ProxyGroupConfig.device_id.is_(None),
                    ProxyGroupConfig.name == new_name,
                    ProxyGroupConfig.id != group_id
                )
                .first()
            )
            if existing:
                return {"success": False, "message": f"❌ 代理组名称 '{new_name}' 已被使用"}

        # 保存更新前的数据
        before_data = self._model_to_dict(config)

        # 更新字段
        update_fields = []
        if new_name:
            config.name = new_name
            update_fields.append("名称")
        if "group_type" in args:
            config.group_type = args["group_type"]
            update_fields.append("类型")
        if "members" in args:
            config.members = args["members"]
            update_fields.append("成员")
        if "description" in args:
            config.description = args["description"]
            update_fields.append("描述")

        if not update_fields:
            return {"success": False, "message": "❌ 未提供任何要更新的字段"}

        self.db.commit()
        self.db.refresh(config)

        # 保存版本记录
        self._save_version(
            resource_type="proxy_group",
            resource_id=group_id,
            operation_type="update",
            before_data=before_data,
            after_data=self._model_to_dict(config)
        )

        return {
            "success": True,
            "message": f"✅ 成功更新代理组 '{config.name}' ({', '.join(update_fields)})",
            "data": {
                "id": config.id,
                "name": config.name,
                "group_type": config.group_type,
                "members": config.members,
            }
        }

    def _handle_delete_proxy_group(self, args: dict[str, Any]) -> dict[str, Any]:
        """删除代理组"""
        group_id = args.get("group_id")
        if not group_id:
            return {"success": False, "message": "❌ 缺少 group_id 参数"}

        config = (
            self.db.query(ProxyGroupConfig)
            .filter(ProxyGroupConfig.id == group_id, ProxyGroupConfig.device_id.is_(None))
            .first()
        )
        if not config:
            return {"success": False, "message": f"❌ 代理组 ID {group_id} 不存在"}

        # 检查是否被规则引用
        group_name = config.name
        referenced_rules = (
            self.db.query(RuleConfig)
            .filter(RuleConfig.device_id.is_(None), RuleConfig.policy == group_name)
            .count()
        )
        if referenced_rules > 0:
            return {
                "success": False,
                "message": f"❌ 无法删除代理组 '{group_name}'，有 {referenced_rules} 条规则正在使用"
            }

        # 保存版本记录（删除前）
        before_data = self._model_to_dict(config)

        self.db.delete(config)
        self.db.commit()

        # 保存版本记录
        self._save_version(
            resource_type="proxy_group",
            resource_id=group_id,
            operation_type="delete",
            before_data=before_data,
            after_data=None
        )

        return {
            "success": True,
            "message": f"✅ 成功删除代理组: {group_name}",
            "data": {"id": group_id, "name": group_name}
        }

    def _handle_create_proxy(self, args: dict[str, Any]) -> dict[str, Any]:
        """创建代理节点"""
        name = args.get("name")
        protocol = args.get("protocol")
        server = args.get("server")
        port = args.get("port")
        params = args.get("params", {})
        description = args.get("description", "")

        if not all([name, protocol, server, port]):
            return {"success": False, "message": "❌ 缺少必要参数: name, protocol, server, port"}

        # 检查名称是否已存在
        existing = (
            self.db.query(ProxyConfig)
            .filter(ProxyConfig.device_id.is_(None), ProxyConfig.name == name)
            .first()
        )
        if existing:
            return {"success": False, "message": f"❌ 代理节点 '{name}' 已存在"}

        # 获取当前最大排序值
        max_order = self.db.query(ProxyConfig).filter(
            ProxyConfig.device_id.is_(None)
        ).count()

        config = ProxyConfig(
            device_id=None,
            name=name,
            protocol=protocol,
            server=server,
            port=port,
            params=params,
            description=description,
            sort_order=max_order,
        )
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)

        # 保存版本记录
        self._save_version(
            resource_type="proxy",
            resource_id=config.id,
            operation_type="create",
            before_data=None,
            after_data=self._model_to_dict(config)
        )

        return {
            "success": True,
            "message": f"✅ 成功创建代理节点: {name} ({protocol}, {server}:{port})",
            "data": {
                "id": config.id,
                "name": config.name,
                "protocol": config.protocol,
                "server": config.server,
                "port": config.port,
            }
        }

    def _handle_update_proxy(self, args: dict[str, Any]) -> dict[str, Any]:
        """更新代理节点"""
        proxy_id = args.get("proxy_id")
        if not proxy_id:
            return {"success": False, "message": "❌ 缺少 proxy_id 参数"}

        config = (
            self.db.query(ProxyConfig)
            .filter(ProxyConfig.id == proxy_id, ProxyConfig.device_id.is_(None))
            .first()
        )
        if not config:
            return {"success": False, "message": f"❌ 代理节点 ID {proxy_id} 不存在"}

        # 检查名称冲突
        new_name = args.get("name")
        if new_name and new_name != config.name:
            existing = (
                self.db.query(ProxyConfig)
                .filter(
                    ProxyConfig.device_id.is_(None),
                    ProxyConfig.name == new_name,
                    ProxyConfig.id != proxy_id
                )
                .first()
            )
            if existing:
                return {"success": False, "message": f"❌ 代理节点名称 '{new_name}' 已被使用"}

        # 保存更新前的数据
        before_data = self._model_to_dict(config)

        # 更新字段
        update_fields = []
        old_name = config.name  # 保存旧名称用于更新代理组 members

        if new_name:
            config.name = new_name
            update_fields.append("名称")
        if "server" in args:
            config.server = args["server"]
            update_fields.append("服务器")
        if "port" in args:
            config.port = args["port"]
            update_fields.append("端口")
        if "params" in args:
            config.params = args["params"]
            update_fields.append("参数")
        if "description" in args:
            config.description = args["description"]
            update_fields.append("描述")

        if not update_fields:
            return {"success": False, "message": "❌ 未提供任何要更新的字段"}

        # 如果名称改变，需要更新所有引用该节点的代理组
        if new_name and new_name != old_name:
            groups = (
                self.db.query(ProxyGroupConfig)
                .filter(ProxyGroupConfig.device_id.is_(None))
                .all()
            )
            updated_groups = 0
            for group in groups:
                if old_name in group.members:
                    group.members = [new_name if m == old_name else m for m in group.members]
                    updated_groups += 1

            if updated_groups > 0:
                update_fields.append(f"更新了 {updated_groups} 个代理组的引用")

        self.db.commit()
        self.db.refresh(config)

        # 保存版本记录
        self._save_version(
            resource_type="proxy",
            resource_id=proxy_id,
            operation_type="update",
            before_data=before_data,
            after_data=self._model_to_dict(config)
        )

        return {
            "success": True,
            "message": f"✅ 成功更新代理节点 '{config.name}' ({', '.join(update_fields)})",
            "data": {
                "id": config.id,
                "name": config.name,
                "protocol": config.protocol,
                "server": config.server,
                "port": config.port,
            }
        }

    def _handle_delete_proxy(self, args: dict[str, Any]) -> dict[str, Any]:
        """删除代理节点"""
        proxy_id = args.get("proxy_id")
        if not proxy_id:
            return {"success": False, "message": "❌ 缺少 proxy_id 参数"}

        config = (
            self.db.query(ProxyConfig)
            .filter(ProxyConfig.id == proxy_id, ProxyConfig.device_id.is_(None))
            .first()
        )
        if not config:
            return {"success": False, "message": f"❌ 代理节点 ID {proxy_id} 不存在"}

        # 检查是否被代理组引用
        proxy_name = config.name
        groups = (
            self.db.query(ProxyGroupConfig)
            .filter(ProxyGroupConfig.device_id.is_(None))
            .all()
        )

        referenced_groups = []
        for group in groups:
            if proxy_name in group.members:
                referenced_groups.append(group.name)

        if referenced_groups:
            return {
                "success": False,
                "message": f"❌ 无法删除代理节点 '{proxy_name}'，以下代理组正在使用: {', '.join(referenced_groups)}"
            }

        # 保存版本记录（删除前）
        before_data = self._model_to_dict(config)

        self.db.delete(config)
        self.db.commit()

        # 保存版本记录
        self._save_version(
            resource_type="proxy",
            resource_id=proxy_id,
            operation_type="delete",
            before_data=before_data,
            after_data=None
        )

        return {
            "success": True,
            "message": f"✅ 成功删除代理节点: {proxy_name}",
            "data": {"id": proxy_id, "name": proxy_name}
        }

    def _handle_move_rule_up(self, args: dict[str, Any]) -> dict[str, Any]:
        """上移规则"""
        rule_id = args.get("rule_id")
        if not rule_id:
            return {"success": False, "message": "❌ 缺少 rule_id 参数"}

        rule = (
            self.db.query(RuleConfig)
            .filter(RuleConfig.id == rule_id, RuleConfig.device_id.is_(None))
            .first()
        )
        if not rule:
            return {"success": False, "message": f"❌ 规则 ID {rule_id} 不存在"}

        # 找到上一条规则
        prev_rule = (
            self.db.query(RuleConfig)
            .filter(
                RuleConfig.device_id.is_(None),
                RuleConfig.sort_order < rule.sort_order
            )
            .order_by(RuleConfig.sort_order.desc())
            .first()
        )

        if not prev_rule:
            return {"success": False, "message": "❌ 规则已在最顶部，无法上移"}

        # 交换 sort_order
        rule.sort_order, prev_rule.sort_order = prev_rule.sort_order, rule.sort_order
        self.db.commit()

        return {
            "success": True,
            "message": f"✅ 规则 #{rule_id} 已上移",
            "data": {"id": rule_id, "new_position": rule.sort_order}
        }

    def _handle_move_rule_down(self, args: dict[str, Any]) -> dict[str, Any]:
        """下移规则"""
        rule_id = args.get("rule_id")
        if not rule_id:
            return {"success": False, "message": "❌ 缺少 rule_id 参数"}

        rule = (
            self.db.query(RuleConfig)
            .filter(RuleConfig.id == rule_id, RuleConfig.device_id.is_(None))
            .first()
        )
        if not rule:
            return {"success": False, "message": f"❌ 规则 ID {rule_id} 不存在"}

        # 找到下一条规则
        next_rule = (
            self.db.query(RuleConfig)
            .filter(
                RuleConfig.device_id.is_(None),
                RuleConfig.sort_order > rule.sort_order
            )
            .order_by(RuleConfig.sort_order.asc())
            .first()
        )

        if not next_rule:
            return {"success": False, "message": "❌ 规则已在最底部，无法下移"}

        # 交换 sort_order
        rule.sort_order, next_rule.sort_order = next_rule.sort_order, rule.sort_order
        self.db.commit()

        return {
            "success": True,
            "message": f"✅ 规则 #{rule_id} 已下移",
            "data": {"id": rule_id, "new_position": rule.sort_order}
        }

    def _handle_reorder_rules(self, args: dict[str, Any]) -> dict[str, Any]:
        """批量重排序规则"""
        orders = args.get("orders", [])
        if not orders:
            return {"success": False, "message": "❌ 缺少 orders 参数"}

        updated_count = 0
        for item in orders:
            rule_id = item.get("id")
            sort_order = item.get("sort_order")

            if rule_id is None or sort_order is None:
                continue

            rule = (
                self.db.query(RuleConfig)
                .filter(RuleConfig.id == rule_id, RuleConfig.device_id.is_(None))
                .first()
            )
            if rule:
                rule.sort_order = sort_order
                updated_count += 1

        self.db.commit()

        return {
            "success": True,
            "message": f"✅ 成功重排序 {updated_count} 条规则",
            "data": {"updated_count": updated_count}
        }

    @with_transaction
    def _handle_batch_delete_rules(self, args: dict[str, Any]) -> dict[str, Any]:
        """批量删除规则"""
        keyword = args.get("keyword", "").lower()
        rule_type = args.get("rule_type")
        policy = args.get("policy")
        dry_run = args.get("dry_run", True)

        # 构建查询
        query = self.db.query(RuleConfig).filter(RuleConfig.device_id.is_(None))

        # 应用过滤条件
        if keyword:
            search_pattern = f"%{keyword}%"
            query = query.filter(
                (RuleConfig.value.like(search_pattern)) |
                (RuleConfig.policy.like(search_pattern)) |
                (RuleConfig.comment.like(search_pattern))
            )
        if rule_type:
            query = query.filter(RuleConfig.rule_type == rule_type)
        if policy:
            query = query.filter(RuleConfig.policy == policy)

        rules = query.all()

        if not rules:
            return {
                "success": False,
                "message": "❌ 未找到匹配条件的规则"
            }

        # 预览模式
        if dry_run:
            preview = [
                {
                    "id": r.id,
                    "rule_type": r.rule_type,
                    "value": r.value[:40] + "..." if len(r.value) > 40 else r.value,
                    "policy": r.policy
                }
                for r in rules[:10]
            ]
            return {
                "success": False,
                "message": f"⚠️ 预览模式：找到 {len(rules)} 条规则将被删除。设置 dry_run=false 确认删除",
                "data": {"preview": preview, "total_count": len(rules)}
            }

        # 执行删除
        for rule in rules:
            self.db.delete(rule)

        return {
            "success": True,
            "message": f"✅ 成功删除 {len(rules)} 条规则",
            "data": {"deleted_count": len(rules)}
        }

    @with_transaction
    def _handle_batch_update_comments(self, args: dict[str, Any]) -> dict[str, Any]:
        """批量更新规则注释"""
        rule_ids = args.get("rule_ids", [])
        comment = args.get("comment", "")

        if not rule_ids:
            return {"success": False, "message": "❌ 缺少 rule_ids 参数"}

        updated_count = 0
        for rule_id in rule_ids:
            rule = (
                self.db.query(RuleConfig)
                .filter(RuleConfig.id == rule_id, RuleConfig.device_id.is_(None))
                .first()
            )
            if rule:
                rule.comment = comment
                updated_count += 1

        if updated_count == 0:
            return {"success": False, "message": "❌ 未找到任何规则"}

        return {
            "success": True,
            "message": f"✅ 成功为 {updated_count} 条规则更新注释",
            "data": {"updated_count": updated_count}
        }

    def _handle_create_wireguard_peer_service(self, args: dict[str, Any]) -> dict[str, Any]:
        """创建 WireGuard 对端服务"""
        name = args.get("name")
        public_key = args.get("public_key")
        endpoint = args.get("endpoint")
        allowed_ips = args.get("allowed_ips")
        preshared_key = args.get("preshared_key")
        keepalive = args.get("keepalive")
        description = args.get("description", "")

        if not all([name, public_key, endpoint, allowed_ips]):
            return {"success": False, "message": "❌ 缺少必要参数: name, public_key, endpoint, allowed_ips"}

        # 检查名称是否已存在
        existing = self.db.query(WireGuardPeerService).filter(WireGuardPeerService.name == name).first()
        if existing:
            return {"success": False, "message": f"❌ 对端服务 '{name}' 已存在"}

        # 获取当前最大排序值
        max_order = self.db.query(WireGuardPeerService).count()

        service = WireGuardPeerService(
            name=name,
            public_key=public_key,
            endpoint=endpoint,
            allowed_ips=allowed_ips,
            preshared_key=preshared_key,
            keepalive=keepalive,
            description=description,
            sort_order=max_order,
        )
        self.db.add(service)
        self.db.commit()
        self.db.refresh(service)

        # 保存版本记录
        self._save_version(
            resource_type="wireguard_peer_service",
            resource_id=service.id,
            operation_type="create",
            before_data=None,
            after_data=self._model_to_dict(service)
        )

        return {
            "success": True,
            "message": f"✅ 成功创建 WireGuard 对端服务: {name}",
            "data": {"id": service.id, "name": service.name, "endpoint": service.endpoint}
        }

    def _handle_list_wireguard_peer_services(self, args: dict[str, Any]) -> dict[str, Any]:
        """列出 WireGuard 对端服务"""
        keyword = args.get("keyword", "").lower()

        services = self.db.query(WireGuardPeerService).order_by(WireGuardPeerService.sort_order).all()

        if keyword:
            services = [
                s for s in services
                if keyword in s.name.lower() or keyword in (s.description or "").lower()
            ]

        if not services:
            return {"success": True, "message": "📋 未找到 WireGuard 对端服务", "data": []}

        service_info = [
            {
                "id": s.id,
                "name": s.name,
                "endpoint": s.endpoint,
                "allowed_ips": s.allowed_ips,
            }
            for s in services
        ]

        return {
            "success": True,
            "message": f"📋 共 {len(services)} 个 WireGuard 对端服务",
            "data": service_info
        }

    def _handle_update_wireguard_peer_service(self, args: dict[str, Any]) -> dict[str, Any]:
        """更新 WireGuard 对端服务"""
        service_id = args.get("service_id")
        if not service_id:
            return {"success": False, "message": "❌ 缺少 service_id 参数"}

        service = self.db.query(WireGuardPeerService).filter(WireGuardPeerService.id == service_id).first()
        if not service:
            return {"success": False, "message": f"❌ 对端服务 ID {service_id} 不存在"}

        # 检查名称冲突
        new_name = args.get("name")
        if new_name and new_name != service.name:
            existing = (
                self.db.query(WireGuardPeerService)
                .filter(WireGuardPeerService.name == new_name, WireGuardPeerService.id != service_id)
                .first()
            )
            if existing:
                return {"success": False, "message": f"❌ 对端服务名称 '{new_name}' 已被使用"}

        # 保存更新前的数据
        before_data = self._model_to_dict(service)

        # 更新字段
        update_fields = []
        if new_name:
            service.name = new_name
            update_fields.append("名称")
        if "public_key" in args:
            service.public_key = args["public_key"]
            update_fields.append("公钥")
        if "endpoint" in args:
            service.endpoint = args["endpoint"]
            update_fields.append("端点")
        if "allowed_ips" in args:
            service.allowed_ips = args["allowed_ips"]
            update_fields.append("允许 IP")
        if "preshared_key" in args:
            service.preshared_key = args["preshared_key"]
            update_fields.append("预共享密钥")
        if "keepalive" in args:
            service.keepalive = args["keepalive"]
            update_fields.append("保持连接")
        if "description" in args:
            service.description = args["description"]
            update_fields.append("描述")

        if not update_fields:
            return {"success": False, "message": "❌ 未提供任何要更新的字段"}

        self.db.commit()
        self.db.refresh(service)

        # 保存版本记录
        self._save_version(
            resource_type="wireguard_peer_service",
            resource_id=service_id,
            operation_type="update",
            before_data=before_data,
            after_data=self._model_to_dict(service)
        )

        return {
            "success": True,
            "message": f"✅ 成功更新 WireGuard 对端服务 '{service.name}' ({', '.join(update_fields)})",
            "data": {"id": service.id, "name": service.name}
        }

    def _handle_delete_wireguard_peer_service(self, args: dict[str, Any]) -> dict[str, Any]:
        """删除 WireGuard 对端服务"""
        service_id = args.get("service_id")
        if not service_id:
            return {"success": False, "message": "❌ 缺少 service_id 参数"}

        service = self.db.query(WireGuardPeerService).filter(WireGuardPeerService.id == service_id).first()
        if not service:
            return {"success": False, "message": f"❌ 对端服务 ID {service_id} 不存在"}

        # 检查是否有 WireGuard 配置在使用
        configs_using = self.db.query(WireGuardConfig).filter(WireGuardConfig.peer_service_id == service_id).count()
        if configs_using > 0:
            return {
                "success": False,
                "message": f"❌ 无法删除：有 {configs_using} 个 WireGuard 配置正在使用此对端服务"
            }

        # 保存版本记录（删除前）
        before_data = self._model_to_dict(service)
        service_name = service.name

        self.db.delete(service)
        self.db.commit()

        # 保存版本记录
        self._save_version(
            resource_type="wireguard_peer_service",
            resource_id=service_id,
            operation_type="delete",
            before_data=before_data,
            after_data=None
        )

        return {
            "success": True,
            "message": f"✅ 成功删除 WireGuard 对端服务: {service_name}",
            "data": {"id": service_id, "name": service_name}
        }

    def _handle_create_wireguard_config(self, args: dict[str, Any]) -> dict[str, Any]:
        """创建 WireGuard 配置"""
        peer_service_id = args.get("peer_service_id")
        section_name = args.get("section_name")
        private_key = args.get("private_key")
        self_ip = args.get("self_ip")
        self_ip_v6 = args.get("self_ip_v6")
        dns_server = args.get("dns_server")
        mtu = args.get("mtu")
        description = args.get("description", "")

        if not all([peer_service_id, section_name, private_key, self_ip]):
            return {"success": False, "message": "❌ 缺少必要参数: peer_service_id, section_name, private_key, self_ip"}

        # 检查对端服务是否存在
        peer_service = self.db.query(WireGuardPeerService).filter(WireGuardPeerService.id == peer_service_id).first()
        if not peer_service:
            return {"success": False, "message": f"❌ 对端服务 ID {peer_service_id} 不存在"}

        # 检查 section_name 是否已存在
        existing = (
            self.db.query(WireGuardConfig)
            .filter(WireGuardConfig.device_id.is_(None), WireGuardConfig.section_name == section_name)
            .first()
        )
        if existing:
            return {"success": False, "message": f"❌ WireGuard 配置 '{section_name}' 已存在"}

        # 获取当前最大排序值
        max_order = self.db.query(WireGuardConfig).filter(WireGuardConfig.device_id.is_(None)).count()

        config = WireGuardConfig(
            device_id=None,
            section_name=section_name,
            peer_service_id=peer_service_id,
            private_key=private_key,
            self_ip=self_ip,
            self_ip_v6=self_ip_v6,
            dns_server=dns_server,
            mtu=mtu,
            description=description,
            sort_order=max_order,
        )
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)

        # 保存版本记录
        self._save_version(
            resource_type="wireguard_config",
            resource_id=config.id,
            operation_type="create",
            before_data=None,
            after_data=self._model_to_dict(config)
        )

        return {
            "success": True,
            "message": f"✅ 成功创建 WireGuard 配置: {section_name}（使用对端服务 '{peer_service.name}'）",
            "data": {"id": config.id, "section_name": config.section_name, "peer_service": peer_service.name}
        }

    def _handle_list_wireguard_configs(self, args: dict[str, Any]) -> dict[str, Any]:
        """列出 WireGuard 配置"""
        keyword = args.get("keyword", "").lower()

        configs = (
            self.db.query(WireGuardConfig)
            .filter(WireGuardConfig.device_id.is_(None))
            .order_by(WireGuardConfig.sort_order)
            .all()
        )

        if keyword:
            configs = [
                c for c in configs
                if keyword in c.section_name.lower() or keyword in (c.description or "").lower()
            ]

        if not configs:
            return {"success": True, "message": "📋 未找到 WireGuard 配置", "data": []}

        config_info = []
        for c in configs:
            # 获取关联的对端服务名称
            peer_service = self.db.query(WireGuardPeerService).filter(WireGuardPeerService.id == c.peer_service_id).first()
            config_info.append({
                "id": c.id,
                "section_name": c.section_name,
                "self_ip": c.self_ip,
                "peer_service": peer_service.name if peer_service else "未知"
            })

        return {
            "success": True,
            "message": f"📋 共 {len(configs)} 个 WireGuard 配置",
            "data": config_info
        }

    def _handle_update_wireguard_config(self, args: dict[str, Any]) -> dict[str, Any]:
        """更新 WireGuard 配置"""
        config_id = args.get("config_id")
        if not config_id:
            return {"success": False, "message": "❌ 缺少 config_id 参数"}

        config = (
            self.db.query(WireGuardConfig)
            .filter(WireGuardConfig.id == config_id, WireGuardConfig.device_id.is_(None))
            .first()
        )
        if not config:
            return {"success": False, "message": f"❌ WireGuard 配置 ID {config_id} 不存在"}

        # 检查 section_name 冲突
        new_section_name = args.get("section_name")
        if new_section_name and new_section_name != config.section_name:
            existing = (
                self.db.query(WireGuardConfig)
                .filter(
                    WireGuardConfig.device_id.is_(None),
                    WireGuardConfig.section_name == new_section_name,
                    WireGuardConfig.id != config_id
                )
                .first()
            )
            if existing:
                return {"success": False, "message": f"❌ WireGuard 配置名称 '{new_section_name}' 已被使用"}

        # 保存更新前的数据
        before_data = self._model_to_dict(config)

        # 更新字段
        update_fields = []
        if new_section_name:
            config.section_name = new_section_name
            update_fields.append("节名称")
        if "private_key" in args:
            config.private_key = args["private_key"]
            update_fields.append("私钥")
        if "self_ip" in args:
            config.self_ip = args["self_ip"]
            update_fields.append("本地 IP")
        if "self_ip_v6" in args:
            config.self_ip_v6 = args["self_ip_v6"]
            update_fields.append("本地 IPv6")
        if "dns_server" in args:
            config.dns_server = args["dns_server"]
            update_fields.append("DNS")
        if "mtu" in args:
            config.mtu = args["mtu"]
            update_fields.append("MTU")
        if "description" in args:
            config.description = args["description"]
            update_fields.append("描述")

        if not update_fields:
            return {"success": False, "message": "❌ 未提供任何要更新的字段"}

        self.db.commit()
        self.db.refresh(config)

        # 保存版本记录
        self._save_version(
            resource_type="wireguard_config",
            resource_id=config_id,
            operation_type="update",
            before_data=before_data,
            after_data=self._model_to_dict(config)
        )

        return {
            "success": True,
            "message": f"✅ 成功更新 WireGuard 配置 '{config.section_name}' ({', '.join(update_fields)})",
            "data": {"id": config.id, "section_name": config.section_name}
        }

    def _handle_delete_wireguard_config(self, args: dict[str, Any]) -> dict[str, Any]:
        """删除 WireGuard 配置"""
        config_id = args.get("config_id")
        if not config_id:
            return {"success": False, "message": "❌ 缺少 config_id 参数"}

        config = (
            self.db.query(WireGuardConfig)
            .filter(WireGuardConfig.id == config_id, WireGuardConfig.device_id.is_(None))
            .first()
        )
        if not config:
            return {"success": False, "message": f"❌ WireGuard 配置 ID {config_id} 不存在"}

        # 保存版本记录（删除前）
        before_data = self._model_to_dict(config)
        section_name = config.section_name

        self.db.delete(config)
        self.db.commit()

        # 保存版本记录
        self._save_version(
            resource_type="wireguard_config",
            resource_id=config_id,
            operation_type="delete",
            before_data=before_data,
            after_data=None
        )

        return {
            "success": True,
            "message": f"✅ 成功删除 WireGuard 配置: {section_name}",
            "data": {"id": config_id, "section_name": section_name}
        }

    def _handle_list_config_history(self, args: dict[str, Any]) -> dict[str, Any]:
        """查看配置历史记录"""
        resource_type = args.get("resource_type")
        resource_id = args.get("resource_id")
        limit = args.get("limit", 20)

        if not resource_type:
            return {"success": False, "message": "❌ 缺少 resource_type 参数"}

        # 构建查询
        query = self.db.query(ConfigVersion).filter(ConfigVersion.resource_type == resource_type)

        if resource_id:
            query = query.filter(ConfigVersion.resource_id == resource_id)

        # 按时间倒序排列
        versions = query.order_by(ConfigVersion.created_at.desc()).limit(limit).all()

        if not versions:
            msg = f"📋 未找到 {resource_type}"
            if resource_id:
                msg += f" ID {resource_id}"
            msg += " 的历史记录"
            return {"success": True, "message": msg, "data": []}

        # 构建历史信息
        history_info = []
        for v in versions:
            history_info.append({
                "id": v.id,
                "resource_id": v.resource_id,
                "operation": v.operation_type,
                "created_at": v.created_at.isoformat() if v.created_at else None,
                "before": v.before_data,
                "after": v.after_data,
            })

        msg = f"📋 找到 {len(versions)} 条历史记录"
        if resource_id:
            msg += f"（{resource_type} ID {resource_id}）"
        else:
            msg += f"（{resource_type} 类型）"

        return {
            "success": True,
            "message": msg,
            "data": history_info
        }

    def _handle_rollback_config(self, args: dict[str, Any]) -> dict[str, Any]:
        """回滚配置到指定版本"""
        version_id = args.get("version_id")
        confirm = args.get("confirm", False)

        if not version_id:
            return {"success": False, "message": "❌ 缺少 version_id 参数"}

        # 查找版本记录
        version = self.db.query(ConfigVersion).filter(ConfigVersion.id == version_id).first()
        if not version:
            return {"success": False, "message": f"❌ 版本记录 ID {version_id} 不存在"}

        # 危险操作确认
        if not confirm:
            return {
                "success": False,
                "message": f"⚠️ 这是危险操作！将回滚 {version.resource_type} ID {version.resource_id} 到版本 {version_id}（{version.operation_type}，{version.created_at}）。请添加 confirm=True 参数确认。",
                "data": {
                    "version_id": version_id,
                    "resource_type": version.resource_type,
                    "resource_id": version.resource_id,
                    "operation": version.operation_type,
                    "before_data": version.before_data,
                    "after_data": version.after_data,
                }
            }

        resource_type = version.resource_type
        resource_id = version.resource_id
        restore_data = version.before_data  # 回滚使用 before_data

        if not restore_data:
            return {"success": False, "message": "❌ 该版本没有可恢复的数据（before_data 为空）"}

        try:
            # 根据资源类型查找对应的模型
            model_map = {
                "rule": RuleConfig,
                "proxy": ProxyConfig,
                "proxy_group": ProxyGroupConfig,
                "host": HostConfig,
                "general_config": GeneralConfig,
                "wireguard_config": WireGuardConfig,
                "wireguard_peer_service": WireGuardPeerService,
            }

            model_class = model_map.get(resource_type)
            if not model_class:
                return {"success": False, "message": f"❌ 不支持的资源类型: {resource_type}"}

            # 查找资源对象
            obj = self.db.query(model_class).filter(model_class.id == resource_id).first()

            if version.operation_type == "delete":
                # 如果是删除操作，需要重新创建对象
                if obj:
                    return {"success": False, "message": f"❌ 资源已存在，无法恢复删除的数据（ID {resource_id} 已被占用）"}

                # 重新创建对象
                new_obj = model_class(**restore_data)
                self.db.add(new_obj)
                self.db.commit()
                self.db.refresh(new_obj)

                # 保存回滚操作的版本记录
                self._save_version(
                    resource_type=resource_type,
                    resource_id=new_obj.id,
                    operation_type="rollback",
                    before_data=None,
                    after_data=restore_data
                )

                return {
                    "success": True,
                    "message": f"✅ 成功恢复已删除的 {resource_type} (ID {new_obj.id})",
                    "data": {"id": new_obj.id, "restored_data": restore_data}
                }

            elif obj:
                # 如果是创建或更新操作，恢复对象的字段
                current_data = {}
                for key, value in restore_data.items():
                    if hasattr(obj, key) and key != "id":  # 不恢复 ID
                        current_data[key] = getattr(obj, key)
                        setattr(obj, key, value)

                self.db.commit()
                self.db.refresh(obj)

                # 保存回滚操作的版本记录
                self._save_version(
                    resource_type=resource_type,
                    resource_id=resource_id,
                    operation_type="rollback",
                    before_data=current_data,
                    after_data=restore_data
                )

                return {
                    "success": True,
                    "message": f"✅ 成功回滚 {resource_type} ID {resource_id} 到版本 {version_id}",
                    "data": {"id": resource_id, "restored_data": restore_data}
                }
            else:
                return {"success": False, "message": f"❌ 资源 {resource_type} ID {resource_id} 不存在，无法回滚"}

        except Exception as e:
            self.db.rollback()
            logger.error(f"回滚配置失败: {e}", exc_info=True)
            return {"success": False, "message": f"❌ 回滚失败: {str(e)}"}


    def get_config_context(self, force_refresh: bool = False) -> str:
        """生成配置上下文摘要，供系统提示词使用（带缓存）"""
        logger.info("get_config_context 开始执行")
        # 检查缓存
        now = time.time()
        if not force_refresh and self._cache_data and (now - self._cache_timestamp) < self.CACHE_TTL:
            logger.info("使用缓存的配置上下文")
            return self._cache_data

        logger.info("重新生成配置上下文")
        lines = ["[当前配置概览]"]

        # 规则摘要 + 统计
        all_rules = (
            self.db.query(RuleConfig)
            .filter(RuleConfig.device_id.is_(None))
            .order_by(RuleConfig.sort_order)
            .all()
        )
        total_rules = len(all_rules)

        # 统计规则类型分布
        rule_type_count = {}
        policy_count = {}
        for r in all_rules:
            rule_type_count[r.rule_type] = rule_type_count.get(r.rule_type, 0) + 1
            policy_count[r.policy] = policy_count.get(r.policy, 0) + 1

        # 规则类型分布（按数量排序）
        type_dist = ", ".join([f"{k}({v})" for k, v in sorted(rule_type_count.items(), key=lambda x: -x[1])[:5]])
        # 策略分布（按数量排序）
        policy_dist = ", ".join([f"{k}({v})" for k, v in sorted(policy_count.items(), key=lambda x: -x[1])[:5]])

        lines.append(f"\n规则 (共 {total_rules} 条):")
        lines.append(f"  类型分布: {type_dist}")
        lines.append(f"  策略分布: {policy_dist}")
        lines.append("")

        # 显示前 30 条规则
        for r in all_rules[:30]:
            line = f"  [ID:{r.id}] {r.rule_type}, {r.value}, {r.policy}"
            if r.comment:
                line += f" // {r.comment}"
            lines.append(line)
        if total_rules > 30:
            lines.append(f"  ... 还有 {total_rules - 30} 条规则")

        # 策略组摘要 + 统计
        groups = (
            self.db.query(ProxyGroupConfig)
            .filter(ProxyGroupConfig.device_id.is_(None))
            .all()
        )

        # 统计代理组类型分布
        group_type_count = {}
        for g in groups:
            group_type_count[g.group_type] = group_type_count.get(g.group_type, 0) + 1

        group_type_dist = ", ".join([f"{k}({v})" for k, v in group_type_count.items()])

        lines.append(f"\n策略组 (共 {len(groups)} 个):")
        if group_type_dist:
            lines.append(f"  类型分布: {group_type_dist}")
        for g in groups:
            lines.append(f"  - {g.name} ({g.group_type})")

        # 代理摘要 + 统计
        proxies = (
            self.db.query(ProxyConfig)
            .filter(ProxyConfig.device_id.is_(None), ProxyConfig.is_active == True)
            .all()
        )

        # 统计代理协议分布
        protocol_count = {}
        for p in proxies:
            protocol_count[p.protocol] = protocol_count.get(p.protocol, 0) + 1

        protocol_dist = ", ".join([f"{k}({v})" for k, v in protocol_count.items()])

        lines.append(f"\n代理节点 (共 {len(proxies)} 个):")
        if protocol_dist:
            lines.append(f"  协议分布: {protocol_dist}")
        for p in proxies[:10]:
            lines.append(f"  - {p.name} ({p.protocol})")
        if len(proxies) > 10:
            lines.append(f"  ... 还有 {len(proxies) - 10} 个节点")

        # AI 配置建议检测
        suggestions = []

        # 检测 1: 冗余规则（相同的 rule_type + value + policy）
        rule_signatures = {}
        for r in all_rules:
            sig = f"{r.rule_type}|{r.value}|{r.policy}"
            if sig in rule_signatures:
                rule_signatures[sig].append(r.id)
            else:
                rule_signatures[sig] = [r.id]

        duplicates = {sig: ids for sig, ids in rule_signatures.items() if len(ids) > 1}
        if duplicates:
            for sig, ids in list(duplicates.items())[:3]:  # 只显示前 3 组
                suggestions.append(f"⚠️ 冗余规则：规则 {', '.join([f'#{id}' for id in ids])} 完全相同")

        # 检测 2: 未使用的代理组
        used_policies = set(r.policy for r in all_rules)
        unused_groups = [g.name for g in groups if g.name not in used_policies]
        if unused_groups:
            suggestions.append(f"⚠️ 未使用的代理组：{', '.join(unused_groups[:5])}")

        # 检测 3: FINAL 规则顺序问题
        final_rules = [r for r in all_rules if r.rule_type == "FINAL"]
        if final_rules:
            final_rule = final_rules[0]
            # 检查 FINAL 是否在最后
            if all_rules and all_rules[-1].id != final_rule.id:
                last_rule_idx = all_rules.index(final_rule) if final_rule in all_rules else -1
                if last_rule_idx >= 0 and last_rule_idx < len(all_rules) - 1:
                    rules_after = len(all_rules) - last_rule_idx - 1
                    suggestions.append(f"⚠️ 规则顺序：FINAL 规则（#{final_rule.id}）应该在最后，但后面还有 {rules_after} 条规则")

        # 检测 4: 未使用的代理节点
        used_proxy_names = set()
        for g in groups:
            used_proxy_names.update(g.members)
        unused_proxies = [p.name for p in proxies if p.name not in used_proxy_names]
        if unused_proxies and len(unused_proxies) <= 5:
            suggestions.append(f"⚠️ 未使用的代理节点：{', '.join(unused_proxies)}")

        # 添加建议到输出
        if suggestions:
            lines.append("\n[配置建议]")
            lines.append(f"发现 {len(suggestions)} 个潜在问题：")
            for suggestion in suggestions[:5]:  # 最多显示 5 条建议
                lines.append(f"  {suggestion}")

        # 更新缓存
        context = "\n".join(lines)
        self._cache_data = context
        self._cache_timestamp = time.time()

        return context

    # ============ 规则集管理 ============

    def _handle_create_ruleset(self, args: dict[str, Any]) -> dict[str, Any]:
        """创建规则集"""
        name = args.get("name")
        description = args.get("description", "")
        items = args.get("items", [])

        if not name:
            return {"success": False, "message": "❌ 缺少必要参数: name"}

        # 检查名称唯一性
        existing = self.db.query(RuleSet).filter(RuleSet.name == name).first()
        if existing:
            return {"success": False, "message": f"❌ 规则集名称 '{name}' 已存在"}

        # 获取最大排序值
        max_order = self.db.query(RuleSet).count()

        # 创建规则集
        ruleset = RuleSet(
            name=name,
            description=description,
            sort_order=max_order,
        )
        self.db.add(ruleset)
        self.db.flush()

        # 添加初始条目
        added_items = []
        for idx, item_data in enumerate(items):
            item = RuleSetItem(
                ruleset_id=ruleset.id,
                item_type=item_data.get("item_type"),
                value=item_data.get("value"),
                comment=item_data.get("comment", ""),
                sort_order=idx,
            )
            self.db.add(item)
            added_items.append(f"{item.item_type}: {item.value}")

        self.db.commit()
        self.db.refresh(ruleset)

        result_msg = f"✅ 成功创建规则集 '{name}'"
        if added_items:
            result_msg += f"，包含 {len(added_items)} 个条目"

        return {
            "success": True,
            "message": result_msg,
            "data": {
                "id": ruleset.id,
                "name": ruleset.name,
                "item_count": len(added_items)
            }
        }

    def _handle_list_rulesets(self, args: dict[str, Any]) -> dict[str, Any]:
        """查询规则集列表"""
        keyword = args.get("keyword", "").lower()

        query = self.db.query(RuleSet)

        if keyword:
            search_pattern = f"%{keyword}%"
            query = query.filter(
                (RuleSet.name.like(search_pattern)) |
                (RuleSet.description.like(search_pattern))
            )

        rulesets = query.order_by(RuleSet.sort_order).all()

        if not rulesets:
            return {"success": True, "message": "📋 暂无规则集", "data": []}

        data = []
        for rs in rulesets:
            item_count = len(rs.items)
            active_count = len([i for i in rs.items if i.is_active])
            data.append({
                "id": rs.id,
                "name": rs.name,
                "description": rs.description or "",
                "is_active": rs.is_active,
                "item_count": item_count,
                "active_item_count": active_count,
            })

        return {
            "success": True,
            "message": f"📋 共 {len(rulesets)} 个规则集",
            "data": data
        }

    def _handle_get_ruleset(self, args: dict[str, Any]) -> dict[str, Any]:
        """获取规则集详情"""
        ruleset_id = args.get("ruleset_id")
        name = args.get("name")

        if not ruleset_id and not name:
            return {"success": False, "message": "❌ 需要提供 ruleset_id 或 name"}

        if ruleset_id:
            ruleset = self.db.query(RuleSet).filter(RuleSet.id == ruleset_id).first()
        else:
            ruleset = self.db.query(RuleSet).filter(RuleSet.name == name).first()

        if not ruleset:
            return {"success": False, "message": "❌ 规则集不存在"}

        items_data = []
        for item in ruleset.items:
            items_data.append({
                "id": item.id,
                "type": item.item_type,
                "value": item.value,
                "comment": item.comment or "",
                "is_active": item.is_active,
            })

        return {
            "success": True,
            "message": f"📋 规则集 '{ruleset.name}' 详情",
            "data": {
                "id": ruleset.id,
                "name": ruleset.name,
                "description": ruleset.description or "",
                "is_active": ruleset.is_active,
                "item_count": len(items_data),
                "items": items_data,
            }
        }

    def _handle_update_ruleset(self, args: dict[str, Any]) -> dict[str, Any]:
        """更新规则集"""
        ruleset_id = args.get("ruleset_id")

        if not ruleset_id:
            return {"success": False, "message": "❌ 缺少必要参数: ruleset_id"}

        ruleset = self.db.query(RuleSet).filter(RuleSet.id == ruleset_id).first()
        if not ruleset:
            return {"success": False, "message": "❌ 规则集不存在"}

        updated_fields = []

        # 更新名称
        new_name = args.get("name")
        if new_name and new_name != ruleset.name:
            existing = self.db.query(RuleSet).filter(
                RuleSet.name == new_name,
                RuleSet.id != ruleset_id
            ).first()
            if existing:
                return {"success": False, "message": f"❌ 规则集名称 '{new_name}' 已存在"}
            ruleset.name = new_name
            updated_fields.append("名称")

        # 更新描述
        if "description" in args:
            ruleset.description = args["description"]
            updated_fields.append("描述")

        # 更新激活状态
        if "is_active" in args:
            ruleset.is_active = args["is_active"]
            updated_fields.append("激活状态")

        if not updated_fields:
            return {"success": False, "message": "❌ 未提供任何要更新的字段"}

        self.db.commit()
        self.db.refresh(ruleset)

        return {
            "success": True,
            "message": f"✅ 规则集已更新: {', '.join(updated_fields)}",
            "data": {"id": ruleset.id, "name": ruleset.name}
        }

    def _handle_delete_ruleset(self, args: dict[str, Any]) -> dict[str, Any]:
        """删除规则集"""
        ruleset_id = args.get("ruleset_id")

        if not ruleset_id:
            return {"success": False, "message": "❌ 缺少必要参数: ruleset_id"}

        ruleset = self.db.query(RuleSet).filter(RuleSet.id == ruleset_id).first()
        if not ruleset:
            return {"success": False, "message": "❌ 规则集不存在"}

        name = ruleset.name
        item_count = len(ruleset.items)

        self.db.delete(ruleset)
        self.db.commit()

        return {
            "success": True,
            "message": f"✅ 已删除规则集 '{name}'（包含 {item_count} 个条目）",
            "data": {"id": ruleset_id, "name": name}
        }

    def _handle_add_ruleset_items(self, args: dict[str, Any]) -> dict[str, Any]:
        """向规则集添加条目"""
        logger.info(f"add_ruleset_items 收到的 args: {args}")
        logger.info(f"args 类型: {type(args)}")

        ruleset_id = args.get("ruleset_id")
        ruleset_name = args.get("ruleset_name")
        items = args.get("items", [])
        logger.info(f"items 类型: {type(items)}, 内容: {items}")

        if not ruleset_id and not ruleset_name:
            return {"success": False, "message": "❌ 缺少必要参数: 需要提供 ruleset_id 或 ruleset_name"}

        if not items:
            return {"success": False, "message": "❌ 缺少必要参数: items"}

        # 支持通过 ID 或名称查找规则集
        if ruleset_id:
            ruleset = self.db.query(RuleSet).filter(RuleSet.id == ruleset_id).first()
        else:
            ruleset = self.db.query(RuleSet).filter(RuleSet.name == ruleset_name).first()

        if not ruleset:
            return {"success": False, "message": f"❌ 规则集不存在: {ruleset_name or ruleset_id}"}

        # 获取当前最大排序值
        current_count = len(ruleset.items)

        added = []
        for idx, item_data in enumerate(items):
            item_type = item_data.get("item_type")
            value = item_data.get("value")

            if not item_type or not value:
                continue

            item = RuleSetItem(
                ruleset_id=ruleset.id,  # 使用查询到的 ruleset.id，而不是传入参数
                item_type=item_type,
                value=value,
                comment=item_data.get("comment", ""),
                sort_order=current_count + idx,
            )
            self.db.add(item)
            added.append(f"{item_type}: {value}")

        self.db.commit()

        return {
            "success": True,
            "message": f"✅ 向规则集 '{ruleset.name}' 添加了 {len(added)} 个条目",
            "data": {"ruleset_id": ruleset.id, "added_count": len(added), "items": added}
        }

    def _handle_delete_ruleset_item(self, args: dict[str, Any]) -> dict[str, Any]:
        """删除规则集条目"""
        ruleset_id = args.get("ruleset_id")
        item_id = args.get("item_id")

        if not ruleset_id or not item_id:
            return {"success": False, "message": "❌ 缺少必要参数: ruleset_id, item_id"}

        item = self.db.query(RuleSetItem).filter(
            RuleSetItem.id == item_id,
            RuleSetItem.ruleset_id == ruleset_id
        ).first()

        if not item:
            return {"success": False, "message": "❌ 条目不存在"}

        item_info = f"{item.item_type}: {item.value}"
        self.db.delete(item)
        self.db.commit()

        return {
            "success": True,
            "message": f"✅ 已删除条目: {item_info}",
            "data": {"item_id": item_id}
        }

    def _handle_create_wireguard_full(self, args: dict[str, Any]) -> dict[str, Any]:
        """一次性创建完整的 WireGuard 配置（对端服务 + 配置 + 可选代理节点）"""
        name = args.get("name")
        private_key = args.get("private_key")
        self_ip = args.get("self_ip")
        public_key = args.get("public_key")
        endpoint = args.get("endpoint")
        allowed_ips = args.get("allowed_ips")
        preshared_key = args.get("preshared_key")
        dns_server = args.get("dns_server")
        device_name = args.get("device_name")

        if not all([name, private_key, self_ip, public_key, endpoint, allowed_ips]):
            return {"success": False, "message": "❌ 缺少必要参数"}

        # 处理 self_ip，去掉可能的掩码
        if "/" in self_ip:
            self_ip = self_ip.split("/")[0]

        results = []

        try:
            # 1. 创建对端服务
            peer_name = f"{name}-Peer"
            existing_peer = self.db.query(WireGuardPeerService).filter(
                WireGuardPeerService.name == peer_name
            ).first()

            if existing_peer:
                peer_service = existing_peer
                results.append(f"ℹ️ 对端服务 '{peer_name}' 已存在，复用")
            else:
                peer_service = WireGuardPeerService(
                    name=peer_name,
                    public_key=public_key,
                    endpoint=endpoint,
                    allowed_ips=allowed_ips,
                    preshared_key=preshared_key,
                    is_active=True
                )
                self.db.add(peer_service)
                self.db.flush()
                results.append(f"✅ 创建对端服务: {peer_name}")

            # 2. 查找设备（如果指定）
            device_id = None
            if device_name:
                device = self.db.query(Device).filter(Device.name == device_name).first()
                if device:
                    device_id = device.id
                else:
                    results.append(f"⚠️ 设备 '{device_name}' 不存在，将创建全局配置")

            # 3. 创建 WireGuard 配置
            section_name = name
            existing_config = self.db.query(WireGuardConfig).filter(
                WireGuardConfig.section_name == section_name
            ).first()

            if existing_config:
                results.append(f"⚠️ WireGuard 配置 '{section_name}' 已存在")
            else:
                wg_config = WireGuardConfig(
                    section_name=section_name,
                    private_key=private_key,
                    self_ip=self_ip,
                    dns_server=dns_server,
                    peer_service_id=peer_service.id,
                    device_id=device_id,
                    mtu=1420,
                    prefer_ipv6=False,
                    is_active=True
                )
                self.db.add(wg_config)
                results.append(f"✅ 创建 WireGuard 配置: {section_name}" + (f" (设备: {device_name})" if device_name else " (全局)"))

            # 4. 创建 WireGuard 代理节点（可选）
            if device_id:
                proxy_name = f"{name}-Proxy"
                existing_proxy = self.db.query(ProxyConfig).filter(
                    ProxyConfig.name == proxy_name
                ).first()

                if not existing_proxy:
                    proxy = ProxyConfig(
                        name=proxy_name,
                        protocol="wireguard",
                        device_id=device_id,
                        params={"section-name": section_name},
                        is_active=True
                    )
                    self.db.add(proxy)
                    results.append(f"✅ 创建代理节点: {proxy_name}")

            self.db.commit()

            return {
                "success": True,
                "message": "\n".join(results),
                "data": {
                    "peer_service_id": peer_service.id,
                    "section_name": section_name,
                    "device_id": device_id
                }
            }

        except Exception as e:
            self.db.rollback()
            return {"success": False, "message": f"❌ 创建失败: {str(e)}"}

    def _handle_extract_to_ruleset(self, args: dict[str, Any]) -> dict[str, Any]:
        """从现有规则中提取 IP/域名，添加到指定规则集"""
        import re

        policy = args.get("policy")
        ruleset_name = args.get("ruleset_name")
        include_types = args.get("include_types", [
            "IP-CIDR", "IP-CIDR6", "DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD"
        ])

        if not policy or not ruleset_name:
            return {"success": False, "message": "❌ 缺少必要参数: policy, ruleset_name"}

        # 查找目标规则集
        ruleset = self.db.query(RuleSet).filter(RuleSet.name == ruleset_name).first()
        if not ruleset:
            return {"success": False, "message": f"❌ 规则集 '{ruleset_name}' 不存在"}

        # 查询指定策略的规则
        rules = self.db.query(RuleConfig).filter(
            RuleConfig.device_id.is_(None),
            RuleConfig.policy.ilike(f"%{policy}%")
        ).all()

        if not rules:
            return {"success": False, "message": f"❌ 未找到策略为 '{policy}' 的规则"}

        # 解析规则中的值
        extracted_items = []

        for rule in rules:
            rule_type = rule.rule_type
            value = rule.value

            # 简单规则类型直接提取
            if rule_type in include_types:
                extracted_items.append({
                    "item_type": rule_type,
                    "value": value,
                    "comment": f"从规则 #{rule.id} 提取"
                })

            # 复合规则（AND/OR）需要解析内部值
            elif rule_type in ("AND", "OR"):
                # 使用正则表达式提取各种类型的值
                for item_type in include_types:
                    # 匹配模式: (类型,值) 或 (类型,值,选项)
                    pattern = rf'\({item_type},([^,\)]+)'
                    matches = re.findall(pattern, value, re.IGNORECASE)
                    for match in matches:
                        extracted_value = match.strip()
                        if extracted_value:
                            extracted_items.append({
                                "item_type": item_type,
                                "value": extracted_value,
                                "comment": f"从规则 #{rule.id} ({rule_type}) 提取"
                            })

        if not extracted_items:
            return {
                "success": False,
                "message": f"❌ 从 {len(rules)} 条规则中未提取到任何 IP/域名值"
            }

        # 去重（基于 item_type + value）
        seen = set()
        unique_items = []
        for item in extracted_items:
            key = (item["item_type"], item["value"])
            if key not in seen:
                seen.add(key)
                unique_items.append(item)

        # 检查现有条目，避免重复添加
        existing_items = self.db.query(RuleSetItem).filter(
            RuleSetItem.ruleset_id == ruleset.id
        ).all()
        existing_set = {(i.item_type, i.value) for i in existing_items}

        # 过滤掉已存在的条目
        new_items = [
            item for item in unique_items
            if (item["item_type"], item["value"]) not in existing_set
        ]

        if not new_items:
            return {
                "success": True,
                "message": f"ℹ️ 提取了 {len(unique_items)} 个值，但都已存在于规则集 '{ruleset_name}' 中",
                "data": {"extracted_count": len(unique_items), "added_count": 0}
            }

        # 添加新条目
        current_max_order = len(existing_items)
        added = []
        for idx, item_data in enumerate(new_items):
            item = RuleSetItem(
                ruleset_id=ruleset.id,
                item_type=item_data["item_type"],
                value=item_data["value"],
                comment=item_data.get("comment"),
                is_active=True,
                sort_order=current_max_order + idx
            )
            self.db.add(item)
            added.append(f"{item_data['item_type']}: {item_data['value']}")

        self.db.commit()

        return {
            "success": True,
            "message": f"✅ 从 {len(rules)} 条规则中提取并添加了 {len(added)} 个条目到规则集 '{ruleset_name}':\n" + "\n".join(f"  - {a}" for a in added),
            "data": {
                "ruleset_id": ruleset.id,
                "rules_scanned": len(rules),
                "extracted_count": len(unique_items),
                "added_count": len(added),
                "items": added
            }
        }

    def _handle_update_host(self, args: dict[str, Any]) -> dict[str, Any]:
        """更新主机映射"""
        host_id = args.get("host_id")
        if not host_id:
            return {"success": False, "message": "❌ 缺少 host_id 参数"}

        host = self.db.query(HostConfig).filter(
            HostConfig.id == host_id,
            HostConfig.device_id.is_(None)
        ).first()

        if not host:
            return {"success": False, "message": f"❌ 主机映射 ID {host_id} 不存在"}

        # 保存更新前的数据
        before_data = self._model_to_dict(host)
        update_fields = []

        if "target" in args and args["target"]:
            host.target = args["target"]
            update_fields.append("目标")
        if "description" in args:
            host.description = args["description"]
            update_fields.append("描述")

        if not update_fields:
            return {"success": False, "message": "❌ 未提供任何要更新的字段"}

        self.db.commit()
        self.db.refresh(host)

        # 保存版本记录
        self._save_version(
            resource_type="host",
            resource_id=host_id,
            operation_type="update",
            before_data=before_data,
            after_data=self._model_to_dict(host)
        )

        return {
            "success": True,
            "message": f"✅ 成功更新主机映射 '{host.hostname}' ({', '.join(update_fields)})",
            "data": {
                "id": host.id,
                "hostname": host.hostname,
                "target": host.target,
                "description": host.description,
            }
        }

    def _handle_delete_general_config(self, args: dict[str, Any]) -> dict[str, Any]:
        """删除通用配置"""
        key = args.get("key")
        if not key:
            return {"success": False, "message": "❌ 缺少 key 参数"}

        config = self.db.query(GeneralConfig).filter(
            GeneralConfig.device_id.is_(None),
            GeneralConfig.key == key
        ).first()

        if not config:
            return {"success": False, "message": f"❌ 配置项 '{key}' 不存在"}

        # 保存版本记录（删除前）
        before_data = self._model_to_dict(config)
        config_id = config.id

        self.db.delete(config)
        self.db.commit()

        # 保存版本记录
        self._save_version(
            resource_type="general_config",
            resource_id=config_id,
            operation_type="delete",
            before_data=before_data,
            after_data=None
        )

        return {"success": True, "message": f"✅ 成功删除配置项：{key}"}

    def _handle_list_devices(self, args: dict[str, Any]) -> dict[str, Any]:
        """获取设备列表"""
        keyword = args.get("keyword", "").lower()

        devices = self.db.query(Device).filter(
            Device.user_id == self.current_user.id
        ).all()

        if keyword:
            devices = [d for d in devices if keyword in d.name.lower()]

        if not devices:
            return {"success": True, "message": "暂无设备", "data": []}

        lines = [f"📱 共 {len(devices)} 个设备：", ""]
        device_info = []
        for d in devices:
            lines.append(f"#{d.id}  {d.name}")
            if d.description:
                lines.append(f"    💬 {d.description}")
            lines.append("")
            device_info.append({
                "id": d.id,
                "name": d.name,
                "description": d.description,
            })

        return {
            "success": True,
            "message": "\n".join(lines),
            "data": device_info
        }

    def _handle_create_general_config(self, args: dict[str, Any]) -> dict[str, Any]:
        """创建通用配置"""
        key = args.get("key")
        value = args.get("value")
        description = args.get("description", "")

        if not key or value is None:
            return {"success": False, "message": "❌ 缺少 key 或 value 参数"}

        # 检查是否已存在
        existing = self.db.query(GeneralConfig).filter(
            GeneralConfig.device_id.is_(None),
            GeneralConfig.key == key
        ).first()

        if existing:
            return {"success": False, "message": f"❌ 配置项 '{key}' 已存在，请使用 update_general_config 更新"}

        # 获取当前最大排序值
        max_order = self.db.query(GeneralConfig).filter(
            GeneralConfig.device_id.is_(None)
        ).count()

        config = GeneralConfig(
            device_id=None,
            key=key,
            value=value,
            description=description,
            sort_order=max_order,
        )
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)

        # 保存版本记录
        self._save_version(
            resource_type="general_config",
            resource_id=config.id,
            operation_type="create",
            before_data=None,
            after_data=self._model_to_dict(config)
        )

        return {
            "success": True,
            "message": f"✅ 成功创建配置：{key} = {value}",
            "data": {
                "id": config.id,
                "key": config.key,
                "value": config.value,
            }
        }

    def _handle_create_device(self, args: dict[str, Any]) -> dict[str, Any]:
        """创建设备"""
        name = args.get("name")
        description = args.get("description", "")

        if not name:
            return {"success": False, "message": "❌ 缺少设备名称"}

        # 检查名称是否已存在
        existing = self.db.query(Device).filter(
            Device.user_id == self.current_user.id,
            Device.name == name
        ).first()

        if existing:
            return {"success": False, "message": f"❌ 设备 '{name}' 已存在"}

        device = Device(
            user_id=self.current_user.id,
            name=name,
            description=description,
        )
        self.db.add(device)
        self.db.commit()
        self.db.refresh(device)

        return {
            "success": True,
            "message": f"✅ 成功创建设备：{name}",
            "data": {
                "id": device.id,
                "name": device.name,
                "description": device.description,
            }
        }

    def _handle_delete_device(self, args: dict[str, Any]) -> dict[str, Any]:
        """删除设备"""
        device_id = args.get("device_id")
        if not device_id:
            return {"success": False, "message": "❌ 缺少 device_id 参数"}

        device = self.db.query(Device).filter(
            Device.id == device_id,
            Device.user_id == self.current_user.id
        ).first()

        if not device:
            return {"success": False, "message": f"❌ 设备 ID {device_id} 不存在"}

        device_name = device.name

        # 检查是否有关联的配置
        wg_count = self.db.query(WireGuardConfig).filter(WireGuardConfig.device_id == device_id).count()
        proxy_count = self.db.query(ProxyConfig).filter(ProxyConfig.device_id == device_id).count()
        rule_count = self.db.query(RuleConfig).filter(RuleConfig.device_id == device_id).count()

        if wg_count + proxy_count + rule_count > 0:
            return {
                "success": False,
                "message": f"❌ 设备 '{device_name}' 有关联配置（WireGuard: {wg_count}, 代理: {proxy_count}, 规则: {rule_count}），请先删除这些配置"
            }

        self.db.delete(device)
        self.db.commit()

        return {"success": True, "message": f"✅ 成功删除设备：{device_name}"}

    def _handle_create_ruleset(self, args: dict[str, Any]) -> dict[str, Any]:
        """创建规则集"""
        name = args.get("name")
        description = args.get("description", "")

        if not name:
            return {"success": False, "message": "❌ 缺少规则集名称"}

        # 检查名称是否已存在
        existing = self.db.query(RuleSet).filter(RuleSet.name == name).first()
        if existing:
            return {"success": False, "message": f"❌ 规则集 '{name}' 已存在"}

        ruleset = RuleSet(
            name=name,
            description=description,
        )
        self.db.add(ruleset)
        self.db.commit()
        self.db.refresh(ruleset)

        return {
            "success": True,
            "message": f"✅ 成功创建规则集：{name}",
            "data": {
                "id": ruleset.id,
                "name": ruleset.name,
                "description": ruleset.description,
            }
        }

    def _handle_list_rulesets(self, args: dict[str, Any]) -> dict[str, Any]:
        """获取规则集列表"""
        keyword = args.get("keyword", "").lower()

        rulesets = self.db.query(RuleSet).filter(RuleSet.is_active == True).all()

        if keyword:
            rulesets = [r for r in rulesets if keyword in r.name.lower() or keyword in (r.description or "").lower()]

        if not rulesets:
            return {"success": True, "message": "暂无规则集", "data": []}

        lines = [f"📋 共 {len(rulesets)} 个规则集：", ""]
        ruleset_info = []
        for r in rulesets:
            # 获取条目数量
            item_count = self.db.query(RuleSetItem).filter(RuleSetItem.ruleset_id == r.id).count()
            lines.append(f"#{r.id}  {r.name} ({item_count} 条)")
            if r.description:
                lines.append(f"    💬 {r.description}")
            lines.append("")
            ruleset_info.append({
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "item_count": item_count,
            })

        return {
            "success": True,
            "message": "\n".join(lines),
            "data": ruleset_info
        }

    def _handle_delete_ruleset(self, args: dict[str, Any]) -> dict[str, Any]:
        """删除规则集"""
        ruleset_id = args.get("ruleset_id")
        if not ruleset_id:
            return {"success": False, "message": "❌ 缺少 ruleset_id 参数"}

        ruleset = self.db.query(RuleSet).filter(RuleSet.id == ruleset_id).first()
        if not ruleset:
            return {"success": False, "message": f"❌ 规则集 ID {ruleset_id} 不存在"}

        ruleset_name = ruleset.name

        # 删除所有条目（级联删除应该会自动处理，但显式删除更安全）
        self.db.query(RuleSetItem).filter(RuleSetItem.ruleset_id == ruleset_id).delete()
        self.db.delete(ruleset)
        self.db.commit()

        return {"success": True, "message": f"✅ 成功删除规则集：{ruleset_name}"}

    def _handle_add_ruleset_item(self, args: dict[str, Any]) -> dict[str, Any]:
        """向规则集添加条目"""
        ruleset_name = args.get("ruleset_name")
        item_type = args.get("item_type")
        value = args.get("value")
        comment = args.get("comment", "")

        if not all([ruleset_name, item_type, value]):
            return {"success": False, "message": "❌ 缺少必要参数: ruleset_name, item_type, value"}

        # 查找规则集
        ruleset = self.db.query(RuleSet).filter(RuleSet.name == ruleset_name).first()
        if not ruleset:
            return {"success": False, "message": f"❌ 规则集 '{ruleset_name}' 不存在"}

        # 检查是否已存在相同条目
        existing = self.db.query(RuleSetItem).filter(
            RuleSetItem.ruleset_id == ruleset.id,
            RuleSetItem.item_type == item_type,
            RuleSetItem.value == value
        ).first()

        if existing:
            return {"success": False, "message": f"❌ 条目 '{item_type}: {value}' 已存在于规则集中"}

        # 获取当前最大排序值
        max_order = self.db.query(RuleSetItem).filter(
            RuleSetItem.ruleset_id == ruleset.id
        ).count()

        item = RuleSetItem(
            ruleset_id=ruleset.id,
            item_type=item_type,
            value=value,
            comment=comment,
            sort_order=max_order,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)

        return {
            "success": True,
            "message": f"✅ 成功添加条目到规则集 '{ruleset_name}': {item_type}, {value}",
            "data": {
                "id": item.id,
                "item_type": item.item_type,
                "value": item.value,
            }
        }

    def _handle_batch_set_sort_order(self, args: dict[str, Any]) -> dict[str, Any]:
        """批量设置规则的排序值"""
        sort_order = args.get("sort_order")
        keyword = args.get("keyword", "").lower()
        policy = args.get("policy")
        dry_run = args.get("dry_run", False)

        if sort_order is None:
            return {"success": False, "message": "❌ 缺少 sort_order 参数"}

        # 构建查询
        query = self.db.query(RuleConfig).filter(RuleConfig.device_id.is_(None))

        # 应用过滤条件
        if keyword:
            search_pattern = f"%{keyword}%"
            query = query.filter(
                (RuleConfig.value.like(search_pattern)) |
                (RuleConfig.policy.like(search_pattern)) |
                (RuleConfig.comment.like(search_pattern))
            )
        if policy:
            query = query.filter(RuleConfig.policy == policy)

        rules = query.all()

        if not rules:
            return {
                "success": True,
                "message": "未找到匹配的规则",
                "data": {"affected_count": 0}
            }

        # 预览或执行
        if dry_run:
            filter_desc = []
            if keyword:
                filter_desc.append(f"关键词: {keyword}")
            if policy:
                filter_desc.append(f"策略: {policy}")
            filter_info = f"（{', '.join(filter_desc)}）" if filter_desc else "（所有规则）"

            lines = [f"🔍 预览：将 {len(rules)} 条规则的 sort_order 设置为 {sort_order} {filter_info}：", ""]
            for r in rules[:20]:
                value = r.value[:40] + "..." if len(r.value or "") > 40 else r.value
                lines.append(f"  [ID:{r.id}] {r.rule_type}, {value} (当前: {r.sort_order})")
            if len(rules) > 20:
                lines.append(f"  ... 还有 {len(rules) - 20} 条规则")

            return {
                "success": True,
                "message": "\n".join(lines),
                "data": {"affected_count": len(rules), "preview": True}
            }
        else:
            # 执行批量更新
            for rule in rules:
                rule.sort_order = sort_order
            self.db.commit()

            filter_desc = []
            if keyword:
                filter_desc.append(f"关键词: {keyword}")
            if policy:
                filter_desc.append(f"策略: {policy}")
            filter_info = f"（{', '.join(filter_desc)}）" if filter_desc else ""

            return {
                "success": True,
                "message": f"✅ 成功将 {len(rules)} 条规则的 sort_order 设置为 {sort_order} {filter_info}",
                "data": {"affected_count": len(rules)}
            }

    def _handle_execute_sql(self, args: dict[str, Any]) -> dict[str, Any]:
        """执行任意 SQL 语句"""
        from sqlalchemy import text

        sql = args.get("sql")
        params = args.get("params", {})

        if not sql:
            return {"success": False, "message": "❌ 缺少 sql 参数"}

        sql = sql.strip()

        try:
            # 判断是查询还是修改操作
            sql_upper = sql.upper()
            is_select = sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")

            if is_select:
                # 执行查询
                result = self.db.execute(text(sql), params)
                rows = result.fetchall()
                columns = result.keys() if hasattr(result, 'keys') else []

                if not rows:
                    return {
                        "success": True,
                        "message": "查询成功，无结果",
                        "data": {"rows": [], "columns": list(columns)}
                    }

                # 格式化输出
                columns_list = list(columns)
                lines = [f"📊 查询结果（{len(rows)} 行）：", ""]

                # 表头
                if columns_list:
                    header = " | ".join(str(c) for c in columns_list)
                    lines.append(header)
                    lines.append("-" * len(header))

                # 数据行（限制显示 50 行）
                data_list = []
                for row in rows[:50]:
                    row_dict = dict(zip(columns_list, row))
                    data_list.append(row_dict)
                    row_str = " | ".join(str(v)[:30] for v in row)
                    lines.append(row_str)

                if len(rows) > 50:
                    lines.append(f"... 还有 {len(rows) - 50} 行未显示")

                return {
                    "success": True,
                    "message": "\n".join(lines),
                    "data": {
                        "columns": columns_list,
                        "rows": data_list,
                        "total_count": len(rows)
                    }
                }
            else:
                # 执行修改操作
                result = self.db.execute(text(sql), params)
                self.db.commit()

                affected = result.rowcount if hasattr(result, 'rowcount') else 0

                return {
                    "success": True,
                    "message": f"✅ SQL 执行成功，影响了 {affected} 行",
                    "data": {"affected_count": affected}
                }

        except Exception as e:
            self.db.rollback()
            return {
                "success": False,
                "message": f"❌ SQL 执行失败: {str(e)}"
            }
