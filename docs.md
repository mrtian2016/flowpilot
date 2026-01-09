# 个人智能 Agent（面向程序员工作流加速）开发需求文档 PRD

> 文档版本：v0.2 - AI Agent 核心架构
> 更新日期：2026-01-09
> 目标读者：产品/研发（你本人）、未来贡献者
> 关键词：**AI Agent/Claude Agent/Gemini Agent/LLM Agent/Model Context Protocol/MCP Tools**/工作流自主规划/SSH/K8s/安全可控/可审计

---

## 1. 背景与问题陈述

你（程序员）在日常工作中存在大量重复、机械、步骤繁琐的操作，例如：
- SSH 到不同环境/不同主机（含跳板机）、进入固定目录、执行一组命令、收集输出
- 查看/过滤日志、定位错误、提取关键上下文（traceId、requestId）、生成汇报
- 常见 DevOps/K8s 操作：切 context、找 pod、拉 logs、exec、rollout 检查
- CI/CD 失败排查：定位失败 stage、汇总错误、给出修复建议
- Git 操作：开分支、rebase、生成 changelog、PR 总结

当前痛点：
- 操作步骤多、上下文切换频繁、记忆负担大
- 手工执行容易出错（误连环境、误操作生产、忘记记录）
- 排障/发布后需要汇总，手工写报告耗时

---

## 2. 产品目标（Goals）

### 2.1 核心目标
1. **减少操作步骤**：把常见 10~30 步压缩成 1 条命令或一句话
2. **可控执行**：默认生成计划（Plan）+ 预演（Dry-run），关键写操作需确认
3. **可复现与可审计**：执行有完整记录（命令/目标/输出摘要/耗时/退出码）
4. **可扩展**：通过 Skills/插件机制快速增加能力，复用既有工具链（ssh/kubectl/git）

### 2.2 成功度量（Metrics）
- 日常高频场景（SSH、日志、K8s）节省时间 ≥ 50%
- 常用工作流一键化覆盖 ≥ 10 个（MVP 阶段 ≥ 3 个）
- 误操作（例如连错环境）显著降低：通过环境标识/策略确认机制实现
- 执行记录自动生成的汇报可直接用于工单/IM 群同步（减少手写）

---

## 3. 非目标（Non-Goals / 能力边界）

### 3.1 不做的事情（明确边界）
- **不做全自动“无人值守”生产变更**：默认不允许无确认的 destructive 操作
- **不替代配置管理/CMDB**：只做轻量资产与别名管理（host/service/context）
- **不保存明文密钥/Token**：仅引用系统 Keychain/ssh-agent/外部 Secret Manager
- **不承诺“理解所有自然语言”**：自然语言仅作为入口，最终必须落到结构化 Plan 执行
- **不做通用远程桌面/GUI 自动化**（MVP 不包含）

### 3.2 风险控制边界
- 生产环境（prod）相关操作必须：
  - 高亮提示 + 二次确认（可配置）
  - 强制策略校验（命令白名单/namespace 限制/只读优先）
  - 全量审计记录

---

## 4. 用户画像与使用场景

### 4.1 目标用户
- 单人开发者/工程师（你本人），偏 CLI、偏效率工具

### 4.2 Top 场景（示例）
1. SSH：`agent ssh prod-api-3` / `agent ssh prod "tail -n 200 /var/log/app.log"`
2. 日志排查：`agent logs payment --env prod --since 10m --level error --cluster traceId`
3. K8s 排障：`agent k pod payment --env prod --logs --since 10m`
4. CI 失败总结：`agent ci last-failed --repo xxx --summary`
5. 一键发布/回滚：`agent deploy payment --env staging`（MVP 可先只做 staging）

---

## 5. 总体方案与架构概览

### 5.1 核心架构（AI Agent First）

```
用户自然语言/结构化输入
         ↓
    Agent Core (Claude API)
    - 理解意图
    - 自主规划多步骤
    - 分析结果并总结
         ↓
    MCP Tool System (确定性执行)
    - SSH Tool
    - K8s Tool
    - Logs Tool
    - Git Tool (后续)
         ↓
    Policy Engine (策略校验层)
    - 风险评估
    - 强制确认
    - 操作拦截
         ↓
    Execution Layer (实际执行)
         ↓
    Audit Logger (全链路记录)
```

### 5.2 分层架构详解

#### **Agent 层（核心大脑）**
- **职责：**
  - 解析用户自然语言意图
  - 自主规划执行步骤（无需预定义 Workflow）
  - 调用 Tools 完成确定性操作
  - 分析执行结果，生成人类可读总结
- **实现：** 统一 LLM Provider 抽象层，支持多个提供商
- **支持的 LLM 提供商：**
  - **Claude (Anthropic)**: Sonnet 4.5 / Opus 4.5 - Tool Use 成熟、推理能力强
  - **Gemini (Google)**: Gemini 2.0 Flash / Pro - 速度快、成本低
  - **智谱 (GLM)**: GLM-4-Plus / GLM-4-Flash - 国内部署、合规友好
- **关键特性：**
  - 上下文保持（会话模式）
  - 多步骤推理与规划
  - 错误处理与重试策略
  - 动态切换 LLM 提供商（基于成本/速度/场景）

#### **Tool System 层（MCP 协议）**
- **职责：** 提供标准化的能力接口给 Agent
- **协议：** Model Context Protocol (MCP)
- **每个 Tool 包含：**
  - 标准化的输入 Schema（JSON Schema）
  - 确定性执行逻辑
  - 策略检查集成点
  - 结构化返回结果
- **优势：**
  - Agent 可动态发现 Tool 能力
  - 社区生态可复用（MCP servers）
  - 类型安全、可测试

#### **Policy Engine 层（安全核心）**
- **职责：**
  - 在 Tool 执行前强制检查
  - 风险评级（read/write/destructive）
  - 返回决策（allow/require_confirm/deny）
- **不可绕过：** 即使 Agent "尝试"绕过，Tool 侧强制执行
- **声明式规则：** YAML 配置，Agent 可理解策略原因

#### **交互层**
- **CLI（必选）**：主要入口，支持自然语言和结构化命令
- **TUI（后续）**：交互式确认、Plan 预览
- **VS Code 插件（后续）**：编辑器集成

#### **存储层**
- **配置：** YAML（hosts/services/policies）
- **审计记录：** SQLite（完整对话 + Tool 调用链）
- **会话状态：** 内存 + 可选持久化（支持"继续上次的排查"）

### 5.3 执行模式（Agent 驱动）

**模式 1：单步执行**
```
User: "查看 prod-api-3 的运行时间"
Agent: [分析] → [调用 ssh_exec tool] → [总结结果]
输出: "prod-api-3 已运行 45 天 3 小时"
```

**模式 2：多步规划（Agent 自主）**
```
User: "排查 payment 服务在生产环境的错误"
Agent 内部规划:
  1. 调用 logs tool 查看最近日志
  2. 发现 Database timeout，提取 traceId
  3. 调用 k8s_pod_status 检查 database pod
  4. 汇总分析根因
输出: 结构化报告 + 建议
```

**模式 3：需要确认（Policy 触发）**
```
User: "清理所有生产 API 服务器的临时文件"
Agent: [规划批量操作] → [调用 ssh_exec_batch]
Tool 返回: {status: "pending_confirm", ...}
Agent: 向用户展示详细信息（5台主机、命令、风险）
User: 确认
Agent: [带确认 token 再次调用] → [执行] → [总结结果]
```

### 5.4 关键设计决策

| 决策点 | 选择 | 原因 |
|--------|------|------|
| LLM 提供商 | **多提供商支持**（Claude / Gemini / 智谱） | 灵活切换、成本优化、避免单一依赖 |
| LLM 抽象层 | 统一 LLMProvider 接口 | 屏蔽不同 API 差异、支持动态切换 |
| Tool 协议 | MCP (Model Context Protocol) | 标准化、社区生态、跨平台支持 |
| 编程语言 | **Python 3.12** | 类型系统增强、性能提升、生态成熟 |
| 包管理器 | **uv** | 极速依赖解析、兼容 pip、现代化工具链 |
| 数据库 | **SQLite** | 零配置、单文件、足够审计日志需求 |
| 工作流编排 | Agent 自主规划（无预定义） | 灵活应对复杂场景、减少维护成本 |
| 安全模型 | Policy Engine + Tool 侧强制执行 | 防止 Agent "越狱"、可审计、可配置 |

---

## 6. 核心概念定义

### 6.1 Tool（工具）
Tool 是提供给 Agent 的"确定性能力单元"，基于 MCP 协议：

**Tool 的组成：**
```json
{
  "name": "ssh_exec",
  "description": "在远程主机执行 SSH 命令，支持配置别名",
  "input_schema": {
    "type": "object",
    "properties": {
      "host": {"type": "string", "description": "主机别名或地址"},
      "command": {"type": "string", "description": "要执行的命令"},
      "env": {"type": "string", "enum": ["dev", "staging", "prod"]}
    },
    "required": ["host", "command"]
  }
}
```

**Tool 的执行流程：**
1. Agent 根据用户意图决定调用哪个 Tool
2. Tool 收到请求 → 查询 Policy Engine
3. Policy Engine 返回决策（allow/require_confirm/deny）
4. 如需确认，返回详细预览信息给 Agent
5. 用户确认后，Tool 执行实际操作
6. 记录完整审计日志
7. 返回结构化结果给 Agent

**关键特性：**
- **幂等性：** 相同输入应产生相同结果
- **可测试：** 可 mock 外部依赖
- **策略集成：** 强制执行安全检查
- **详细返回：** 包含 exit_code、output、error、metadata

### 6.2 Agent Plan（执行规划）
Agent 自主生成的多步骤执行计划（非预定义 Workflow）：

**特点：**
- **动态生成：** 根据上下文和中间结果调整
- **条件分支：** 如果步骤 A 失败，执行步骤 B
- **并行执行：** 多个独立 Tool 可并发调用
- **错误恢复：** 自动重试或人工介入

**示例：Agent 处理"排查 payment 错误"**
```
[Agent 内部推理]
1. 先拉取 payment 服务日志（logs tool）
2. 如果发现错误模式 → 提取关键字段（traceId）
3. 查询 K8s pod 状态（k8s_pod_status tool）
4. 如果 pod 异常 → 查看 events（k8s_events tool）
5. 汇总分析 → 生成结构化报告
```

### 6.3 Policy Rule（策略规则）
声明式安全规则，在 Tool 执行前强制检查：

**规则示例：**
```yaml
- name: prod_write_protection
  condition:
    env: prod
    action_type: write  # 由 Tool 根据命令判断
  effect: require_confirm
  message: "生产环境写操作需要确认"

- name: batch_operation_limit
  condition:
    target_count: ">5"
  effect: require_confirm
  message: "批量操作超过 5 台主机需要确认"

- name: destructive_deny
  condition:
    env: prod
    action_type: destructive  # rm -rf /、mkfs、dd 等
  effect: deny
  message: "禁止在生产环境执行破坏性操作"
```

**Policy 决策：**
- `allow`: 直接执行
- `require_confirm`: 向用户展示详情，等待确认
- `deny`: 拒绝执行，返回错误

### 6.4 Audit Record（审计记录）
每次 Agent 会话的完整记录：

```json
{
  "session_id": "sess_20260109_103045",
  "timestamp": "2026-01-09T10:30:45Z",
  "user": "tianjy",
  "input": "清理生产 api-3 的临时文件",
  "agent_reasoning": "用户请求清理生产环境文件，需要调用 ssh_exec tool",
  "tool_calls": [
    {
      "tool": "ssh_exec",
      "args": {"host": "prod-api-3", "command": "rm -rf /tmp/cache", "env": "prod"},
      "policy_check": {
        "triggered": "prod_write_protection",
        "effect": "require_confirm",
        "user_confirmed": true,
        "confirm_time": "2026-01-09T10:31:00Z"
      },
      "execution": {
        "start": "2026-01-09T10:31:05Z",
        "end": "2026-01-09T10:31:07Z",
        "exit_code": 0,
        "output_summary": "已删除 245MB 文件"
      }
    }
  ],
  "final_output": "完成。已清理 prod-api-3 的 /tmp/cache (245MB)",
  "token_usage": {"input": 1250, "output": 340},
  "total_duration_sec": 22
}
```

---

## 7. 功能需求（Functional Requirements）

> 优先级：P0（MVP 必须）/ P1（增强）/ P2（后续）

### 7.1 CLI 交互（P0）

**核心交互模式：**
```bash
# 模式 1：自然语言（推荐）
agent "查看 prod-api-3 的最近 10 分钟日志"
agent "排查 payment 服务在生产环境的错误"

# 模式 2：结构化命令（向后兼容）
agent ssh prod-api-3 --cmd "uptime"
agent logs payment --env prod --since 10m

# 会话模式（保持上下文）
agent --session  # 进入交互式会话
> 查看 prod-api-3 的日志
> 继续查看最近 1 小时的错误
> 统计错误类型
```

**通用参数：**
- `--env <env>`: 强制指定环境（覆盖 Agent 推断）
- `--dry-run`: 仅生成 Plan，不实际执行
- `--yes`: 自动确认（仅对 require_confirm 生效，deny 仍拦截）
- `--json`: 输出结构化 JSON（供脚本调用）
- `--verbose`: 显示 Agent 推理过程和 Tool 调用详情
- `--session`: 进入会话模式（保持上下文）

**输出格式：**
```
默认人类可读输出：
----------------------------------------
🤖 正在分析请求...
📋 执行计划：
  1. [ssh_exec] 连接 prod-api-3，执行日志查询
  2. [分析] 提取错误模式并统计

⚙️  执行中...
✅ 完成

📊 结果：
发现 3 条 ERROR 日志：
- 11:23:45 Database timeout (traceId: abc123)
- 11:25:12 Payment gateway 503 (traceId: def456)
...

💡 建议：检查数据库连接池配置
----------------------------------------

--json 输出：
{
  "success": true,
  "plan": [...],
  "executions": [...],
  "summary": "...",
  "suggestions": [...]
}
```

**验收标准：**
- `agent --help` 展示自然语言示例和 Tool 列表
- 自然语言输入能正确理解意图（准确率 >90%）
- 错误提示友好，包含修复建议和示例
- `--dry-run` 能准确展示将要执行的 Tool 调用

---

### 7.2 配置与资产管理（P0）

**配置文件结构：** `~/.flowpilot/config.yaml`
```yaml
# 主机配置
hosts:
  prod-api-3:
    env: prod
    addr: 10.0.1.23
    user: ubuntu
    port: 22
    jump: bastion-prod
    tags: [api, payment]
    ssh_key: ~/.ssh/prod_rsa  # 可选，默认使用 ssh-agent

  staging-api-1:
    env: staging
    addr: staging-api-1.internal
    user: ubuntu
    tags: [api, payment]

# 跳板机配置
jumps:
  bastion-prod:
    addr: bastion.prod.example.com
    user: ubuntu
    port: 22

# 服务配置（供 Agent 理解服务拓扑）
services:
  payment:
    description: "支付服务"
    hosts:
      prod: [prod-api-1, prod-api-2, prod-api-3]
      staging: [staging-api-1]
    logs:
      path: /var/log/payment/app.log
      format: json  # json/text
    k8s:
      selector: app=payment
      namespace:
        prod: payments
        staging: payments-stg
    healthcheck:
      url: http://localhost:8080/health

# 策略配置
policies:
  - name: prod_write_protection
    condition:
      env: prod
      action_type: write
    effect: require_confirm

  - name: destructive_deny
    condition:
      env: prod
      action_type: destructive
    effect: deny
```

**配置校验：**
- 启动时自动校验配置文件
- 检查：重复别名、无效端口、循环跳板、不存在的引用
- 提供 `agent config validate` 命令

**验收标准：**
- Agent 能通过别名解析主机配置
- 支持跳板机多级跳转
- 配置错误有清晰的错误提示和行号
- `agent config list hosts --env prod` 能列出所有生产主机

---

### 7.3 Agent 核心能力（P0）

**Agent 必须具备的能力：**

#### 7.3.1 意图理解与 Tool 选择
```
输入："查看 prod-api-3 的磁盘使用"
Agent 推理：
- 目标主机：prod-api-3（从 hosts 配置解析）
- 环境：prod（从主机配置推断）
- 操作：查看磁盘（df 命令，读操作）
- Tool 选择：ssh_exec

生成 Tool 调用：
ssh_exec(host="prod-api-3", command="df -h", env="prod")
```

#### 7.3.2 多步骤规划与执行
```
输入："排查 payment 服务在生产环境的问题"
Agent 规划：
1. 先获取服务信息（从 services 配置）
2. 查看日志（logs tool 或 ssh_exec）
3. 如发现错误 → 提取关键信息（traceId/错误类型）
4. 检查服务健康状态（k8s_pod_status 或 healthcheck）
5. 汇总分析
```

#### 7.3.3 策略感知与确认流程
```
输入："删除 prod-api-3 的临时文件"
Agent：
1. 识别为写操作 + prod 环境
2. 调用 ssh_exec tool
3. Tool 触发 policy → 返回 pending_confirm
4. Agent 向用户展示：
   ⚠️  需要确认的生产环境操作：
   主机：prod-api-3 (10.0.1.23)
   命令：rm -rf /tmp/cache
   风险：删除文件（不可恢复）
   是否继续？[y/N]
5. 用户确认 → Agent 带 confirm_token 重新调用 Tool
```

#### 7.3.4 错误处理与恢复
- SSH 连接失败 → 检查跳板配置、提示检查网络
- 命令执行失败 → 分析 exit_code 和 stderr，给出建议
- Policy 拒绝 → 解释原因，建议修改策略或使用其他方式

**验收标准：**
- 至少支持 5 种常见自然语言表达变体
- 多步骤规划能根据中间结果动态调整
- Policy 触发的确认流程准确、信息完整
- 错误提示能定位问题并给出可行建议

---

### 7.4 审计与执行记录（P0）
- 每次执行记录：
  - request（用户输入）、resolved params、plan、实际执行命令、开始结束时间、exit code、输出摘要
- 查询能力：
  - 最近 N 次、按 env/host/service 过滤
  - 一键导出 Markdown 报告（用于同步/工单）

边界要求：
- 输出脱敏：默认对疑似密钥/Token/密码进行 mask（可配置规则）

验收标准：
- `agent history` 可查看最近执行
- `agent report <run_id>` 生成 Markdown 报告（不包含敏感信息）

---

## 8. P0 Tools 需求定义（MVP）

> 所有 Tools 基于 MCP 协议，提供给 Agent 调用

### 8.1 ssh_exec Tool（P0）

**Tool 定义：**
```json
{
  "name": "ssh_exec",
  "description": "在远程主机执行 SSH 命令，支持配置别名和跳板机",
  "input_schema": {
    "type": "object",
    "properties": {
      "host": {"type": "string", "description": "主机别名（如 prod-api-3）或地址"},
      "command": {"type": "string", "description": "要执行的 shell 命令"},
      "env": {"type": "string", "enum": ["dev", "staging", "prod"]},
      "timeout": {"type": "integer", "default": 30},
      "_confirm_token": {"type": "string", "description": "确认 token"}
    },
    "required": ["host", "command"]
  }
}
```

**执行逻辑：**
1. 解析 host 别名 → 查询 hosts 配置
2. 分类命令类型（read/write/destructive）
3. 查询 Policy Engine → 返回决策
4. 如需确认，返回 `{status: "pending_confirm", preview: {...}}`
5. 用户确认后，Agent 带 `_confirm_token` 再次调用
6. 执行 SSH 命令（支持跳板机）
7. 记录审计日志
8. 返回结构化结果

**命令分类规则：**
```python
destructive_keywords = ["rm -rf /", "mkfs", "dd if=", "shutdown", "reboot", "halt"]
write_keywords = ["rm", "mv", "cp", ">", ">>", "systemctl stop", "kill -9"]
# 其他默认为 read
```

**验收标准：**
- Agent 自然语言"查看 prod-api-3 的运行时间" → 正确调用此 Tool
- 支持多级跳板机（bastion → jump-host → target）
- prod 环境写操作触发确认流程
- 返回完整的 exit_code、stdout、stderr

---

### 8.2 ssh_exec_batch Tool（P0）

**Tool 定义：**
```json
{
  "name": "ssh_exec_batch",
  "description": "批量在多台主机执行相同命令",
  "input_schema": {
    "properties": {
      "hosts": {"type": "array", "items": {"type": "string"}},
      "tags": {"type": "object", "description": "标签过滤"},
      "command": {"type": "string"},
      "parallel": {"type": "boolean", "default": true},
      "continue_on_error": {"type": "boolean", "default": false}
    }
  }
}
```

**特殊处理：**
- 目标主机数 > 5 → 触发 `batch_operation_limit` 策略
- 并发执行时使用线程池，限制并发数（默认 10）
- 返回聚合结果：成功/失败统计、每台主机详情

**验收标准：**
- "检查所有生产 API 服务器的磁盘空间" → 正确调用并聚合结果
- 并发执行 10 台主机稳定
- 失败主机有清晰的错误提示

---

### 8.3 logs_fetch Tool（P0）

**Tool 定义：**
```json
{
  "name": "logs_fetch",
  "description": "从服务拉取日志并分析",
  "input_schema": {
    "properties": {
      "service": {"type": "string"},
      "env": {"type": "string"},
      "since": {"type": "string", "description": "如 10m、1h"},
      "level": {"type": "string", "enum": ["error", "warn", "info"]},
      "grep": {"type": "string"},
      "tail": {"type": "integer", "default": 100}
    },
    "required": ["service", "env"]
  }
}
```

**执行逻辑：**
1. 从 services 配置解析日志路径和主机列表
2. 调用 ssh_exec 拉取日志片段
3. 解析日志格式（JSON/text）
4. 提取关键字段（timestamp、level、message、traceId）
5. 按错误类型聚类（可选）
6. 返回结构化结果 + 样例

**增强功能（MVP 可选）：**
- Agent 自动分析日志模式，提取根因
- 关联 traceId，追踪完整请求链路

**验收标准：**
- "查看 payment 服务最近 10 分钟的错误" → 正确拉取并分类
- 时间窗解析准确（支持相对时间和绝对时间）
- traceId 提取准确率 >95%

---

### 8.4 k8s_pod_status Tool（P1，高频使用可提为 P0）

**Tool 定义：**
```json
{
  "name": "k8s_pod_status",
  "description": "查询 K8s pod 状态和日志",
  "input_schema": {
    "properties": {
      "service": {"type": "string"},
      "env": {"type": "string"},
      "namespace": {"type": "string"},
      "include_logs": {"type": "boolean", "default": false},
      "logs_since": {"type": "string", "default": "10m"},
      "include_events": {"type": "boolean", "default": false}
    },
    "required": ["service", "env"]
  }
}
```

**执行逻辑：**
1. 根据 env 切换 kubectl context
2. 使用 service selector 查找 pods
3. 获取 pod 状态（Running/CrashLoopBackOff/...）
4. 如 `include_logs=true`，拉取容器日志
5. 如 `include_events=true`，拉取相关 events

**验收标准：**
- "检查 payment 服务在生产的状态" → 返回 pod 状态和 restart 次数
- 自动切换正确的 kubectl context
- 如 pod 异常，提取关键错误信息

---

## 9. P1/P2 Tools（增强与后续）

### 9.1 git_操作 Tools（P1）
- `git_create_branch`: 创建并切换分支
- `git_sync`: 同步远程分支、rebase
- `git_changelog`: 生成 changelog
- `git_pr_summary`: 分析提交历史，生成 PR 描述草稿

### 9.2 ci_analyze Tool（P1）
- 拉取最近失败的 CI pipeline
- 分析失败阶段和错误日志
- Agent 自动归类错误类型并给出修复建议

### 9.3 deploy_service Tool（P2）
- staging 一键发布：build → push → deploy → healthcheck
- prod 发布：必须更严格策略、审批流程

---

## 10. 安全与策略（必须实现的硬约束）

### 10.1 策略系统（P0）

**策略维度：**
- `env`：prod/staging/dev
- `tool`：ssh_exec/k8s_pod_status/...
- `action_type`：read/write/destructive（由 Tool 判断）
- `target_scope`：host tags / namespace / 主机数量

**策略效果：**
- `allow`: 直接执行
- `require_confirm`: Tool 返回 pending_confirm，Agent 向用户确认
- `deny`: Tool 拒绝执行，返回错误

**实现要点：**
- Policy Engine 是独立模块，在 Tool 执行前强制调用
- 即使 Agent 尝试绕过，Tool 侧仍会执行检查
- 策略配置声明式（YAML），Agent 可理解策略原因

### 10.2 脱敏（P0）

**脱敏规则：**
```python
sensitive_patterns = [
    r'token["\s:=]+([a-zA-Z0-9_\-\.]+)',  # token=xxx
    r'password["\s:=]+([^\s"]+)',         # password: xxx
    r'secret["\s:=]+([^\s"]+)',           # secret: xxx
    r'Authorization:\s*Bearer\s+(\S+)',   # Bearer token
    r'-----BEGIN.*PRIVATE KEY-----'       # SSH/TLS keys
]

def mask_sensitive(text: str) -> str:
    for pattern in sensitive_patterns:
        text = re.sub(pattern, r'\1***MASKED***', text)
    return text
```

**适用范围：**
- Agent 输出给用户的内容
- 审计日志中的 stdout/stderr
- Report 导出

### 10.3 认证与密钥（P0）

**SSH 认证：**
- 优先使用 `ssh-agent`（最安全）
- 支持 `~/.ssh/config` 配置引用
- 可配置特定主机的 key 路径（存在 hosts 配置中）
- **禁止：** 明文存储私钥内容

**其他凭证（K8s/CI API）：**
- 从环境变量读取：`KUBECONFIG`、`GITHUB_TOKEN`
- 支持外部 Secret Manager（AWS Secrets Manager/HashiCorp Vault）
- **禁止：** 在 config.yaml 或 SQLite 中存明文 token

**Claude API Key：**
- 从环境变量 `ANTHROPIC_API_KEY` 或 `CLAUDE_API_KEY` 读取
- 启动时检查，缺失时友好提示

---

## 12. 可用性与体验（UX Requirements）
- 交互反馈：
  - 计划预览可读（步骤编号、目标、风险标识）
  - 执行时显示进度与耗时
  - 并发执行有聚合输出（成功/失败汇总）
- 错误处理：
  - 网络/权限/命令失败的错误分类
  - 给出下一步建议（比如“请检查跳板配置/密钥权限/namespace”）

---

## 13. 数据结构（完整示例）

### 13.1 config.yaml（统一配置文件）

```yaml
# ~/.flowpilot/config.yaml

# LLM 提供商配置
llm:
  # 默认使用的提供商（claude | gemini | zhipu）
  default_provider: claude

  # 按场景选择提供商（可选）
  providers:
    claude:
      model: claude-sonnet-4.5  # claude-sonnet-4.5 | claude-opus-4.5
      api_key_env: ANTHROPIC_API_KEY
      max_tokens: 4096
      temperature: 0.7

    gemini:
      model: gemini-2.0-flash-exp  # gemini-2.0-flash-exp | gemini-2.0-pro-exp
      api_key_env: GOOGLE_API_KEY
      max_tokens: 8192
      temperature: 0.7

    zhipu:
      model: glm-4-plus  # glm-4-plus | glm-4-flash
      api_key_env: ZHIPU_API_KEY
      max_tokens: 4096
      temperature: 0.7

  # 场景路由规则（可选，高级功能）
  routing:
    - scenario: quick_query  # 快速查询用 Flash 模型
      provider: gemini
      model: gemini-2.0-flash-exp
    - scenario: complex_analysis  # 复杂分析用 Claude
      provider: claude
      model: claude-opus-4.5
    - scenario: china_compliance  # 国内合规用智谱
      provider: zhipu

# 主机配置
hosts:
  prod-api-3:
    env: prod
    user: ubuntu
    addr: 10.0.1.23
    port: 22
    jump: bastion-prod
    tags: [api, payment]
    ssh_key: ~/.ssh/prod_rsa  # 可选

  staging-api-1:
    env: staging
    addr: staging-api-1.internal
    user: ubuntu
    tags: [api, payment]

# 跳板机配置
jumps:
  bastion-prod:
    addr: bastion.prod.example.com
    user: ubuntu
    port: 22

# 服务配置
services:
  payment:
    description: "支付服务"
    hosts:
      prod: [prod-api-1, prod-api-2, prod-api-3]
      staging: [staging-api-1]
    logs:
      path: /var/log/payment/app.log
      format: json  # json | text
    k8s:
      selector: app=payment
      namespace:
        prod: payments
        staging: payments-stg
    healthcheck:
      url: http://localhost:8080/health

# 策略配置
policies:
  - name: prod_write_protection
    condition:
      env: prod
      action_type: write
    effect: require_confirm
    message: "生产环境写操作需要确认"

  - name: batch_operation_limit
    condition:
      target_count: ">5"
    effect: require_confirm
    message: "批量操作超过 5 台主机需要确认"

  - name: destructive_deny
    condition:
      env: prod
      action_type: destructive
    effect: deny
    message: "禁止在生产环境执行破坏性操作"
```

### 13.2 Tool Definition（MCP 格式）

```json
{
  "name": "ssh_exec",
  "description": "在远程主机执行 SSH 命令，支持配置别名和跳板机",
  "input_schema": {
    "type": "object",
    "properties": {
      "host": {
        "type": "string",
        "description": "主机别名（如 prod-api-3）或地址"
      },
      "command": {
        "type": "string",
        "description": "要执行的 shell 命令"
      },
      "env": {
        "type": "string",
        "enum": ["dev", "staging", "prod"],
        "description": "环境（影响策略检查）"
      },
      "timeout": {
        "type": "integer",
        "default": 30,
        "description": "超时时间（秒）"
      },
      "_confirm_token": {
        "type": "string",
        "description": "确认 token（策略要求确认时使用）"
      }
    },
    "required": ["host", "command"]
  }
}
```

### 13.3 Tool Response（标准返回格式）

**成功响应：**
```json
{
  "status": "success",
  "host": "prod-api-3",
  "command": "uptime",
  "exit_code": 0,
  "stdout": "10:30:45 up 45 days,  3:21,  1 user",
  "stderr": "",
  "duration_sec": 1.2,
  "metadata": {
    "resolved_addr": "10.0.1.23",
    "jump_used": "bastion-prod",
    "user": "ubuntu"
  }
}
```

**需要确认响应：**
```json
{
  "status": "pending_confirm",
  "host": "prod-api-3",
  "command": "rm -rf /tmp/cache",
  "policy_triggered": "prod_write_protection",
  "message": "生产环境写操作需要确认",
  "risk_level": "high",
  "preview": {
    "host_info": "prod-api-3 (10.0.1.23)",
    "command": "rm -rf /tmp/cache",
    "action_type": "write",
    "env": "prod",
    "estimated_impact": "删除文件（不可恢复）"
  },
  "confirm_token": "conf_20260109_103045_abc123"
}
```

**错误响应：**
```json
{
  "status": "error",
  "error_type": "PolicyDenied",
  "message": "禁止在生产环境执行破坏性操作",
  "policy_triggered": "destructive_deny",
  "suggestion": "请使用 staging 环境测试，或联系管理员修改策略"
}
```

### 13.4 Audit Record（审计日志格式）

```json
{
  "session_id": "sess_20260109_103045",
  "timestamp": "2026-01-09T10:30:45Z",
  "user": "tianjy",
  "hostname": "macbook-pro.local",
  "input": "删除 prod-api-3 的临时文件",
  "input_mode": "natural_language",

  "agent_reasoning": "用户请求清理生产环境文件，需要调用 ssh_exec tool",

  "tool_calls": [
    {
      "call_id": "call_001",
      "tool": "ssh_exec",
      "args": {
        "host": "prod-api-3",
        "command": "rm -rf /tmp/cache",
        "env": "prod"
      },
      "policy_check": {
        "triggered": "prod_write_protection",
        "effect": "require_confirm",
        "user_confirmed": true,
        "confirm_time": "2026-01-09T10:31:00Z"
      },
      "execution": {
        "start": "2026-01-09T10:31:05Z",
        "end": "2026-01-09T10:31:07Z",
        "exit_code": 0,
        "stdout_summary": "已删除 245MB 文件（脱敏）",
        "stderr": "",
        "duration_sec": 2.1
      }
    }
  ],

  "final_output": "完成。已清理 prod-api-3 的 /tmp/cache (245MB)",
  "status": "completed",
  "token_usage": {
    "input": 1250,
    "output": 340,
    "total": 1590
  },
  "total_duration_sec": 22,
  "cost_usd": 0.024
}
```

---

## 14. 兼容性与运行环境

### 14.1 技术栈决策

**核心技术栈：**
- **编程语言**: Python 3.12
- **包管理器**: uv (替代 pip/poetry)
- **数据库**: SQLite 3.44+
- **LLM 提供商**: Claude / Gemini / 智谱（多提供商支持）

**选择理由：**

**Python 3.12:**
- ✅ 类型系统增强（PEP 695 Generic Type Syntax）
- ✅ 性能提升（~10% 相比 3.11）
- ✅ 丰富的库生态（Pydantic、Rich、Typer、Paramiko）
- ✅ AI/ML 社区首选语言

**uv:**
- ✅ **极速依赖解析**（比 pip 快 10-100 倍）
- ✅ 兼容 pip/requirements.txt/pyproject.toml
- ✅ 现代化工具链（类似 Rust 的 cargo）
- ✅ 内置虚拟环境管理

**SQLite:**
- ✅ 零配置、单文件数据库
- ✅ 足够审计日志需求（百万级记录）
- ✅ 支持 JSON 字段（SQLite 3.38+）
- ✅ 跨平台、无依赖

**多 LLM 提供商:**
- ✅ **Claude**: Tool Use 最成熟、推理能力强
- ✅ **Gemini**: 速度快、成本低（Flash 模型）
- ✅ **智谱**: 国内部署、数据合规
- ✅ 避免单一 API 依赖、成本优化

### 14.2 系统要求

**操作系统：**
- ✅ macOS 12+ (主要开发和使用环境)
- ✅ Linux (Ubuntu 20.04+, Debian 11+, RHEL 8+)
- ⚠️  Windows: WSL2 支持（原生 Windows 后续）

**必需软件：**
- Python 3.12+ (推荐使用 pyenv 安装)
- uv >= 0.1.0 (包管理器)
- SQLite 3.44+ (通常系统自带)
- SSH 客户端（系统自带）

**可选依赖：**
- kubectl（如使用 K8s Tool）
- git（如使用 Git Tools）

**网络要求：**
- LLM API 访问（Claude/Gemini/智谱）
- 目标主机 SSH 访问（含跳板机）

### 14.3 安装方式

**方式 1: 使用 uv (推荐)**
```bash
# 1. 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 克隆项目
git clone https://github.com/yourusername/flowpilot
cd flowpilot

# 3. 创建虚拟环境并安装依赖（uv 自动管理）
uv sync

# 4. 激活环境
source .venv/bin/activate  # macOS/Linux

# 5. 初始化配置
flowpilot init
# 生成 ~/.flowpilot/config.yaml 模板
```

**方式 2: 使用 pipx (独立安装)**
```bash
# 安装 pipx（如未安装）
python3.12 -m pip install --user pipx
python3.12 -m pipx ensurepath

# 安装 flowpilot
pipx install flowpilot --python python3.12

# 初始化
flowpilot init
```

**方式 3: 开发模式（源码安装）**
```bash
git clone https://github.com/yourusername/flowpilot
cd flowpilot

# 使用 uv 安装开发依赖
uv sync --all-extras

# 安装为可编辑模式
uv pip install -e .
```

**设置 API Keys:**
```bash
# ~/.bashrc 或 ~/.zshrc
export ANTHROPIC_API_KEY="sk-ant-..."       # Claude
export GOOGLE_API_KEY="AIza..."             # Gemini
export ZHIPU_API_KEY="..."                  # 智谱

# 或使用 .env 文件（项目根目录）
# flowpilot 会自动加载
cat > ~/.flowpilot/.env <<EOF
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...
ZHIPU_API_KEY=...
EOF
```

---

## 15. 测试与验收（Test Plan）

### 15.1 单元测试（P0）

**测试范围：**
- ✅ 配置加载与校验（Pydantic models）
- ✅ Policy Engine 决策逻辑（allow/require_confirm/deny）
- ✅ 命令分类（read/write/destructive）
- ✅ 脱敏规则匹配
- ✅ 时间窗解析（10m、1h、绝对时间）

**测试框架：** pytest + pytest-cov

```bash
pytest tests/unit/ --cov=flowpilot --cov-report=html
```

### 15.2 集成测试（P0）

**测试范围：**
- ✅ Mock SSH 连接（使用 pytest-mock）
- ✅ Mock Claude API 响应
- ✅ Tool 执行流程（含 Policy 检查）
- ✅ 并发执行稳定性
- ✅ 超时与重试机制
- ✅ 审计日志完整性

**Mock 策略：**
```python
# 避免真实环境操作
@pytest.fixture
def mock_ssh_client(mocker):
    mock = mocker.patch('paramiko.SSHClient')
    mock.return_value.exec_command.return_value = (
        None,  # stdin
        io.BytesIO(b"mock output"),  # stdout
        io.BytesIO(b"")  # stderr
    )
    return mock
```

### 15.3 E2E 测试（手工验收，P0 最少 10 条）

**基础功能：**
1. ✅ `agent "查看 staging-api-1 的运行时间"` → 正确执行 SSH 命令
2. ✅ `agent "删除 staging 的临时文件"` → 触发确认流程
3. ✅ `agent "查看 payment 服务日志"` → 从 services 配置解析并拉取日志

**策略与安全：**
4. ✅ prod 环境写操作 → 触发 `require_confirm`
5. ✅ prod 环境破坏性操作 → 被 `deny` 拦截
6. ✅ 批量操作 >5 台主机 → 触发确认
7. ✅ 日志输出包含 token → 自动脱敏

**并发与错误处理：**
8. ✅ 批量执行 10 台主机 → 并发稳定，聚合结果正确
9. ✅ SSH 连接失败 → 错误提示清晰，包含诊断建议
10. ✅ Agent 理解失败 → 进入澄清流程或给出候选

**审计与报告：**
11. ✅ `agent history --last 5` → 显示最近执行记录
12. ✅ `agent report <session_id>` → 生成 Markdown 报告（脱敏）

**多步规划：**
13. ✅ "排查 payment 错误" → Agent 自主多步执行 → 生成分析报告

---

## 16. 里程碑与范围（Roadmap）

### **Milestone 1：最小 Agent 循环（2-3周）**

**目标：** 验证 AI Agent + Tool 的核心架构可行性

**交付物：**
- ✅ Claude API 集成（Tool Use 能力）
- ✅ MCP Tool System 基础框架
- ✅ ssh_exec Tool（支持别名、跳板机、命令分类）
- ✅ Policy Engine（基础策略检查 + 确认流程）
- ✅ 配置系统（hosts.yaml + policies.yaml）
- ✅ 审计日志（SQLite，记录完整会话）
- ✅ CLI 入口（支持自然语言和结构化命令）

**验收标准：**
```bash
# 自然语言
agent "查看 prod-api-3 的运行时间"
→ Agent 理解意图 → 调用 ssh_exec tool → 返回结果

# 确认流程
agent "删除 prod-api-3 的临时文件"
→ 触发 prod_write_protection 策略 → 展示详情 → 等待确认 → 执行

# 审计
agent history --last 5
→ 显示最近 5 次执行记录
```

---

### **Milestone 2：增强 Tools + 多步规划（1-2周）**

**目标：** Agent 能自主规划多步骤任务

**交付物：**
- ✅ ssh_exec_batch Tool（批量并发执行）
- ✅ logs_fetch Tool（日志拉取 + 字段提取）
- ✅ Agent 多步骤规划能力（根据中间结果动态调整）
- ✅ 会话模式（保持上下文）
- ✅ 错误处理与恢复策略

**验收标准：**
```bash
agent "排查 payment 服务在生产环境的错误"
→ Agent 自动：
  1. 调用 logs_fetch 查日志
  2. 发现 Database timeout，提取 traceId
  3. 再次调用 logs_fetch 过滤 traceId
  4. 汇总分析 → 生成报告

agent "检查所有生产 API 服务器的磁盘空间"
→ 调用 ssh_exec_batch → 并发执行 → 聚合结果
```

---

### **Milestone 3：K8s + Report + 优化（1-2周）**

**目标：** 覆盖常见运维场景，体验优化

**交付物：**
- ✅ k8s_pod_status Tool（如需要）
- ✅ Report 导出（Markdown 格式，可复制粘贴）
- ✅ 脱敏增强（自动识别敏感信息）
- ✅ 性能优化（并发、超时、重试）
- ✅ 错误提示优化（详细诊断 + 修复建议）

**验收标准：**
```bash
agent "检查 payment 服务的 K8s pod 状态"
→ 切换 context → 查找 pods → 返回状态 + events

agent report <session_id>
→ 生成包含完整执行过程的 Markdown 报告
```

---

### **Milestone 4：扩展能力（P1/P2）**

- Git Tools（分支管理、PR 总结）
- CI Tools（失败分析）
- Deploy Tools（一键发布）
- TUI 界面（更友好的交互）
- VS Code 插件（编辑器集成）
- 知识库（Runbook 检索 + RAG）

---

## 17. 技术实现建议

### 17.1 项目结构（Python 3.12）
```
flowpilot/
├── pyproject.toml            # uv 项目配置
├── uv.lock                   # 依赖锁文件
├── .python-version           # Python 版本 (3.12)
├── src/
│   └── flowpilot/
│       ├── __init__.py
│       ├── agent/
│       │   ├── __init__.py
│       │   ├── base.py           # LLM Provider 抽象接口
│       │   ├── claude.py         # Claude Provider 实现
│       │   ├── gemini.py         # Gemini Provider 实现
│       │   ├── zhipu.py          # 智谱 Provider 实现
│       │   ├── conversation.py   # 会话管理
│       │   ├── executor.py       # Tool 调用执行器
│       │   └── router.py         # 场景路由（选择 LLM）
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── base.py           # MCP Tool 基类
│       │   ├── ssh.py            # SSH Tools
│       │   ├── logs.py           # Logs Tools
│       │   └── k8s.py            # K8s Tools (可选)
│       ├── policy/
│       │   ├── __init__.py
│       │   ├── engine.py         # 策略引擎
│       │   ├── rules.py          # 规则匹配
│       │   └── action_classifier.py
│       ├── config/
│       │   ├── __init__.py
│       │   ├── loader.py         # 配置加载
│       │   ├── schema.py         # Pydantic models
│       │   └── defaults.py
│       ├── audit/
│       │   ├── __init__.py
│       │   ├── logger.py         # 审计日志（SQLite）
│       │   ├── models.py         # SQLAlchemy models
│       │   └── reporter.py       # Report 生成
│       ├── cli/
│       │   ├── __init__.py
│       │   └── main.py           # Typer CLI 入口
│       └── utils/
│           ├── __init__.py
│           ├── sensitive.py      # 脱敏工具
│           └── time_parser.py    # 时间窗解析
└── tests/
    ├── unit/
    │   ├── test_providers.py
    │   ├── test_tools.py
    │   └── test_policy.py
    └── integration/
        ├── test_agent_flow.py
        └── test_ssh_execution.py
```

### 17.2 核心依赖（pyproject.toml）

```toml
[project]
name = "flowpilot"
version = "0.1.0"
description = "AI Agent for programmer workflow automation"
requires-python = ">=3.12"
dependencies = [
    # LLM SDKs
    "anthropic>=0.40.0",              # Claude
    "google-generativeai>=0.8.0",     # Gemini
    "zhipuai>=2.1.0",                 # 智谱 GLM

    # 核心框架
    "pydantic>=2.8",                  # Schema 校验与配置
    "pydantic-settings>=2.0",         # 环境变量配置

    # CLI
    "typer>=0.12.0",                  # CLI 框架
    "rich>=13.0",                     # 美化输出
    "prompt-toolkit>=3.0",            # 交互式输入

    # 数据存储
    "sqlalchemy>=2.0",                # ORM
    "alembic>=1.13",                  # 数据库迁移

    # SSH & 工具
    "paramiko>=3.4",                  # SSH 客户端
    "asyncssh>=2.14",                 # 异步 SSH（可选）

    # 配置解析
    "pyyaml>=6.0",                    # YAML 解析
    "python-dotenv>=1.0",             # .env 文件支持

    # 实用工具
    "httpx>=0.27",                    # HTTP 客户端（K8s API）
    "tenacity>=8.0",                  # 重试机制
    "python-dateutil>=2.8",           # 时间解析
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "pytest-mock>=3.14",
    "pytest-asyncio>=0.23",
    "ruff>=0.5.0",                    # Linter & Formatter
    "mypy>=1.11",                     # 类型检查
]

[project.scripts]
flowpilot = "flowpilot.cli.main:app"
agent = "flowpilot.cli.main:app"      # 别名

[tool.uv]
dev-dependencies = [
    "pytest>=8.0",
    "ruff>=0.5.0",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.mypy]
python_version = "3.12"
strict = true
```

### 17.3 LLM Provider 抽象层设计

**基础接口（agent/base.py）：**
```python
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

class LLMProvider(ABC):
    """统一的 LLM Provider 接口"""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs
    ) -> dict[str, Any]:
        """发送聊天请求，返回响应"""
        pass

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs
    ) -> AsyncIterator[dict[str, Any]]:
        """流式聊天响应"""
        pass

    @property
    @abstractmethod
    def supports_tool_use(self) -> bool:
        """是否支持 Tool Use（Function Calling）"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider 名称"""
        pass
```

**Claude 实现（agent/claude.py）：**
```python
import anthropic
from .base import LLMProvider

class ClaudeProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4.5"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    async def chat(self, messages, tools=None, **kwargs):
        response = self.client.messages.create(
            model=self.model,
            messages=messages,
            tools=tools or [],
            **kwargs
        )
        return self._normalize_response(response)

    def _normalize_response(self, response):
        """统一返回格式"""
        return {
            "content": response.content,
            "model": response.model,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            "tool_calls": self._extract_tool_calls(response),
        }

    @property
    def supports_tool_use(self) -> bool:
        return True

    @property
    def name(self) -> str:
        return "claude"
```

**Provider 工厂（agent/router.py）：**
```python
from .base import LLMProvider
from .claude import ClaudeProvider
from .gemini import GeminiProvider
from .zhipu import ZhipuProvider

class ProviderRouter:
    """根据配置选择 LLM Provider"""

    def __init__(self, config: dict):
        self.config = config
        self._providers: dict[str, LLMProvider] = {}

    def get_provider(self, scenario: str = None) -> LLMProvider:
        """根据场景选择 Provider"""
        provider_name = self._route(scenario)

        if provider_name not in self._providers:
            self._providers[provider_name] = self._create_provider(provider_name)

        return self._providers[provider_name]

    def _route(self, scenario: str | None) -> str:
        """场景路由逻辑"""
        if scenario and "routing" in self.config:
            for rule in self.config["routing"]:
                if rule["scenario"] == scenario:
                    return rule["provider"]

        return self.config.get("default_provider", "claude")

    def _create_provider(self, name: str) -> LLMProvider:
        config = self.config["providers"][name]
        api_key = os.getenv(config["api_key_env"])

        match name:
            case "claude":
                return ClaudeProvider(api_key, config["model"])
            case "gemini":
                return GeminiProvider(api_key, config["model"])
            case "zhipu":
                return ZhipuProvider(api_key, config["model"])
            case _:
                raise ValueError(f"Unknown provider: {name}")
```

### 17.4 环境变量
```bash
# LLM API Keys（至少配置一个）
export ANTHROPIC_API_KEY="sk-ant-..."       # Claude
export GOOGLE_API_KEY="AIza..."             # Gemini
export ZHIPU_API_KEY="..."                  # 智谱

# 可选配置
export FLOWPILOT_CONFIG="~/.flowpilot/config.yaml"
export FLOWPILOT_LOG_LEVEL="INFO"
export KUBECONFIG="~/.kube/config"          # K8s 工具需要
```

---

## 18. 多 LLM 提供商策略

### 18.1 使用场景建议

| 场景 | 推荐提供商 | 原因 |
|------|-----------|------|
| **复杂任务规划** | Claude Opus 4.5 | 推理能力最强，多步骤规划准确 |
| **日常简单查询** | Gemini Flash | 速度快（<1s），成本低 |
| **国内部署/合规** | 智谱 GLM-4 | 数据不出境，符合合规要求 |
| **成本敏感** | Gemini Flash | 价格最低，适合高频调用 |
| **Tool Use 复杂度高** | Claude Sonnet | Tool Use 能力最成熟 |

### 18.2 成本对比（估算）

| 提供商 | 模型 | Input ($/1M tokens) | Output ($/1M tokens) | 典型会话成本 |
|--------|------|---------------------|---------------------|-------------|
| Claude | Sonnet 4.5 | $3 | $15 | $0.02-0.05 |
| Claude | Opus 4.5 | $15 | $75 | $0.10-0.20 |
| Gemini | Flash 2.0 | $0.075 | $0.30 | $0.001-0.003 |
| Gemini | Pro 2.0 | $1.25 | $5 | $0.01-0.03 |
| 智谱 | GLM-4-Plus | ¥0.05/1K | ¥0.05/1K | ¥0.01-0.03 |
| 智谱 | GLM-4-Flash | ¥0.001/1K | ¥0.001/1K | ¥0.0005-0.002 |

*典型会话：1500 input tokens + 500 output tokens*

### 18.3 动态切换策略（高级功能）

**示例：根据任务复杂度自动选择**
```python
# config.yaml
llm:
  routing:
    - scenario: quick_query
      condition:
        input_length: "<100"  # 输入短
      provider: gemini
      model: gemini-2.0-flash-exp

    - scenario: complex_task
      condition:
        has_keywords: ["排查", "分析", "多步骤"]
      provider: claude
      model: claude-sonnet-4.5

    - scenario: china_only
      condition:
        target_region: "china"
      provider: zhipu
      model: glm-4-plus
```

**CLI 手动切换：**
```bash
# 使用默认 provider
agent "查看日志"

# 强制使用 Gemini（快速便宜）
agent "查看日志" --provider gemini

# 强制使用 Claude Opus（复杂任务）
agent "排查复杂错误" --provider claude --model opus-4.5

# 会话模式下切换
agent --session
> 查看日志
> /switch gemini  # 切换到 Gemini
> 继续分析
```

### 18.4 降级策略（容错）

当主 Provider 失败时，自动降级到备用：

```python
# 自动降级顺序
fallback_chain = ["claude", "gemini", "zhipu"]

# 场景：
# 1. Claude API rate limit → 自动切换到 Gemini
# 2. Gemini 不可用 → 切换到智谱
# 3. 所有 Provider 失败 → 友好错误提示
```

---

## 19. 开放问题（需明确）

在开始实施前需要确认：

### 19.1 使用场景
1. **你最高频的 3 个场景是什么？**
   - 决定 MVP 重点 Tool
   - 示例：SSH > Logs > K8s 还是其他顺序

2. **是否重度使用跳板机？**
   - 影响 SSH 连接复杂度

3. **是否需要 K8s Tool？**
   - 如果日常不用 K8s，可以 P1 或不做

4. **日志格式主要是什么？**
   - JSON 结构化日志 vs 纯文本日志
   - 影响日志解析逻辑

### 19.2 LLM 提供商选择
5. **主要使用哪个 LLM 提供商？**
   - Claude（推理强但贵）
   - Gemini（快速便宜）
   - 智谱（国内合规）
   - 混合使用？

6. **是否需要成本优化？**
   - 如需要，优先实现场景路由

7. **是否有数据合规要求？**
   - 如有国内合规需求，优先智谱

### 19.3 部署与协作
8. **是否需要团队共享配置？**
   - 本地 YAML vs Git 仓库同步

9. **是否需要审计日志集中存储？**
   - SQLite 本地 vs 远程数据库

---

## 20. 附录：术语表

- **Agent**: AI 智能体，负责理解意图、规划、分析结果
- **LLM Provider**: 大语言模型提供商（Claude/Gemini/智谱）
- **Tool**: 确定性能力单元（基于 MCP 协议），提供给 Agent 调用
- **MCP**: Model Context Protocol，标准化的 Tool 协议
- **Policy Engine**: 策略引擎，在 Tool 执行前强制检查安全规则
- **Policy Rule**: 策略规则，声明式定义（YAML）
- **Action Type**: 操作类型（read/write/destructive）
- **Audit Record**: 审计记录，完整的会话执行日志
- **Confirm Token**: 确认令牌，用户确认后 Agent 带此 token 重新调用 Tool
- **Provider Router**: LLM 提供商路由器，根据场景选择最优 Provider
- **uv**: 现代 Python 包管理器，比 pip/poetry 更快

---

## 21. 后续可扩展方向

1. **多模态能力**
   - 上传截图 → Agent 分析错误信息
   - 图表生成（日志趋势、性能指标）

2. **知识库集成（RAG）**
   - 存储 Runbook、故障案例
   - Agent 自动检索相关文档

3. **团队协作**
   - 共享审计记录
   - Playbook 模板市场

4. **更多入口**
   - Slack/Discord Bot
   - Web Dashboard
   - VS Code / JetBrains 插件

5. **企业集成**
   - Jira（自动创建工单）
   - Sentry（关联错误追踪）
   - Grafana（查询指标）
   - PagerDuty（告警响应）