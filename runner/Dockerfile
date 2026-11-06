# TRACE sandbox image: the disposable box each agent run works in.
#
# Per run the orchestrator uses it twice, on one throwaway /workspace volume:
#   setup  — installs the repo's dependencies (pip / npm), with internet, no model involved
#   agent  — NO network, no secrets, memory / CPU / process caps; the agent's tool calls run
#            here one by one (docker exec)
# Both containers and the volume are destroyed when the run ends.
#
#   docker build -t trace-sandbox:latest runner/
FROM python:3.13-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends git ripgrep coreutils findutils procps nodejs npm \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir pytest

# Unprivileged user; the orchestrator also drops all capabilities.
RUN useradd --create-home --uid 1000 agent \
 && mkdir /workspace && chown agent:agent /workspace \
 && git config --system user.email agent@trace.local \
 && git config --system user.name "TRACE agent" \
 && git config --system --add safe.directory /workspace

# Dependencies installed by the setup step are on PATH for every command (bash -l).
RUN printf '%s\n' \
      'if [ -d /workspace/.venv ]; then export VIRTUAL_ENV=/workspace/.venv; PATH="/workspace/.venv/bin:$PATH"; fi' \
      'PATH="/workspace/node_modules/.bin:$PATH"' \
      'export PATH' > /etc/profile.d/trace.sh

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    npm_config_update_notifier=false

USER agent
WORKDIR /workspace

# Stay alive so the orchestrator can exec commands; it removes the container when done.
CMD ["sleep", "infinity"]
