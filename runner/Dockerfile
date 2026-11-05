# TRACE sandbox image: the disposable box each agent run works in.
#
# The orchestrator starts one container per run with NO network, no secrets,
# memory / CPU / process caps, copies the repo into /workspace, runs the
# agent's tool calls here one by one (docker exec), then destroys it.
#
#   docker build -t trace-sandbox:latest runner/
FROM python:3.13-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends git ripgrep coreutils findutils procps \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir pytest

# Unprivileged user; the orchestrator also drops all capabilities.
RUN useradd --create-home --uid 1000 agent \
 && mkdir /workspace && chown agent:agent /workspace \
 && git config --system user.email agent@trace.local \
 && git config --system user.name "TRACE agent" \
 && git config --system --add safe.directory /workspace

USER agent
WORKDIR /workspace

# Stay alive so the orchestrator can exec commands; it removes the container when done.
CMD ["sleep", "infinity"]
