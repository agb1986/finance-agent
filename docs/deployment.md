# Deploying the daily pipeline on CasaOS

The daily pipeline runs as a **one-shot container**: cron fires it once a day, it
builds the report, emails it, and exits. It is not a long-running service.

The same image also serves the MCP server (`finance-mcp`), which *is* a
long-running service. Both are defined in `docker-compose.yml` and share one
build, because they need the identical workspace.

---

## 1. Prerequisites

- Docker Engine and the Compose v2 plugin on the CasaOS host.
- Your user must be able to reach the Docker socket:

  ```bash
  sudo usermod -aG docker "$USER"   # then log out and back in
  ```

- `buildx` is **not** required. The Dockerfile deliberately avoids BuildKit-only
  syntax so it also builds with the legacy builder that ships with Ubuntu's
  `docker.io` package.

## 2. Configure secrets

```bash
cp .env.example .env
$EDITOR .env
```

`.env` is gitignored and is the only place credentials live — nothing is baked
into the image.

| Variable | Required | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Trader stages + executive summary. There is no keyring in a container, so this must be an env var. |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` | For email | Gmail: `smtp.gmail.com` / `587`. |
| `REPORT_TO` / `REPORT_FROM` | `REPORT_TO` for email | `REPORT_FROM` defaults to `SMTP_USER`. |
| `TRADING_212_API_KEY` / `_SECRET` | No | Stock portfolio stage is skipped if unset. |
| `CRYPTO_API_KEY` / `_SECRET` | No | Crypto portfolio stage is skipped if unset. |
| `TZ` | No | Defaults to `Europe/London`. The pipeline keys run directories off the local date. |

### Gmail app password

`SMTP_PASSWORD` must be a Google **app password**, not your account password:

1. Enable 2-Step Verification on the Google account (required — app passwords
   are unavailable without it).
2. Generate one at <https://myaccount.google.com/apppasswords>.
3. Paste the 16-character value into `SMTP_PASSWORD` (spaces can be omitted).

## 3. Build

```bash
docker compose build
```

First build pulls ~1 GB of dependencies and bakes the `all-MiniLM-L6-v2`
embedding model into the image, so there is no cold-start download on the first
run. Expect several minutes.

> The lockfile pins torch to the CPU-only PyTorch index. Without that pin the
> image pulls ~6.5 GB of CUDA and Triton wheels that nothing here uses.

## 4. Verify before scheduling

Print the plan without executing or spending anything:

```bash
docker compose run --rm finance-pipeline \
  uv run skills/daily_pipeline/scripts/run_daily.py --dry-run
```

Then a real run that builds the report but does not email it:

```bash
docker compose run --rm finance-pipeline \
  uv run skills/daily_pipeline/scripts/run_daily.py --skip-email --debug
```

A full run, exactly as cron will invoke it:

```bash
docker compose run --rm finance-pipeline
```

The `finance-pipeline` service sits behind a Compose profile, so
`docker compose up` starts only the MCP server. `docker compose run` activates
the profile automatically.

## 5. Schedule it

Host cron is the simplest option — CasaOS has no built-in job scheduler, and the
pipeline's date-keyed manifest already makes a duplicate fire safe (it resumes
rather than repeating completed API spend).

```bash
crontab -e
```

```cron
# Daily finance report at 07:30 local time
30 7 * * * cd /path/to/finance-agent && /usr/bin/docker compose run --rm finance-pipeline >> /var/log/finance-pipeline.log 2>&1
```

Notes:

- Use the absolute path to `docker`; cron's `PATH` is minimal.
- `cd` into the repo so Compose finds `docker-compose.yml` and `.env`.
- `--rm` prevents a pile-up of exited containers.
- If a run is already in progress, the pipeline's lock file makes the second
  invocation exit rather than run concurrently.

## 6. Reading artifacts

Run artifacts persist in named volumes, so they survive `docker compose down`
and image rebuilds:

| Volume | Contents |
|---|---|
| `daily-pipeline-tmp` | `run_<date>/` — `manifest.json`, `report.md` |
| `trader-tmp` | `verdict_<SYMBOL>_<ts>.json` — the cross-day verdict cache |
| `financial-news-tmp` | Fetched and analysed article JSON |
| `stock-portfolio-tmp` / `crypto-portfolio-tmp` | Portfolio snapshots |

Read one without installing anything on the host:

```bash
# List runs
docker compose run --rm finance-pipeline ls skills/daily_pipeline/tmp

# Print today's report
docker compose run --rm finance-pipeline \
  sh -c 'cat skills/daily_pipeline/tmp/run_$(date +%Y%m%d)/report.md'

# Copy it to the host
docker compose run --rm finance-pipeline \
  sh -c 'cat skills/daily_pipeline/tmp/run_$(date +%Y%m%d)/report.md' > report.md
```

Run directories older than `retention_days` in `pipeline.yaml` (default 14) are
pruned automatically at the end of each run.

## 7. Tuning without a rebuild

`pipeline.yaml` and `ticker_map.json` are baked into the image, so changing them
normally means rebuilding. To iterate on thresholds against a running
deployment, bind-mount the config over the image copy:

```bash
docker compose run --rm \
  -v "$(pwd)/skills/daily_pipeline/pipeline.yaml:/app/skills/daily_pipeline/pipeline.yaml:ro" \
  finance-pipeline
```

The cost-relevant knob is `trader.max_runs` (default **2**). Each trader run is
~10 Anthropic calls (5× Sonnet, 5× Opus), roughly $0.30–0.60, so the default
caps a worst-case day at ~$0.60–1.20. The 3-day verdict cache means steady-state
spend is lower.

## Troubleshooting

| Symptom | Cause |
|---|---|
| `permission denied ... /var/run/docker.sock` | User not in the `docker` group — see step 1. |
| `missing SMTP environment variables: ...` | `.env` incomplete; the message names the missing vars. |
| Report date is a day off | `TZ` not set to your timezone in `.env`. |
| `lock file ... another run in progress?` | A previous run is still going, or died hard. Locks older than 6h are cleared automatically. |
| Model download attempted at runtime | `HF_HUB_OFFLINE=1` is set because the model is baked in. If you change the embedding model, rebuild the image. |

## Not yet done

- **Failure alerting** — a failed stage currently just exits non-zero into the
  cron log; there is no push/email notification.
- **CI/CD** — no GitHub Actions job builds and pushes the image to GHCR yet, so
  the CasaOS host builds locally.
