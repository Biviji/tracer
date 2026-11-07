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
| `MAX_RUNS_PER_DAY` | hard daily ceiling, e.g. `100`; hourly and daily caps are counted in the database, so restarts don't reset them |
| `RETENTION_DAYS` | finished experiments are deleted after this many days (default `30`, 0 = keep). The privacy page says 30 |
| `MODEL_PRICES` | optional, USD per 1M tokens for "cost per correct fix", e.g. `glm-5.3=0.5/1.5,qwen3.8-27b=0.2/0.6` (use your real Vultr prices) |

## 5. Start

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose logs -f orchestrator     # should say: sandbox=docker+gvisor inference=... api.vultrinference.com
```

Open `https://<SITE_ADDRESS>`, use repo `demo` for the built-in demo project.

## Automatic deploys (GitHub Actions)

`.github/workflows/ci.yml` runs lint and tests on every push and pull request. When `main` is
green it ships the commit to this server, rebuilds, and checks `/api/health`. One-time setup:

1. On your machine: `ssh-keygen -t ed25519 -f trace-deploy -N "" -C trace-deploy`, then append
   `trace-deploy.pub` to `/root/.ssh/authorized_keys` on the server.
2. GitHub → repo → Settings → Secrets and variables → Actions:
   - secret `DEPLOY_SSH_KEY` = contents of `trace-deploy` (the private key)
   - secret `DEPLOY_KNOWN_HOSTS` = output of `ssh-keyscan -t ed25519 <server ip>`
   - variable `DEPLOY_HOST` = the server IP, variable `SITE_URL` = `https://<ip-with-dashes>.sslip.io`
3. Optional: Settings → Environments → `production` → required reviewers, so each deploy waits
   for a click.

Each deploy unpacks into a fresh folder and keeps the previous one in `/opt/tracer.prev`.
Rollback: `cd /opt && rm -rf tracer && mv tracer.prev tracer && cd tracer && docker compose -p tracer -f docker-compose.yml -f docker-compose.prod.yml up -d --build`.

## Update / stop / remove (by hand)

```bash
git pull && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build   # update
docker compose -f docker-compose.yml -f docker-compose.prod.yml down                        # stop (data kept)
```

A stopped VM is still billed; delete the instance in the Vultr console to stop charges.
