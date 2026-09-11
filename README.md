# AgentForge Local Coding Agent

Cloud Brain (Cursor online model) + Local Executor (Qwen3-Coder on llama.cpp).

Planner / Reviewer stay in Cursor. This repo is the Local Agent Gateway.

## Setup

```bash
python3.11 -m pip install -e ".[dev]"
cp .env.example .env   # set LLAMA_MODEL to your GGUF
chmod +x scripts/*.sh cursor/hooks/gate.py
```

### Local inference (16K first)

```bash
./scripts/start.sh
./scripts/healthcheck.sh
```

`scripts/start.sh` runs:

```bash
llama-server -m "$LLAMA_MODEL" --host 127.0.0.1 --port 8000 -c 16384
```

Raise context only after this is stable: `LLAMA_CTX=32768` then `65536`. Do not start at 256K.

### Cursor

1. Point MCP at [`cursor/mcp.json`](cursor/mcp.json) (or use [`.cursor/mcp.json`](.cursor/mcp.json)).
2. Skill: [`.cursor/skills/local-dev/SKILL.md`](.cursor/skills/local-dev/SKILL.md)
3. Subagent: [`.cursor/agents/local-coder.md`](.cursor/agents/local-coder.md)
4. Hooks: [`.cursor/hooks.json`](.cursor/hooks.json) — reminder only. The real gate is inside the gateway.

## CLI

```bash
python3.11 -m local_agent.main --task '{"task_id":"t1","workspace":"/abs/project","objective":"add hello()","execution":{"max_iterations":3}}'
python3.11 -m local_agent.main --gate --workspace /abs/project --test-command "pytest tests/auth"
python3.11 -m local_agent.main --mcp
```

## V0 demo

With llama-server up: ask Cursor to add a `hello` function and let it call `local_agent_execute`.

## V1 demo

JWT login with access + refresh tokens, unit tests, `files.allow` limited to auth paths. Tests must exit 0; do not trust the model saying they passed.

## Layout

See `local_agent/` for runtime, MCP, tools, security, tasks, context.
