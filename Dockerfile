FROM python:3.11-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ripgrep curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY local_agent ./local_agent
COPY configs ./configs
COPY tests ./tests

RUN pip install --no-cache-dir -e ".[dev]"

ENV PYTHONUNBUFFERED=1 \
    LOCAL_AGENT_API=responses

ENTRYPOINT ["python", "-m", "local_agent.main"]
CMD ["--mcp"]
