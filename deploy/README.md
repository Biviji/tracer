# Deploying TRACE on a server (Vultr VM or any Ubuntu box)

Everything runs with Docker Compose. Caddy is the only public service: it gets an HTTPS
certificate automatically. The site is open to anyone; `MAX_RUNS_PER_HOUR` and
`MAX_RUNS_PER_CLIENT_PER_HOUR` cap how many runs (and so how much model spend) the public
can trigger.

```
Internet ──HTTPS──▶ caddy (80/443) ──▶ frontend ──/api──▶ orchestrator ──▶ sandboxes (gVisor)
                                                                        └──▶ Vultr Serverless Inference
```

## 1. Server

Ubuntu 24.04 LTS, 4 vCPU / 8 GB recommended (each sandbox may use up to 1 CPU / 1 GB).
Vultr: Compute → Instances → Create Instance → Shared CPU `vc2-4c-8gb`, Ubuntu 24.04 LTS,
your SSH key, backups off.

## 2. Docker, gVisor, firewall (as root on the server)

```bash
curl -fsSL https://get.docker.com | sh          # official Docker install script
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw --force enable

# gVisor: sandboxes run on a user-space kernel, a second wall between agent code and the host
curl -fsSL https://gvisor.dev/archive.key | gpg --dearmor -o /usr/share/keyrings/gvisor-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/gvisor-archive-keyring.gpg] https://storage.googleapis.com/gvisor/releases release main" \
  > /etc/apt/sources.list.d/gvisor.list
apt-get update && apt-get install -y runsc
runsc install

# Dependency-install containers use the default bridge: no container-to-container traffic there
python3 -c "import json,pathlib; p=pathlib.Path('/etc/docker/daemon.json'); c=json.loads(p.read_text()) if p.exists() else {}; c['icc']=False; p.write_text(json.dumps(c, indent=2))"
systemctl restart docker
```

## 3. Code

```bash
git clone <your repo url> /opt/tracer && cd /opt/tracer
```

Keep the dependency-install containers off private networks and cloud metadata:

```bash
cp deploy/trace-sandbox-egress.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now trace-sandbox-egress
```

## 4. `.env` (on the server, never committed)

```bash
cp .env.example .env && nano .env
```

Set at least:

| Variable | Value |
|---|---|
| `LLM_PROVIDER` | `openai_compatible` |
| `LLM_BASE_URL` | `https://api.vultrinference.com/v1` |
| `LLM_API_KEY` | your Vultr Serverless Inference key |
| `LLM_MODELS` | `qwen3.8-27b,glm-5.3,deepseek-v4.1-flash-1017,minimax-m3.1-flash` |
| `SANDBOX_DRIVER` | `docker` |
| `SANDBOX_RUNTIME` | `runsc` (gVisor, from step 2) |
| `DOCKER_GID` | output of `stat -c %g /var/run/docker.sock` |
| `SITE_ADDRESS` | your domain, or `<ip-with-dashes>.sslip.io` (e.g. `144-202-16-76.sslip.io`) |
| `MAX_RUNS_PER_HOUR` | spend guard for the public site, e.g. `30` (0 = unlimited) |
| `MAX_RUNS_PER_CLIENT_PER_HOUR` | per visitor, e.g. `12` |

## 5. Start

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose logs -f orchestrator     # should say: sandbox=docker+gvisor inference=... api.vultrinference.com
```

Open `https://<SITE_ADDRESS>`, use repo `demo` for the built-in demo project.

## Update / stop / remove

```bash
git pull && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build   # update
docker compose -f docker-compose.yml -f docker-compose.prod.yml down                        # stop (data kept)
```

A stopped VM is still billed; delete the instance in the Vultr console to stop charges.
