# Cursor + Local Coding Agent 设计方案

O>
> 核心思想：**Cloud Brain + Local Executor**。

---

## 1. 项目目标

希望实现如下开发体验：

```text
用户：
“给这个项目增加 JWT 登录功能”
                    │
                    ▼
              Cursor Online Model
                    │
             Planner / Reviewer
                    │
                  Skill
                    │
               Subagent
               local-coder
                    │
                   MCP
                    │
                    ▼
          Local Agent Gateway
                    │
               Model Router
                    │
                    ▼
        Qwen3-Coder-30B-A3B-Q4
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
      Code        Shell       Test
        │           │           │
        └───────────┼───────────┘
                    ▼
             Git Diff / Result
                    │
                    ▼
             Hooks / Gate
                    │
                    ▼
           Cursor Online Reviewer
                    │
              ┌─────┴─────┐
              ▼           ▼
             Fix         Pass
              │
              └──────► Local Agent
```

最终目标不是简单地“让 Cursor 使用本地模型”，而是：

> **让在线强模型负责思考和调度，让本地模型负责大量具体 Coding 工作。**

---

# 2. 参考项目与借鉴思路

本方案主要借鉴两个方向。

## 2.1 codex-from-chatgpt

参考：

- `joseanu/codex-from-chatgpt`

核心思想：

```text
Remote Brain
     │
     ▼
MCP
     │
     ▼
Local Job
     │
     ▼
Local Agent
     │
     ▼
Compact Result
     │
     ▼
Remote Brain
```

值得借鉴：

1. 在线模型负责上层决策。
2. 本地 Agent 负责实际执行。
3. MCP 作为远程模型和本地执行环境之间的桥梁。
4. 本地任务采用 Job / Task 的形式管理。
5. 执行结果以结构化、紧凑的形式返回给上层模型。

本项目进一步把：

```text
Local Codex
```

替换为：

```text
Local Agent Runtime
        │
        ▼
Qwen3-Coder
```

---

## 2.2 director

参考：

- `manziman/director`

核心思想：

```text
Large Task
    │
    ▼
Specification
    │
    ▼
Task DAG
    │
    ▼
Atomic Tasks
    │
    ▼
Executor
    │
    ▼
Deterministic Gate
    │
    ▼
Reviewer
    │
    ├── Pass
    │
    └── Retry / Escalation
```

主要借鉴：

- Planner / Executor / Reviewer 分工
- Task DAG
- Atomic Task
- Acceptance Criteria
- Deterministic Gate
- Retry
- Escalation
- Git / Worktree 隔离思路

第一版本不需要完整复制 `director`，只实现上述核心生命周期。

---

# 3. 总体架构

```text
                         ┌───────────────────────┐
                         │        Cursor         │
                         │                       │
                         │    Online Model       │
                         │                       │
                         │ Planner / Reviewer    │
                         └───────────┬───────────┘
                                     │
                                   Skill
                                     │
                         ┌───────────▼───────────┐
                         │      local-dev        │
                         │        Skill          │
                         └───────────┬───────────┘
                                     │
                                  Subagent
                                     │
                         ┌───────────▼───────────┐
                         │      local-coder      │
                         └───────────┬───────────┘
                                     │
                                    MCP
                                     │
                         ┌───────────▼───────────┐
                         │   Local Agent Gateway │
                         │                        │
                         │ Task Manager           │
                         │ Context Manager        │
                         │ Agent Runtime          │
                         │ Model Router            │
                         │ Test Runner             │
                         │ Git Manager             │
                         │ Retry Manager           │
                         └───────────┬────────────┘
                                     │
                              ┌──────▼──────┐
                              │ Model Router│
                              └──────┬──────┘
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                ▼                ▼
             Qwen3-Coder         DeepSeek          Devstral
              Primary             Future            Future
               Worker             Worker            Worker
                    │
                    ▼
          ┌───────────────────────┐
          │ Local Workspace       │
          │                       │
          │ Files / Shell / Git   │
          │ Build / Test          │
          └───────────┬───────────┘
                      │
                      ▼
                 Hooks / Gates
                      │
                      ▼
                  Reviewer
                      │
                      └──────────────► Cursor
```

---

# 4. 四项 Cursor 机制的职责

四项机制不是互相替代，而是分别负责不同层次。

| 机制 | 主要职责 | 本方案中的定位 |
|---|---|---|
| Skills | 描述工作流程和规则 | Workflow Contract |
| MCP | 连接外部工具和本地 Agent | Bridge |
| Subagents | 委派独立任务 | Delegation |
| Hooks | 自动化检查、控制和 Gate | Control / Validation |

---

# 5. Skills

## 5.1 作用

Skill 负责告诉 Cursor：

> “遇到 Coding 任务时，应该如何使用 Local Agent。”

建议：

```text
.cursor/
└── skills/
    └── local-dev/
        └── SKILL.md
```

---

## 5.2 Skill 工作流

核心规则：

```text
用户需求
    │
    ▼
理解需求
    │
    ▼
分析 Repository
    │
    ▼
任务拆解
    │
    ▼
定义 Acceptance Criteria
    │
    ▼
调用 local-coder
    │
    ▼
获取执行结果
    │
    ▼
Review
    │
    ├── PASS
    │
    └── FAIL
          │
          ▼
       Retry
```

---

## 5.3 SKILL.md 建议内容

```markdown
---
name: local-dev
description: Delegate implementation tasks to the local coding agent.
---

# Local Development Workflow

## Principle

Cursor is the planner and reviewer.

The local coding agent is the implementation executor.

## Workflow

1. Understand the user's request.
2. Inspect the repository.
3. Break the task into atomic implementation units.
4. Define acceptance criteria.
5. Delegate implementation to `local-coder`.
6. Wait for the result.
7. Review changed files and test results.
8. If failed, delegate a correction task.
9. Repeat until acceptance criteria pass.
10. Perform final review.

## Delegation

Use MCP tool:

local_agent_execute

Provide:

- task
- repository
- files
- constraints
- acceptance criteria
- test command

## Completion

A task is complete only when:

- implementation exists
- tests pass
- git diff is acceptable
- no unrelated files changed
- acceptance criteria are satisfied
```

---

# 6. Subagent：local-coder

需要特别区分：

```text
Cursor Subagent
       ≠
Local Model
```

Subagent 是 Cursor 在线模型侧的一个“委托角色”。

架构：

```text
Cursor Online Model
        │
        ▼
   local-coder
        │
        ▼
       MCP
        │
        ▼
Local Agent Gateway
        │
        ▼
      Qwen
```

`local-coder` 的职责：

1. 接收 Cursor Planner 的任务。
2. 调用 Local Agent MCP。
3. 等待本地任务完成。
4. 获取执行结果。
5. 将结果返回给 Cursor。

---

# 7. MCP：核心桥接层

MCP Server 是 Cursor 和 Local Agent Gateway 的桥。

第一版不需要暴露大量底层工具给 Cursor。

推荐暴露高层 Agent API。

## 7.1 推荐工具

### local_agent_execute

提交一个本地 Coding Task。

```json
{
  "task_id": "task-001",
  "workspace": "/workspace/project",
  "objective": "Implement JWT authentication",
  "files": [
    "src/auth",
    "src/user"
  ],
  "acceptance": [
    "login API exists",
    "JWT access token is returned",
    "refresh token is supported",
    "unit tests pass"
  ],
  "test_command": "pytest tests/auth"
}
```

### local_agent_status

```json
{
  "task_id": "task-001"
}
```

返回：

```json
{
  "task_id": "task-001",
  "status": "running",
  "iteration": 3
}
```

### local_agent_result

```json
{
  "task_id": "task-001"
}
```

返回：

```json
{
  "status": "success",
  "summary": "JWT login implemented",
  "files_changed": [
    "auth/jwt.go",
    "auth/login.go",
    "auth/jwt_test.go"
  ],
  "tests": {
    "passed": 28,
    "failed": 0
  },
  "diff_summary": "..."
}
```

### local_agent_retry

```json
{
  "task_id": "task-001",
  "feedback": [
    "JWT expiration is not validated",
    "missing refresh token test"
  ]
}
```

### local_agent_cancel

终止任务。

---

# 8. 为什么 MCP 不直接暴露 read/write/shell

不推荐：

```text
Cursor
 ├── read_file
 ├── write_file
 ├── shell
 ├── git
 └── test
```

因为这样 Cursor 仍然是实际 Executor。

推荐：

```text
Cursor
    │
    │ local_agent_execute()
    ▼
Local Agent
    │
    ├── read
    ├── search
    ├── edit
    ├── shell
    ├── test
    └── git
```

这样真正的 Coding Loop 在本地 Agent 内部。

---

# 9. Local Agent Gateway

这是整个系统的核心。

MCP 只是入口。

```text
MCP Server
    │
    ▼
Task Manager
    │
    ▼
Agent Runtime
```

内部模块：

```text
LocalAgentGateway
│
├── MCP Server
│
├── Task Manager
│
├── Agent Runtime
│
├── Context Manager
│
├── Model Router
│
├── Tool Executor
│
├── Test Runner
│
├── Git Manager
│
├── Retry Manager
│
└── Security Policy
```

---

# 10. Local Agent Runtime

Local Agent 不应该是简单的：

```text
Prompt
  ↓
Code
```

而应该是：

```text
Observe
   ↓
Think
   ↓
Act
   ↓
Observe
   ↓
Test
   ↓
Fix
   ↓
Test
   ↓
Done
```

核心循环：

```python
while not task.finished:

    context = context_manager.build(task)

    response = model.generate(
        task=task,
        context=context,
        tools=tools
    )

    actions = parse_actions(response)

    for action in actions:
        result = execute(action)

    test_result = run_tests(task.test_command)

    if test_result.success:
        task.finished = True
    else:
        task.failures.append(test_result)

        if task.iterations >= MAX_ITERATIONS:
            escalate()

        continue
```

---

# 11. Qwen3-Coder：Primary Executor

第一阶段推荐：

```text
Qwen3-Coder-30B-A3B-Instruct
```

使用：

```text
Q4 GGUF
```

而不是 BF16 / FP16。

目标硬件：

```text
RTX 4080
16GB VRAM
64GB RAM
```

Qwen3-Coder-30B-A3B 的优势：

- MoE 架构
- 30B 级总参数
- 约 3.3B active parameters
- Agentic Coding 能力
- Repository-scale coding
- Function calling
- 长上下文能力
- 适合本地 Coding Agent

第一版重点不是追求最大 Context，而是稳定的 Agent Loop。

---

# 12. 本地推理服务

第一版建议使用：

```text
llama.cpp
```

架构：

```text
Local Agent
      │
      │ OpenAI-compatible HTTP
      ▼
127.0.0.1:8000
      │
      ▼
llama-server
      │
      ▼
Qwen3-Coder Q4
      │
      ▼
RTX 4080
```

示例：

```bash
llama-server \
  -m /models/Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf \
  --host 127.0.0.1 \
  --port 8000 \
  -c 32768
```

建议第一阶段逐步测试：

```text
16K
32K
64K
```

不要一开始就使用 256K Context。

---

# 13. Context Manager

这是 Coding Agent 能否真正工作的关键模块。

不要：

```text
整个 Repository
       ↓
Qwen
```

应该：

```text
Task
 │
 ▼
Repository Map
 │
 ▼
Relevant Files
 │
 ▼
Relevant Symbols
 │
 ▼
Relevant Tests
 │
 ▼
Git Diff
 │
 ▼
Qwen
```

例如：

```text
任务：
修复用户登录 Bug

Context：

src/auth/login.py
src/auth/token.py
src/models/user.py
tests/auth/test_login.py
```

而不是整个项目。

---

# 14. Repository Context 策略

建议分四级。

## Level 1：Repository Map

```text
README
package.json
pyproject.toml
目录结构
模块关系
```

## Level 2：Relevant Files

根据任务检索：

```text
src/auth/**
src/user/**
```

## Level 3：Symbols

只读取相关：

```text
class User
function login()
function validate_token()
```

## Level 4：Tests / Diff

加入：

```text
相关测试
当前 Git Diff
失败日志
```

最终 Context：

```text
Task
+
Repo Map
+
Relevant Code
+
Tests
+
Errors
+
Diff
```

---

# 15. Local Agent Tools

本地 Agent 至少需要：

```text
filesystem
├── list_files
├── read_file
├── search
├── write_file
└── patch_file

shell
└── execute

git
├── status
├── diff
└── log

test
└── run_tests
```

这些工具属于：

```text
Local Agent Runtime
```

而不是 Cursor。

---

# 16. Task Manager

任务统一使用 Task Schema。

推荐：

```json
{
  "task_id": "task-20260911-001",

  "workspace": "/workspace/demo",

  "objective": "Implement JWT authentication",

  "specification": {
    "requirements": [
      "support login",
      "support access token",
      "support refresh token"
    ]
  },

  "files": {
    "allow": [
      "src/auth/**",
      "tests/auth/**"
    ]
  },

  "acceptance": [
    "login returns access token",
    "refresh token works",
    "expired token is rejected",
    "all auth tests pass"
  ],

  "test": {
    "command": "pytest tests/auth"
  },

  "execution": {
    "model": "qwen-coder",
    "max_iterations": 8
  }
}
```

这个协议应该成为系统核心 API。

---

# 17. Planner

Planner 由 Cursor Online Model 完成。

Planner 的输出不是代码，而是：

```text
Task Specification
```

例如：

```text
Objective:
实现 OAuth2 登录

Requirements:
1. OAuth Provider
2. Callback API
3. Token Service
4. Session Management

Acceptance:
1. 登录成功
2. callback 正常
3. token 正常刷新
4. 所有测试通过
```

---

# 18. Task DAG

借鉴 director。

大型任务：

```text
OAuth2
 │
 ▼
Planner
 │
 ▼
DAG
```

例如：

```text
T1 Auth Model
T2 OAuth Provider
T3 Callback API
T4 Token Service
T5 Tests
```

依赖：

```text
T1 ─────┐
        ├── T3 ── T5
T2 ─────┤
        │
T4 ─────┘
```

第一版本建议：

```text
parallel = 1
```

原因：

```text
RTX 4080 16GB
```

多个大模型上下文并行容易造成：

- VRAM 压力
- KV Cache 增长
- 推理速度下降
- Context 竞争

稳定以后再增加并行。

---

# 19. Executor

每一个 Atomic Task 交给 Local Agent。

```text
Task
 │
 ▼
Context
 │
 ▼
Qwen
 │
 ├── Search
 ├── Read
 ├── Edit
 ├── Shell
 └── Test
 │
 ▼
Result
```

本地 Agent 自己完成 Coding Loop。

---

# 20. Deterministic Gate

不要相信：

```text
Qwen：
“应该已经完成。”
```

必须执行确定性检查：

```text
git diff --check
npm test
pytest
go test ./...
cargo test
```

判断：

```text
Exit Code
```

而不是让 LLM 判断测试是否通过。

---

# 21. Reviewer

Reviewer 使用 Cursor Online Model。

输入：

```text
Task Specification
+
Git Diff
+
Changed Files
+
Test Result
+
Error Logs
```

Review：

```text
1. 是否满足需求？
2. 是否有隐藏 Bug？
3. 架构是否合理？
4. 测试是否充分？
5. 是否修改了无关文件？
6. 是否存在安全问题？
```

结果：

```json
{
  "status": "pass"
}
```

或者：

```json
{
  "status": "fail",
  "issues": [
    "Refresh token rotation is missing",
    "Authentication middleware bypass exists"
  ]
}
```

---

# 22. Retry

如果 Reviewer 失败：

```text
Reviewer
   │
   ▼
local_agent_retry
   │
   ▼
Qwen
   │
   ▼
Test
   │
   ▼
Reviewer
```

设置：

```text
max_iterations = 8
```

超过次数：

```text
Escalation
```

交给更强模型。

---

# 23. Model Router

V1：

```text
全部任务
   ↓
Qwen3-Coder
```

V2：

```text
Model Router
      │
 ┌────┼──────────────┐
 ▼    ▼              ▼
Qwen  DeepSeek      Devstral
```

可以根据：

```text
task_type
complexity
context_size
language
failure_count
```

选择模型。

例如：

```text
简单 CRUD
    ↓
Qwen 9B

普通 Coding
    ↓
Qwen3-Coder 30B

复杂重构
    ↓
Qwen3-Coder

连续失败
    ↓
DeepSeek

特殊 Agent Coding
    ↓
Devstral
```

---

# 24. Hooks

Hooks 不负责核心 Agent Loop。

主要负责：

```text
自动化
检查
控制
验证
```

例如：

```text
Local Agent 完成
       │
       ▼
Hook
       │
       ├── git diff --check
       ├── lint
       ├── unit test
       └── security check
```

最终：

```text
PASS
 ↓
Reviewer

FAIL
 ↓
Retry
```

注意：

> 关键 Gate 应同时存在于 Local Agent Gateway 内部，不能完全依赖 Cursor Hooks。

这样即使脱离 Cursor：

```bash
local-agent run task.json
```

仍然可以独立执行。

---

# 25. 安全模型

Local Agent 拥有：

```text
Filesystem
Shell
Git
```

因此必须增加安全边界。

## Workspace Allowlist

允许：

```text
/workspace/project/**
```

禁止：

```text
/etc
~/.ssh
~/.aws
```

## Shell Policy

Allow：

```text
npm
pnpm
yarn
pytest
cargo
go
git
```

Review / Block：

```text
sudo
rm
chmod
ssh
docker
curl
```

尤其防止：

```bash
rm -rf /
```

等危险操作。

---

# 26. Git / Worktree

V1：

```text
当前 Workspace
       ↓
Local Agent
       ↓
Git Diff
```

V2：

```text
Repository
   │
   ├── Worktree A
   │
   ├── Worktree B
   │
   └── Worktree C
```

每个 Atomic Task 使用独立 Worktree。

这样：

```text
Task 1
Task 2
Task 3
```

可以隔离修改。

最终：

```text
Tests
 ↓
Review
 ↓
Merge
```

---

# 27. 项目目录结构

建议：

```text
local-coding-agent/
│
├── README.md
├── pyproject.toml
├── .env.example
│
├── cursor/
│   ├── skills/
│   │   └── local-dev/
│   │       └── SKILL.md
│   │
│   ├── agents/
│   │   └── local-coder.md
│   │
│   ├── hooks/
│   │   └── hooks.json
│   │
│   └── mcp.json
│
├── local_agent/
│   ├── main.py
│   │
│   ├── mcp/
│   │   ├── server.py
│   │   └── tools.py
│   │
│   ├── agent/
│   │   ├── runtime.py
│   │   ├── planner.py
│   │   ├── executor.py
│   │   ├── reviewer.py
│   │   └── retry.py
│   │
│   ├── context/
│   │   ├── manager.py
│   │   ├── repo_map.py
│   │   └── search.py
│   │
│   ├── models/
│   │   ├── router.py
│   │   ├── openai_compatible.py
│   │   └── qwen.py
│   │
│   ├── tools/
│   │   ├── filesystem.py
│   │   ├── shell.py
│   │   ├── git.py
│   │   └── tests.py
│   │
│   ├── security/
│   │   ├── sandbox.py
│   │   └── policy.py
│   │
│   └── tasks/
│       ├── schema.py
│       ├── manager.py
│       └── state.py
│
├── configs/
│   ├── models.yaml
│   ├── policy.yaml
│   └── agent.yaml
│
├── tests/
│
└── scripts/
    ├── install.sh
    ├── start.sh
    └── healthcheck.sh
```

---

# 28. Model 配置

第一阶段：

```yaml
models:

  qwen-coder:
    provider: openai-compatible
    endpoint: http://127.0.0.1:8000/v1
    model: qwen3-coder
    role:
      - executor

  deepseek:
    provider: openai-compatible
    endpoint: http://127.0.0.1:8001/v1
    model: deepseek
    role:
      - executor
      - escalation

  devstral:
    provider: openai-compatible
    endpoint: http://127.0.0.1:8002/v1
    model: devstral
    role:
      - executor
```

实际 V1 只启动：

```text
qwen-coder
```

---

# 29. V0：最小验证

目标：

```text
Cursor
 ↓
MCP
 ↓
Python
 ↓
Qwen
 ↓
修改代码
```

只需要一个 MCP Tool：

```text
local_agent_execute
```

验证：

> Cursor Online Model 能否稳定地把一个 Coding Task 委派给本地 Qwen。

---

# 30. V1：可用版本

加入：

```text
Skill
Subagent
MCP
Task Manager
Qwen
Filesystem
Shell
Git
Test
Retry
```

使用体验：

```text
用户：
“实现 XXX”
```

自动：

```text
Cursor
 ↓
Plan
 ↓
local-coder
 ↓
Qwen
 ↓
修改
 ↓
测试
 ↓
失败？
 ↓
Qwen 修复
 ↓
完成
```

---

# 31. V2：Director-style Orchestration

加入：

```text
Planner
 ↓
Specification
 ↓
Task DAG
 ↓
Atomic Tasks
 ↓
Executor
 ↓
Deterministic Gate
 ↓
Reviewer
 ↓
Retry
```

支持大型任务：

```text
20～100 个文件
```

自动拆分。

---

# 32. V3：多模型 Router

加入：

```text
Qwen 9B
Qwen3-Coder 30B
DeepSeek
Devstral
```

根据任务自动选择。

同时可以研究：

```text
Speculative Decoding
```

让小模型作为 Draft Model，大模型作为 Target Model。

---

# 33. V4：完整 Local Agent Platform

最终可以加入：

```text
Parallel Executor
Worktree
Long-term Memory
Repository Index
Code Graph
Task DAG
Model Router
Cost Router
Telemetry
Web Dashboard
```

最终形态：

```text
                         Cursor
                            │
                     Online Brain
                            │
                     ┌──────▼──────┐
                     │ Orchestrator│
                     └──────┬──────┘
                            │
                     ┌──────▼──────┐
                     │   Task DAG  │
                     └──────┬──────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
            Task 1        Task 2        Task 3
              │             │             │
              ▼             ▼             ▼
            Qwen          Qwen        DeepSeek
              │             │             │
              ▼             ▼             ▼
            Test          Test          Test
              │             │             │
              └─────────────┼─────────────┘
                            ▼
                    Deterministic Gate
                            │
                            ▼
                         Reviewer
                            │
                       ┌────┴────┐
                       ▼         ▼
                      Fix       Pass
                       │         │
                       └────┬────┘
                            ▼
                           Git
```

---

# 34. V1 实际开发顺序

建议严格按照这个顺序开发：

```text
① Qwen3-Coder 本地推理服务
        ↓
② Local Agent Runtime
        ↓
③ Filesystem / Shell / Git / Test Tools
        ↓
④ MCP Server
        ↓
⑤ Cursor local-coder Subagent
        ↓
⑥ Cursor local-dev Skill
        ↓
⑦ Hooks / Deterministic Gate
        ↓
⑧ Planner / Reviewer
        ↓
⑨ Task DAG
        ↓
⑩ Model Router
```

---

# 35. 最终职责划分

| 模块 | 职责 |
|---|---|
| Cursor | IDE / 用户入口 |
| Online Model | Planner / Reviewer |
| Skill | 工作流规范 |
| Subagent | 任务委派 |
| MCP | Cursor ↔ Local Agent Bridge |
| Local Agent Gateway | 本地 Agent Runtime |
| Context Manager | 上下文构建 |
| Qwen3-Coder | Primary Executor |
| Model Router | 多模型选择 |
| Tools | 文件 / Shell / Git / Test |
| Deterministic Gate | 自动验证 |
| Hooks | Cursor 生命周期控制 |
| Task Manager | 任务状态 |
| DAG | 大任务拆解 |
| Reviewer | 最终质量判断 |

---

# 36. 核心设计原则

## 原则 1：Cursor 不等于 Executor

Cursor 主要负责：

```text
理解
规划
委派
Review
```

---

## 原则 2：Qwen 不等于整个 Agent

Qwen 只是：

```text
Model
```

真正的 Executor 是：

```text
Local Agent Gateway
```

---

## 原则 3：MCP 是桥，不是 Agent

```text
MCP
 ↓
Local Agent
```

而不是：

```text
MCP
 ↓
几个简单工具
```

---

## 原则 4：测试结果必须确定性

不能：

```text
LLM：
“应该没问题。”
```

必须：

```text
pytest
 ↓
exit code = 0
```

---

## 原则 5：Context 必须按任务构建

不要：

```text
整个 Repository → Qwen
```

应该：

```text
Task
 ↓
Relevant Context
 ↓
Qwen
```

---

## 原则 6：第一版本只使用一个本地模型

先：

```text
Qwen3-Coder 30B-A3B Q4
```

稳定后再：

```text
Model Router
```

---

# 37. 最终方案总结

整个系统可以浓缩成：

```text
                  Cursor
                     │
              Online Model
                     │
             Planner / Reviewer
                     │
                   Skill
                     │
                 Subagent
                     │
                local-coder
                     │
                    MCP
                     │
          Local Agent Gateway
                     │
              ┌──────▼──────┐
              │ Model Router│
              └──────┬──────┘
                     │
              Qwen3-Coder
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
      Files        Shell         Git
        │            │            │
        └────────────┼────────────┘
                     ▼
                    Test
                     │
                     ▼
             Deterministic Gate
                     │
                     ▼
                  Reviewer
                     │
               ┌─────┴─────┐
               ▼           ▼
              Fix         Pass
               │           │
               └─────┬─────┘
                     ▼
                    Git
```

最终形成：

> **Cursor Online Model = Brain**
>
> **Skill = Workflow**
>
> **Subagent = Delegation**
>
> **MCP = Bridge**
>
> **Local Agent Gateway = Executor**
>
> **Qwen3-Coder = Local Coding Model**
>
> **Hooks = Control**
>
> **Director-style DAG = Orchestration**
>
> **Tests + Reviewer = Quality Gate**

---

# 38. 第一阶段验收标准

完成 V1 后，应当能够在 Cursor 中直接输入：

```text
实现一个 JWT 登录功能。
要求：
1. 支持 access token
2. 支持 refresh token
3. 增加单元测试
4. 不修改无关模块
```

系统自动完成：

```text
Cursor Online
      │
      ▼
分析需求
      │
      ▼
生成 Task
      │
      ▼
local-coder
      │
      ▼
MCP
      │
      ▼
Qwen3-Coder
      │
      ▼
搜索代码
      │
      ▼
修改代码
      │
      ▼
运行测试
      │
      ├── FAIL ──► Qwen 修复
      │
      └── PASS
             │
             ▼
        Git Diff
             │
             ▼
     Cursor Online Review
             │
             ├── FAIL ──► Qwen 修复
             │
             └── PASS
                    │
                    ▼
                  完成
```

这就是第一阶段最重要的 Demo。

---

## 39. 后续实现建议

建议不要一开始开发 Web UI、数据库、复杂 DAG、多个模型。

第一阶段只完成：

```text
Cursor
 +
Skill
 +
Subagent
 +
MCP
 +
Local Agent
 +
Qwen3-Coder
 +
Git
 +
Test
```

当这条链路稳定后，再加入：

```text
Planner
+
Reviewer
+
DAG
+
Retry
+
Model Router
+
Worktree
```

这样可以快速验证整个方案，而不会在一开始陷入 Agent Framework 的复杂性。
