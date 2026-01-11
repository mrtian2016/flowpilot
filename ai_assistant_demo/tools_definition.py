"""AI 助手工具定义

定义 AI 可调用的工具列表，支持 OpenAI 和 Gemini 格式。
"""

# ============ 工具定义 ============

TOOLS_DEFINITION = [
    {
        "type": "function",
        "function": {
            "name": "create_rule",
            "description": """创建一条代理规则。支持简单规则和复合规则（AND/OR/NOT）。

简单规则类型: DOMAIN、DOMAIN-SUFFIX、DOMAIN-KEYWORD、IP-CIDR、GEOIP、RULE-SET 等。

复合规则类型 AND: 用于组合多个条件，所有条件都满足时匹配。
AND 规则的 value 格式: ((条件1), (条件2), ...)
常用条件:
- NOT,((SUBNET,ROUTER:路由器IP)) - 不在指定路由器子网时匹配
- IP-CIDR,网段 - 目标 IP 在指定网段时匹配
- SUBNET,ROUTER:路由器IP - 在指定路由器子网时匹配

示例: 当不在办公室(路由器10.21.21.254)时，访问10.21.21.0/24走代理:
rule_type="AND", value="((NOT,((SUBNET,ROUTER:10.21.21.254))), (IP-CIDR,10.21.21.0/24))", policy="代理组名"
""",
            "parameters": {
                "type": "object",
                "properties": {
                    "rule_type": {
                        "type": "string",
                        "description": "规则类型。简单类型直接指定，复合规则使用 AND/OR/NOT",
                        "enum": [
                            "DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD", "DOMAIN-SET",
                            "IP-CIDR", "IP-CIDR6", "GEOIP", "IP-ASN", "RULE-SET",
                            "USER-AGENT", "URL-REGEX", "PROCESS-NAME",
                            "DEST-PORT", "SRC-PORT", "PROTOCOL", "FINAL",
                            "AND", "OR", "NOT", "SUBNET"
                        ]
                    },
                    "value": {
                        "type": "string",
                        "description": "规则值。简单规则: 域名/IP等。AND规则: ((条件1), (条件2)) 格式"
                    },
                    "policy": {
                        "type": "string",
                        "description": "目标策略。例如：'DIRECT'（直连）、'REJECT'（拒绝）、'节点选择'（策略组名称）"
                    },
                    "comment": {
                        "type": "string",
                        "description": "规则注释/备注（可选）"
                    }
                },
                "required": ["rule_type", "value", "policy"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_rules",
            "description": "查询现有的代理规则列表，支持按关键词搜索。返回规则的完整信息包括 ID、类型、值、策略、注释。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词，用于匹配规则的 value、policy（策略名）或 comment 字段（可选）"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回的规则数量上限，默认 20",
                        "default": 20
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_rule",
            "description": "删除指定 ID 的规则",
            "parameters": {
                "type": "object",
                "properties": {
                    "rule_id": {
                        "type": "integer",
                        "description": "要删除的规则 ID"
                    }
                },
                "required": ["rule_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_proxy_groups",
            "description": "获取可用的策略组列表，用于确定规则应该使用哪个策略",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_rule",
            "description": "修改现有规则的策略、注释或排序",
            "parameters": {
                "type": "object",
                "properties": {
                    "rule_id": {
                        "type": "integer",
                        "description": "要修改的规则 ID"
                    },
                    "policy": {
                        "type": "string",
                        "description": "新的策略（可选）"
                    },
                    "comment": {
                        "type": "string",
                        "description": "新的注释（可选）"
                    },
                    "sort_order": {
                        "type": "integer",
                        "description": "新的排序值（可选，数字越小优先级越高）"
                    }
                },
                "required": ["rule_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "batch_set_sort_order",
            "description": "批量设置规则的排序值。可以将所有规则或匹配条件的规则设置为指定的 sort_order 值",
            "parameters": {
                "type": "object",
                "properties": {
                    "sort_order": {
                        "type": "integer",
                        "description": "要设置的排序值"
                    },
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词，只更新匹配的规则（可选，不提供则更新所有规则）"
                    },
                    "policy": {
                        "type": "string",
                        "description": "策略名称，只更新使用该策略的规则（可选）"
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "是否只预览而不实际修改（默认 false）",
                        "default": False
                    }
                },
                "required": ["sort_order"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_proxies",
            "description": "查询代理节点列表",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词（可选）"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_config_summary",
            "description": "获取当前配置的完整摘要，包含规则、策略组、代理等信息",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_hosts",
            "description": "查询主机映射列表（DNS Host 配置）",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词（可选）"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_host",
            "description": "创建主机映射，将域名映射到指定 IP 或其他域名",
            "parameters": {
                "type": "object",
                "properties": {
                    "hostname": {
                        "type": "string",
                        "description": "源主机名/域名"
                    },
                    "target": {
                        "type": "string",
                        "description": "目标 IP 或域名"
                    },
                    "description": {
                        "type": "string",
                        "description": "描述（可选）"
                    }
                },
                "required": ["hostname", "target"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_host",
            "description": "删除主机映射",
            "parameters": {
                "type": "object",
                "properties": {
                    "host_id": {
                        "type": "integer",
                        "description": "主机映射 ID"
                    }
                },
                "required": ["host_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_general_configs",
            "description": "查询通用配置项列表",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词（可选）"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_general_config",
            "description": "修改通用配置项的值",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "配置键名"
                    },
                    "value": {
                        "type": "string",
                        "description": "新的配置值"
                    }
                },
                "required": ["key", "value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "batch_replace_policy",
            "description": "批量替换规则中的策略名称。例如：将所有使用 'QTCloudSmart' 策略的规则改为 'QTCloudSelect'",
            "parameters": {
                "type": "object",
                "properties": {
                    "old_policy": {
                        "type": "string",
                        "description": "要替换的旧策略名称"
                    },
                    "new_policy": {
                        "type": "string",
                        "description": "新的策略名称"
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "是否只预览而不实际修改（默认 false）",
                        "default": False
                    }
                },
                "required": ["old_policy", "new_policy"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_proxy_group",
            "description": "创建代理组（策略组），支持 select（手动选择）、url-test（自动测速）、fallback（故障转移）、load-balance（负载均衡）等类型",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "策略组名称，如 '节点选择'、'自动选择'"
                    },
                    "group_type": {
                        "type": "string",
                        "enum": ["select", "url-test", "fallback", "load-balance", "smart"],
                        "description": "策略组类型"
                    },
                    "members": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "成员列表，可以是代理名称、其他策略组名、DIRECT、REJECT"
                    },
                    "description": {
                        "type": "string",
                        "description": "描述（可选）"
                    }
                },
                "required": ["name", "group_type", "members"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_proxy_group",
            "description": "更新代理组配置，可以修改名称、类型、成员列表等",
            "parameters": {
                "type": "object",
                "properties": {
                    "group_id": {
                        "type": "integer",
                        "description": "要更新的代理组 ID"
                    },
                    "name": {
                        "type": "string",
                        "description": "新的策略组名称（可选）"
                    },
                    "group_type": {
                        "type": "string",
                        "enum": ["select", "url-test", "fallback", "load-balance", "smart"],
                        "description": "新的策略组类型（可选）"
                    },
                    "members": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "新的成员列表（可选）"
                    },
                    "description": {
                        "type": "string",
                        "description": "新的描述（可选）"
                    }
                },
                "required": ["group_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_proxy_group",
            "description": "删除代理组。注意：会检查是否有规则引用该策略组，如果有则拒绝删除",
            "parameters": {
                "type": "object",
                "properties": {
                    "group_id": {
                        "type": "integer",
                        "description": "要删除的代理组 ID"
                    }
                },
                "required": ["group_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_proxy",
            "description": "创建代理节点。支持协议：trojan, ss (Shadowsocks), snell, http, socks5, wireguard。不同协议需要的参数不同（通过 params 传递）",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "代理节点名称（必须唯一）"
                    },
                    "protocol": {
                        "type": "string",
                        "enum": ["trojan", "ss", "snell", "http", "socks5", "wireguard"],
                        "description": "代理协议类型"
                    },
                    "server": {
                        "type": "string",
                        "description": "服务器地址（IP 或域名）"
                    },
                    "port": {
                        "type": "integer",
                        "description": "服务器端口"
                    },
                    "params": {
                        "type": "object",
                        "description": "协议特定参数。例如 Trojan: {\"password\": \"xxx\"}, SS: {\"encrypt-method\": \"aes-256-gcm\", \"password\": \"xxx\"}, WireGuard: {\"section-name\": \"xxx\"}"
                    },
                    "description": {
                        "type": "string",
                        "description": "节点描述（可选）"
                    }
                },
                "required": ["name", "protocol", "server", "port"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_proxy",
            "description": "更新代理节点配置。可以更新名称、服务器地址、端口、协议参数等",
            "parameters": {
                "type": "object",
                "properties": {
                    "proxy_id": {
                        "type": "integer",
                        "description": "要更新的代理节点 ID"
                    },
                    "name": {
                        "type": "string",
                        "description": "新的节点名称（可选）"
                    },
                    "server": {
                        "type": "string",
                        "description": "新的服务器地址（可选）"
                    },
                    "port": {
                        "type": "integer",
                        "description": "新的端口（可选）"
                    },
                    "params": {
                        "type": "object",
                        "description": "新的协议参数（可选）"
                    },
                    "description": {
                        "type": "string",
                        "description": "新的描述（可选）"
                    }
                },
                "required": ["proxy_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_proxy",
            "description": "删除代理节点。注意：会检查是否有代理组引用该节点，如果有则拒绝删除",
            "parameters": {
                "type": "object",
                "properties": {
                    "proxy_id": {
                        "type": "integer",
                        "description": "要删除的代理节点 ID"
                    }
                },
                "required": ["proxy_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move_rule_up",
            "description": "将规则向上移动一位（优先级提高）。规则顺序决定匹配优先级",
            "parameters": {
                "type": "object",
                "properties": {
                    "rule_id": {
                        "type": "integer",
                        "description": "要上移的规则 ID"
                    }
                },
                "required": ["rule_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move_rule_down",
            "description": "将规则向下移动一位（优先级降低）",
            "parameters": {
                "type": "object",
                "properties": {
                    "rule_id": {
                        "type": "integer",
                        "description": "要下移的规则 ID"
                    }
                },
                "required": ["rule_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "reorder_rules",
            "description": "批量重新排序规则。传入规则 ID 和新的排序位置的映射关系",
            "parameters": {
                "type": "object",
                "properties": {
                    "orders": {
                        "type": "array",
                        "description": "排序列表，每项包含 id 和 sort_order",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "sort_order": {"type": "integer"}
                            }
                        }
                    }
                },
                "required": ["orders"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "batch_delete_rules",
            "description": "批量删除匹配条件的规则。支持按关键词、规则类型、策略筛选。默认为预览模式（dry_run=true），需要确认后设置 dry_run=false 才会真正删除",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词（在 value/policy/comment 中匹配）"
                    },
                    "rule_type": {
                        "type": "string",
                        "description": "规则类型（如 DOMAIN-SUFFIX, IP-CIDR 等）"
                    },
                    "policy": {
                        "type": "string",
                        "description": "策略名称（如 DIRECT, REJECT 等）"
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "是否为预览模式（默认 true）。设为 false 才会真正执行删除",
                        "default": True
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "batch_update_comments",
            "description": "批量为多条规则添加或更新注释",
            "parameters": {
                "type": "object",
                "properties": {
                    "rule_ids": {
                        "type": "array",
                        "description": "要更新的规则 ID 列表",
                        "items": {"type": "integer"}
                    },
                    "comment": {
                        "type": "string",
                        "description": "要设置的注释内容"
                    }
                },
                "required": ["rule_ids", "comment"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_wireguard_peer_service",
            "description": "创建 WireGuard 对端服务（全局共享）。对端服务可被多个 WireGuard 配置引用",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "对端服务名称（必须唯一）"
                    },
                    "public_key": {
                        "type": "string",
                        "description": "对端公钥"
                    },
                    "endpoint": {
                        "type": "string",
                        "description": "对端端点（格式: IP:Port）"
                    },
                    "allowed_ips": {
                        "type": "string",
                        "description": "允许的 IP 段（如 0.0.0.0/0）"
                    },
                    "preshared_key": {
                        "type": "string",
                        "description": "预共享密钥（可选）"
                    },
                    "keepalive": {
                        "type": "integer",
                        "description": "保持连接间隔（秒，可选）"
                    },
                    "description": {
                        "type": "string",
                        "description": "服务描述（可选）"
                    }
                },
                "required": ["name", "public_key", "endpoint", "allowed_ips"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_wireguard_peer_services",
            "description": "列出所有 WireGuard 对端服务",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词（在名称/描述中匹配）"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_wireguard_peer_service",
            "description": "更新 WireGuard 对端服务",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_id": {
                        "type": "integer",
                        "description": "要更新的对端服务 ID"
                    },
                    "name": {
                        "type": "string",
                        "description": "新的服务名称（可选）"
                    },
                    "public_key": {
                        "type": "string",
                        "description": "新的公钥（可选）"
                    },
                    "endpoint": {
                        "type": "string",
                        "description": "新的端点（可选）"
                    },
                    "allowed_ips": {
                        "type": "string",
                        "description": "新的允许 IP 段（可选）"
                    },
                    "preshared_key": {
                        "type": "string",
                        "description": "新的预共享密钥（可选）"
                    },
                    "keepalive": {
                        "type": "integer",
                        "description": "新的保持连接间隔（可选）"
                    },
                    "description": {
                        "type": "string",
                        "description": "新的描述（可选）"
                    }
                },
                "required": ["service_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_wireguard_peer_service",
            "description": "删除 WireGuard 对端服务。注意：会检查是否有 WireGuard 配置在使用，如果有则拒绝删除",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_id": {
                        "type": "integer",
                        "description": "要删除的对端服务 ID"
                    }
                },
                "required": ["service_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_wireguard_config",
            "description": "创建 WireGuard 配置。每个配置关联一个对端服务",
            "parameters": {
                "type": "object",
                "properties": {
                    "peer_service_id": {
                        "type": "integer",
                        "description": "关联的对端服务 ID"
                    },
                    "section_name": {
                        "type": "string",
                        "description": "配置节名称（在 Surge 中使用，必须唯一）"
                    },
                    "private_key": {
                        "type": "string",
                        "description": "本地私钥"
                    },
                    "self_ip": {
                        "type": "string",
                        "description": "本地 IP 地址（IPv4）"
                    },
                    "self_ip_v6": {
                        "type": "string",
                        "description": "本地 IPv6 地址（可选）"
                    },
                    "dns_server": {
                        "type": "string",
                        "description": "DNS 服务器（可选）"
                    },
                    "mtu": {
                        "type": "integer",
                        "description": "MTU 值（可选）"
                    },
                    "description": {
                        "type": "string",
                        "description": "配置描述（可选）"
                    }
                },
                "required": ["peer_service_id", "section_name", "private_key", "self_ip"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_wireguard_configs",
            "description": "列出所有 WireGuard 配置",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词（在 section_name/描述中匹配）"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_wireguard_config",
            "description": "更新 WireGuard 配置",
            "parameters": {
                "type": "object",
                "properties": {
                    "config_id": {
                        "type": "integer",
                        "description": "要更新的配置 ID"
                    },
                    "section_name": {
                        "type": "string",
                        "description": "新的节名称（可选）"
                    },
                    "private_key": {
                        "type": "string",
                        "description": "新的私钥（可选）"
                    },
                    "self_ip": {
                        "type": "string",
                        "description": "新的本地 IP（可选）"
                    },
                    "self_ip_v6": {
                        "type": "string",
                        "description": "新的本地 IPv6（可选）"
                    },
                    "dns_server": {
                        "type": "string",
                        "description": "新的 DNS 服务器（可选）"
                    },
                    "mtu": {
                        "type": "integer",
                        "description": "新的 MTU 值（可选）"
                    },
                    "description": {
                        "type": "string",
                        "description": "新的描述（可选）"
                    }
                },
                "required": ["config_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_wireguard_config",
            "description": "删除 WireGuard 配置",
            "parameters": {
                "type": "object",
                "properties": {
                    "config_id": {
                        "type": "integer",
                        "description": "要删除的配置 ID"
                    }
                },
                "required": ["config_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_config_history",
            "description": "查看配置历史记录（版本控制）。可查看某个资源的所有修改历史",
            "parameters": {
                "type": "object",
                "properties": {
                    "resource_type": {
                        "type": "string",
                        "enum": ["rule", "proxy", "proxy_group", "host", "wireguard_config", "wireguard_peer_service"],
                        "description": "资源类型"
                    },
                    "resource_id": {
                        "type": "integer",
                        "description": "资源 ID（可选，不提供则显示该类型的所有历史）"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回记录数限制（默认 20）",
                        "default": 20
                    }
                },
                "required": ["resource_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rollback_config",
            "description": "回滚配置到指定的历史版本。可以恢复误删除或误修改的配置",
            "parameters": {
                "type": "object",
                "properties": {
                    "version_id": {
                        "type": "integer",
                        "description": "要回滚到的版本记录 ID（从 list_config_history 获取）"
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": "确认执行回滚操作（默认 false，需明确设置为 true）",
                        "default": False
                    }
                },
                "required": ["version_id"]
            }
        }
    },
    # ============ 规则集管理 ============
    {
        "type": "function",
        "function": {
            "name": "create_ruleset",
            "description": "创建一个规则集，用于组织和管理 IP 网段、域名等地址集合。可以在创建时同时添加条目。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "规则集名称（唯一）"
                    },
                    "description": {
                        "type": "string",
                        "description": "规则集描述（可选）"
                    },
                    "items": {
                        "type": "array",
                        "description": "初始条目列表（可选）",
                        "items": {
                            "type": "object",
                            "properties": {
                                "item_type": {
                                    "type": "string",
                                    "enum": ["IP-CIDR", "IP-CIDR6", "DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD"],
                                    "description": "条目类型"
                                },
                                "value": {
                                    "type": "string",
                                    "description": "条目值，如 '10.0.0.0/8' 或 'google.com'"
                                },
                                "comment": {
                                    "type": "string",
                                    "description": "条目注释（可选）"
                                }
                            },
                            "required": ["item_type", "value"]
                        }
                    }
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_rulesets",
            "description": "查询规则集列表。返回所有规则集的基本信息和条目数量。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词，匹配名称或描述（可选）"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_ruleset",
            "description": "获取规则集详情，包含所有条目。",
            "parameters": {
                "type": "object",
                "properties": {
                    "ruleset_id": {
                        "type": "integer",
                        "description": "规则集 ID"
                    },
                    "name": {
                        "type": "string",
                        "description": "规则集名称（可通过名称查找）"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_ruleset",
            "description": "更新规则集的名称或描述。",
            "parameters": {
                "type": "object",
                "properties": {
                    "ruleset_id": {
                        "type": "integer",
                        "description": "规则集 ID"
                    },
                    "name": {
                        "type": "string",
                        "description": "新的规则集名称（可选）"
                    },
                    "description": {
                        "type": "string",
                        "description": "新的描述（可选）"
                    },
                    "is_active": {
                        "type": "boolean",
                        "description": "是否启用（可选）"
                    }
                },
                "required": ["ruleset_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_ruleset",
            "description": "删除规则集（会同时删除所有条目）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "ruleset_id": {
                        "type": "integer",
                        "description": "规则集 ID"
                    }
                },
                "required": ["ruleset_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_ruleset_items",
            "description": "向规则集添加条目（支持批量添加）。可以通过 ruleset_id 或 ruleset_name 指定目标规则集。",
            "parameters": {
                "type": "object",
                "properties": {
                    "ruleset_id": {
                        "type": "integer",
                        "description": "规则集 ID（与 ruleset_name 二选一）"
                    },
                    "ruleset_name": {
                        "type": "string",
                        "description": "规则集名称（与 ruleset_id 二选一，推荐使用）"
                    },
                    "items": {
                        "type": "array",
                        "description": "要添加的条目列表",
                        "items": {
                            "type": "object",
                            "properties": {
                                "item_type": {
                                    "type": "string",
                                    "enum": ["IP-CIDR", "IP-CIDR6", "DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD"],
                                    "description": "条目类型"
                                },
                                "value": {
                                    "type": "string",
                                    "description": "条目值"
                                },
                                "comment": {
                                    "type": "string",
                                    "description": "条目注释（可选）"
                                }
                            },
                            "required": ["item_type", "value"]
                        }
                    }
                },
                "required": ["items"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_ruleset_item",
            "description": "删除规则集中的指定条目。",
            "parameters": {
                "type": "object",
                "properties": {
                    "ruleset_id": {
                        "type": "integer",
                        "description": "规则集 ID"
                    },
                    "item_id": {
                        "type": "integer",
                        "description": "条目 ID"
                    }
                },
                "required": ["ruleset_id", "item_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_wireguard_full",
            "description": """一次性创建完整的 WireGuard 配置（包括对端服务和配置）。

当用户提供 WireGuard 配置文件（包含 [Interface] 和 [Peer]）时，使用此工具一次性完成创建。

此工具会自动：
1. 创建对端服务 (Peer)
2. 创建 WireGuard 配置，关联到对端服务
3. 如果指定了设备，还会创建 WireGuard 类型的代理节点

示例：用户说"根据这个配置为 iPhone 创建 WireGuard"
调用：create_wireguard_full(
    name="MyWG",
    private_key="xxx",
    self_ip="10.8.0.7",
    public_key="yyy",
    endpoint="wg.example.com:51820",
    allowed_ips="0.0.0.0/0",
    device_name="iPhone"
)
""",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "配置名称（用于对端服务名和配置节名）"
                    },
                    "private_key": {
                        "type": "string",
                        "description": "本地私钥 [Interface] PrivateKey"
                    },
                    "self_ip": {
                        "type": "string",
                        "description": "本地 IP 地址 [Interface] Address（不含掩码，如 10.8.0.7）"
                    },
                    "public_key": {
                        "type": "string",
                        "description": "对端公钥 [Peer] PublicKey"
                    },
                    "endpoint": {
                        "type": "string",
                        "description": "对端地址 [Peer] Endpoint（如 wg.example.com:51820）"
                    },
                    "allowed_ips": {
                        "type": "string",
                        "description": "允许的 IP 范围 [Peer] AllowedIPs（如 0.0.0.0/0, ::/0）"
                    },
                    "preshared_key": {
                        "type": "string",
                        "description": "[Peer] PresharedKey（可选）"
                    },
                    "dns_server": {
                        "type": "string",
                        "description": "[Interface] DNS（可选）"
                    },
                    "device_name": {
                        "type": "string",
                        "description": "要关联的设备名称（可选，如 iPhone、MacBook）"
                    }
                },
                "required": ["name", "private_key", "self_ip", "public_key", "endpoint", "allowed_ips"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "extract_to_ruleset",
            "description": """从现有规则中提取 IP/域名，添加到指定规则集。

这是一个组合操作工具，用于：
1. 查询指定策略的所有规则
2. 从规则的 value 中解析出 IP-CIDR、DOMAIN、DOMAIN-SUFFIX 等值
3. 将解析出的值添加到目标规则集的条目中

注意：此操作不会删除或修改原有规则，只是提取值到规则集。

示例：用户说"把 QTCloudSelect 相关的 IP 放到规则集中"
调用：extract_to_ruleset(policy="QTCloudSelect", ruleset_name="QTCloud-IPs")
""",
            "parameters": {
                "type": "object",
                "properties": {
                    "policy": {
                        "type": "string",
                        "description": "策略名称，用于筛选规则（如 QTCloudSelect、DIRECT 等）"
                    },
                    "ruleset_name": {
                        "type": "string",
                        "description": "目标规则集名称"
                    },
                    "include_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要提取的类型列表，默认为 ['IP-CIDR', 'IP-CIDR6', 'DOMAIN', 'DOMAIN-SUFFIX', 'DOMAIN-KEYWORD']"
                    }
                },
                "required": ["policy", "ruleset_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_host",
            "description": "更新主机映射的目标地址或描述",
            "parameters": {
                "type": "object",
                "properties": {
                    "host_id": {
                        "type": "integer",
                        "description": "主机映射 ID"
                    },
                    "target": {
                        "type": "string",
                        "description": "新的目标 IP 或域名（可选）"
                    },
                    "description": {
                        "type": "string",
                        "description": "新的描述（可选）"
                    }
                },
                "required": ["host_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_general_config",
            "description": "删除通用配置项",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "要删除的配置键名"
                    }
                },
                "required": ["key"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_devices",
            "description": "获取设备列表，包括设备名称、类型等信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词（可选）"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_general_config",
            "description": "创建新的通用配置项",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "配置键名"
                    },
                    "value": {
                        "type": "string",
                        "description": "配置值"
                    },
                    "description": {
                        "type": "string",
                        "description": "配置描述（可选）"
                    }
                },
                "required": ["key", "value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_device",
            "description": "创建新设备",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "设备名称（如 iPhone、MacBook）"
                    },
                    "description": {
                        "type": "string",
                        "description": "设备描述（可选）"
                    }
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_device",
            "description": "删除设备。注意：会检查设备是否有关联配置，如果有则提示用户",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "integer",
                        "description": "要删除的设备 ID"
                    }
                },
                "required": ["device_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": """执行任意 SQL 语句。支持 SELECT 查询和 UPDATE/INSERT/DELETE 等修改操作。

数据库表结构：
- rule_configs: id, rule_type, value, policy, comment, sort_order, is_active, device_id
- proxy_configs: id, name, protocol, server, port, params(JSON), is_active, device_id
- proxy_group_configs: id, name, group_type, members(JSON), params(JSON), is_active, device_id
- host_configs: id, hostname, target, description, is_active, device_id
- general_configs: id, key, value, description, sort_order, is_active, device_id
- wireguard_configs: id, device_id, peer_service_id, section_name, private_key, self_ip, ...
- wireguard_peer_services: id, name, public_key, endpoint, allowed_ips, ...
- rule_sets: id, name, description, is_active
- rule_set_items: id, ruleset_id, item_type, value, comment, sort_order
- devices: id, user_id, name, description

注意：修改操作会直接影响数据库，请谨慎使用。""",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "要执行的 SQL 语句"
                    },
                    "params": {
                        "type": "object",
                        "description": "SQL 参数（可选，用于参数化查询）"
                    }
                },
                "required": ["sql"]
            }
        }
    }
]


# Gemini 格式的工具定义
GEMINI_TOOLS_DEFINITION = [
    {
        "name": tool["function"]["name"],
        "description": tool["function"]["description"],
        "parameters": tool["function"]["parameters"]
    }
    for tool in TOOLS_DEFINITION
]
