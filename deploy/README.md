# Deploying TRACE on a server (Vultr VM or any Ubuntu box)

Everything runs with Docker Compose. Caddy is the only public service: it gets an HTTPS
certificate automatically and asks for a password before anything else loads.

```
Internet ──HTTPS──▶ caddy (80/443, password) ──▶ frontend ──/api──▶ orchestrator ──▶ sandboxes
                                                                        └──▶ Vultr Serverless Inference
```

## 1. Server

Ubuntu 24.04 LTS, 4 vCPU / 8 GB recommended (each sandbox may use up to 1 CPU / 1 GB).
Vultr: Compute → Instances → Create Instance → Shared CPU `vc2-4c-8gb`, Ubuntu 24.04 LTS,
your SSH key, backups off.

## 2. Docker + firewall (as root on the server)

```bash
curl -fsSL https://get.docker.com | sh          # official Docker install script
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw --force enable
```

## 3. Code

```bash
git clone <your repo url> /opt/tracer && cd /opt/tracer
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
| `DOCKER_GID` | output of `stat -c %g /var/run/docker.sock` |
| `SITE_ADDRESS` | your domain, or `<ip-with-dashes>.sslip.io` (e.g. `144-202-16-76.sslip.io`) |
| `BASIC_AUTH_USER` | login name, e.g. `trace` |
| `BASIC_AUTH_HASH` | `'<hash>'` in **single quotes**, from: `docker run --rm caddy:2.8.4 caddy hash-password --plaintext 'your-password'` |

## 5. Start

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose logs -f orchestrator     # should say: sandbox=docker inference=... api.vultrinference.com
```

Open `https://<SITE_ADDRESS>` and log in.

## Update / stop / remove

```bash
git pull && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build   # update
docker compose -f docker-compose.yml -f docker-compose.prod.yml down                        # stop (data kept)
```

A stopped VM is still billed; delete the instance in the Vultr console to stop charges.
