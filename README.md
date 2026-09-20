# AgentForge

## 这个项目解决什么问题

在线top模型越来越贵。若规划、改文件、跑测试、看日志全走云端 IDE，token 会很快堆上去。

AgentForge 把 **简单、重复、量大的实现工作交给本地模型或者更加便宜的在线模型**，在线top模型只做理解需求、拆任务和 Review，从而减少云端 token。

做法不是「把主模型换成本地模型」（那样规划质量会掉，本地模型也没有完整执行闸门），而是：

> 在线强模型（Cursor / Claude Code / Codex）= 大脑（少 token、关键决策）  
> Gateway + 执行模型 = 干活（大量 Coding / 测试循环；执行模型可以是本机 llama.cpp，也可以是便宜/免费的在线 API）

你在任一终端里下任务；搜代码、改文件、跑测试发生在本机 Gateway。三个终端共用 **同一个** Docker 镜像。完整设计见 [cursor-local-coding-agent-design.md](cursor-local-coding-agent-design.md)。

## 架构

三部分：

```text
你（在 Cursor / Claude Code / Codex 里说话）
        │
        ▼
[1] 在线大脑                         安装配置即可
    Planner / Reviewer
    Skill local-dev / Subagent local-coder
    MCP 客户端
        │  MCP（stdio）→ 同一条 mcp-docker.sh
        ▼
[2] Local Agent Gateway             必须能跑（一个 Docker 镜像）
    读改文件 / 受限 Shell / Git / 测试
    只信测试 exit code 和 git diff --check
        │  HTTP（可带 API Key）
        ▼
[3] 执行模型                         用户配置，本仓库不部署
    llama.cpp 或 xAI / 智谱 GLM 等
```

## Architecture Overview (v2.1)

```text
                        ┌─────────────────────────────────┐
                        │         External Agents         │
                        │                                 │
                        │  Cursor · Codex · Claude Code   │
                        └────────────────┬────────────────┘
                                         │
              ┌──────────────────────────┼──────────────────────────┐
              │                          │                          │
              ▼                          ▼                          ▼
     ┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
     │ Native Observer │       │ Local Observer  │       │ Runtime Observer│
     │                 │       │                 │       │                 │
     │ OTel / API      │       │ Session / Logs  │       │ Process / FS    │
     └────────┬────────┘       └────────┬────────┘       └────────┬────────┘
              │                         │                         │
              └─────────────────────────┼─────────────────────────┘
                                        │
                                        ▼
                               ┌─────────────────┐
                               │ Network Observer│
                               │                 │
                               │ API / Proxy     │
                               │ Provider Usage  │
                               └────────┬────────┘
                                        │
                                        ▼
                               ┌─────────────────┐
                               │  Event Gateway  │
                               │                 │
                               │ • Normalize     │
                               │ • Deduplicate   │
                               │ • Correlate     │
                               │ • Confidence    │
                               └────────┬────────┘
                                        │
                                        ▼
                               ┌─────────────────┐
                               │   Event Store   │
                               └────────┬────────┘
                                        │
              ┌─────────────────────────┼─────────────────────────┐
              │                         │                         │
              ▼                         ▼                         ▼
     ┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
     │ Context Engine  │       │  Usage Engine   │       │   Task Engine   │
     └────────┬────────┘       └────────┬────────┘       └────────┬────────┘
              │                         │                         │
              └─────────────────────────┼─────────────────────────┘
                                        │
                                        ▼
                               ┌─────────────────┐
                               │Budget Controller│
                               │                 │
                               │ • Forecast      │
                               │ • Policy        │
                               │ • Threshold     │
                               └────────┬────────┘
                                        │
              ┌─────────────────────────┼─────────────────────────┐
              │                         │                         │
              ▼                         ▼                         ▼
     ┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
     │ Snapshot Engine │       │Compressor Engine│       │ Handoff Engine  │
     └────────┬────────┘       └────────┬────────┘       └────────┬────────┘
              │                         │                         │
              └─────────────────────────┼─────────────────────────┘
                                        │
                                        ▼
                               ┌─────────────────┐
                               │ Context Package │
                               │                 │
                               │ • Snapshot      │
                               │ • Diff          │
                               │ • Graph         │
                               │ • Provenance    │
                               └────────┬────────┘
                                        │
                                        ▼
                               ┌─────────────────┐
                               │  Target Agent   │
                               └────────┬────────┘
                                        │
                                        └──────────────→ Event Store (Feedback Loop)

```

| 部分 | 做什么 | 你怎么对待它 |
|---|---|---|
| [1] Cursor / Claude Code / Codex | 入口、规划、委派、Review | `install.sh` 写入各工具的项目文件，在该工具里打开 MCP |
| [2] Gateway | 真正的 Executor | `docker build` 一次；各终端 MCP **按需**起容器，不必常驻 |
| [3] 执行模型 | 生成补丁/工具调用 | llama.cpp，或 xAI / 智谱 GLM 等在线 API |

MCP 不把 `read`/`write`/`shell` 暴露给在线模型。改代码的循环只在 Gateway 里。

---

## 如何安装

需要：Docker（daemon 已开）、至少一个在线客户端（Cursor **或** Claude Code **或** Codex），以及 [3] 的执行模型（llama.cpp **或** 在线 API Key）。

### 1. 一键安装客户端配置 + Gateway 镜像

```bash
git clone git@github.com:smart110118/AgentForge.git
cd AgentForge
./scripts/install.sh
```

会 build `agentforge:latest`，并默认写入 Cursor、Claude Code、Codex 的项目文件（同一 `mcp-docker.sh`）。

装到**业务仓库**：

```bash
./scripts/install.sh /abs/path/to/your-project
```

只要部分客户端：

```bash
INSTALL_CLIENTS=cursor,claude ./scripts/install.sh /abs/path/to/your-project
```

`INSTALL_SKIP_DOCKER=1` 只写文件、不 build 镜像（测试用）。

### 2. 配置执行模型（不部署）

Key 只放 `.env`，不要提交：

```bash
cp .env.example .env
# 选 LLM_PROVIDER，填对应 Key
./scripts/healthcheck.sh
```

`LLM_PROVIDER`：

| 值 | 变量 | `LOCAL_AGENT_API` | 说明 |
|---|---|---|---|
| `openai` | `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL` | 默认 `chat` | OpenAI 官方或兼容网关。免费：智谱 `glm-4-flash-250414`，`OPENAI_BASE_URL=https://open.bigmodel.cn/api/coding/paas/v4` |
| `xai` | `XAI_API_KEY` / `XAI_BASE_URL` / `XAI_MODEL` | 默认 `chat` | xAI Grok，例如 `grok-4.20-0309-reasoning` |
| `local` | `LOCAL_AGENT_ENDPOINT` / `LOCAL_AGENT_MODEL` | 默认 `responses` | 局域网 llama.cpp，一般无 Key |

- **`chat`**：`POST {base}/chat/completions`（智谱、xAI、多数云）
- **`responses`**：`POST {base}/responses`（当前 llama.cpp；不要用 chat，容易 `content` 为空）

有 Key 时请求带 `Authorization: Bearer …`。温度：`LLM_TEMPERATURE`。改 `.env` 后在对应客户端 Refresh `local-agent`（MCP 用 `--env-file .env`）。

### 3. 在客户端里启用（每个工具做一次）

脚本不能代替各工具自己的 MCP 授权。打开你执行 `install.sh` 时的那个目录。

**打开（启用本地执行链路）：**

1. **MCP（总开关）**  
   工具应有：`local_agent_execute`、`local_agent_status`、`local_agent_result`、`local_agent_retry`、`local_agent_cancel`。

   | 客户端 | 怎么开 |
   |---|---|
   | **Cursor** | Settings → MCP → 打开 **`local-agent`**（绿灯）。红灯：镜像没 build、Docker 没开、环境里没有 `docker`/`bash`。 |
   | **Claude Code** | 在该目录运行 `claude`，**批准项目 `.mcp.json`**。 |
   | **Codex** | 将该项目标为 **trusted**（否则忽略 `.codex/config.toml`）。`/mcp` 列表可能只显示全局服务器，但 agent 仍能调用项目 MCP。 |

2. **Skill**  
   项目 Skill **`local-dev`**（Cursor: `.cursor/skills`；Claude: `.claude/skills`；Codex: `.agents/skills`）。对话里写：`按 local-dev skill 做`，或 `/local-dev` / `$local-dev`。

3. **Subagent（Cursor / Claude Code）**  
   `local-coder.md` 应在可委派列表里。Planner 把实现交给 MCP，而不是自己改文件。

4. **Hook（仅 Cursor，可选）**  
   只提醒看 `local_agent_result`。Claude / Codex 第一期不装 Stop hook。

**关掉（停止用本地 Gateway）：**

| 你想停什么 | 怎么做 | 效果 |
|---|---|---|
| 暂时不用本地执行 | 关闭该客户端的 MCP `local-agent`（Cursor 开关；Claude 拒绝/禁用 `.mcp.json`；Codex 关掉该 server 或取消 trust） | 不再调 Gateway；没有常驻容器 |
| 这次对话不要委派 | 不要提 local-dev / local-coder | 在线模型会自己改代码 |
| 关掉 Skill | 禁用 **`local-dev`** | 不再自动按「委派本地」工作流 |
| 关掉 Cursor Hook | 去掉项目 `.cursor/hooks.json` | 不再插入 Gate 提醒 |
| 取消正在跑的任务 | 对话里 Stop，或让 Agent 调 `local_agent_cancel` | Gateway 循环停掉 |
| 卸掉本项目集成 | 删掉 install 写入的 `.cursor/`、`.mcp.json`、`.claude/`、`.codex/`、`.agents/skills/`，以及 `CLAUDE.md`/`AGENTS.md` 里的 AgentForge 小节 | 项目不再指向 Gateway |
| 清掉镜像 | `docker rmi agentforge:latest` | 卸 Gateway；MCP 会起不来直到再 `install.sh` |

Gateway **没有需要你手动 `docker compose up` 的常驻服务**。MCP 关闭后，新的 `docker run --rm -i` 不会再出现。若怀疑残留：`docker ps` 里看 `agentforge`，有则 `docker stop`。

---

## 如何使用

前提：所用客户端里 MCP `local-agent` 已连接，`./scripts/healthcheck.sh` **通过**。Planner 仍是在线强模型；GLM / xAI / llama 只给 Gateway 当 Executor。

在对话里说明仓库路径和验收，例如：

```text
按 local-dev skill，把实现委派给 local-coder / local_agent_execute。

workspace：/abs/path/to/your-project
任务：实现 JWT 登录（access + refresh + 单测），不要改无关模块。
files.allow：src/auth/** 、 tests/auth/**
test_command：pytest tests/auth
```

有顺序的多步改动：一次 MCP，用 `dag.tasks`，不要拆成多次 execute。

流程：在线模型规划 → MCP `execute` → Gateway 在容器里改代码并跑测试 → 结果回来 Review。  
**完成标准：** `local_agent_result.status == success`，测试 **exit code 0**，diff 可接受。不要信本地模型说「应该过了」。失败就 `local_agent_retry` 并带上 `feedback`。

不用 IDE、只测 Gateway：

```bash
PROJ="/abs/path/to/your-project"
docker compose run --rm -v "${PROJ}:${PROJ}" agent --task "{
  \"workspace\": \"${PROJ}\",
  \"objective\": \"Add hello()\",
  \"execution\": {\"max_iterations\": 3}
}"
```

---

文件只能落在 `task.workspace`（再被 `files.allow` 收窄）。Shell 白名单见 [`configs/policy.yaml`](configs/policy.yaml)。
