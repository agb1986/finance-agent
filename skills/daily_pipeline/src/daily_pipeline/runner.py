"""Checkpointed orchestrator for the daily finance pipeline.

Each run gets a date-keyed directory under tmp/ containing a manifest.json.
Stages record their status and output path there; re-running the same day
resumes from the first incomplete stage, so a crash (or a re-fire from cron)
never repeats completed API spend. Trader runs additionally consult the
existing verdict files in skills/trader/tmp as a cross-day cache.
"""

import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

from common.logger import get_logger

from daily_pipeline import candidates as candidates_mod
from daily_pipeline import context as context_mod
from daily_pipeline import report as report_mod
from daily_pipeline import tickers as tickers_mod
from daily_pipeline.emailer import send_report

REPO_ROOT = Path(__file__).parents[4]
SKILL_ROOT = Path(__file__).parent.parent.parent
TMP_DIR = SKILL_ROOT / "tmp"
TRADER_TMP = REPO_ROOT / "skills" / "trader" / "tmp"

SCRIPTS = {
    "fetch_news": "skills/financial_news/scripts/fetch_news.py",
    "analyze_news": "skills/financial_news/scripts/analyze_news.py",
    "stock_portfolio": "skills/get_stock_portfolio/scripts/fetch_portfolio.py",
    "crypto_portfolio": "skills/get_crypto_portfolio/scripts/fetch_portfolio.py",
    "fetch_quote": "skills/check_stock/scripts/fetch_quote.py",
    "fetch_history": "skills/check_stock/scripts/fetch_history.py",
    "run_panel": "skills/trader/scripts/run_panel.py",
    "run_debate": "skills/trader/scripts/run_debate.py",
    "run_judge": "skills/trader/scripts/run_judge.py",
}

STAGE_TIMEOUT = 900  # seconds per script invocation
LOCK_MAX_AGE = 6 * 3600

_VERDICT_RE = re.compile(r"verdict_(?P<symbol>[A-Z.]+)_(?P<ts>\d{8}_\d{6})\.json")


class StageError(Exception):
    """A pipeline stage failed."""


# ── subprocess + manifest plumbing ────────────────────────────────────────────


def run_script(script: str, args: list[str] | None = None, timeout: int = STAGE_TIMEOUT) -> str:
    """Run a skill script via ``uv run`` and return its output-file path.

    Every skill script prints its output path as the first line of stdout.

    Raises:
        StageError: On non-zero exit, timeout, or empty stdout.
    """
    logger = get_logger()
    command = ["uv", "run", script, *(args or [])]
    logger.debug(f"running: {' '.join(command)}")
    try:
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise StageError(f"{script} timed out after {timeout}s") from exc
    if result.returncode != 0:
        tail = "\n".join(result.stderr.strip().splitlines()[-5:])
        raise StageError(f"{script} exited {result.returncode}: {tail}")
    lines = result.stdout.strip().splitlines()
    if not lines:
        raise StageError(f"{script} produced no output path")
    return lines[0].strip()


def load_manifest(run_dir: Path) -> dict:
    """Load (or initialise) the run manifest."""
    manifest_path = run_dir / "manifest.json"
    if manifest_path.exists():
        with manifest_path.open() as f:
            return json.load(f)
    return {"stages": {}, "trader": {}}


def save_manifest(run_dir: Path, manifest: dict) -> None:
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))


def stage_done(manifest: dict, name: str) -> bool:
    """True when a stage completed and its output artifact still exists."""
    stage = manifest["stages"].get(name)
    if not stage or stage.get("status") != "done":
        return False
    output = stage.get("output")
    return output is None or Path(output).exists()


def record_stage(
    run_dir: Path, manifest: dict, name: str, status: str, output: str | None = None
) -> None:
    manifest["stages"][name] = {
        "status": status,
        "output": output,
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    save_manifest(run_dir, manifest)


# ── locking and retention ─────────────────────────────────────────────────────


def acquire_lock(run_dir: Path) -> Path:
    """Atomically create a lock file; refuse to start when a fresh lock exists.

    Raises:
        StageError: If another run appears to be in progress.
    """
    lock_path = run_dir / ".lock"
    if lock_path.exists():
        age = time.time() - lock_path.stat().st_mtime
        if age < LOCK_MAX_AGE:
            raise StageError(f"lock file {lock_path} is {age:.0f}s old — another run in progress?")
        get_logger().debug(f"removing stale lock ({age:.0f}s old)")
        lock_path.unlink()
    try:
        # open("x") is atomic: two simultaneous cron fires cannot both win.
        with lock_path.open("x") as f:
            f.write(str(os.getpid()))
    except FileExistsError as exc:
        raise StageError(f"lock file {lock_path} appeared concurrently — another run won") from exc
    return lock_path


def prune_old_runs(tmp_dir: Path, retention_days: int, now: datetime | None = None) -> int:
    """Delete run_<date> directories older than retention_days. Returns count removed."""
    logger = get_logger()
    now = now or datetime.now()
    cutoff = now - timedelta(days=retention_days)
    removed = 0
    for run_dir in sorted(tmp_dir.glob("run_*")):
        try:
            run_date = datetime.strptime(run_dir.name, "run_%Y%m%d")
        except ValueError:
            continue
        if run_date < cutoff:
            shutil.rmtree(run_dir)
            logger.debug(f"pruned {run_dir}")
            removed += 1
    return removed


# ── trader with verdict cache ─────────────────────────────────────────────────


def find_cached_verdict(
    symbol: str, max_age_days: int, trader_tmp: Path = TRADER_TMP, now: datetime | None = None
) -> Path | None:
    """Return the newest verdict file for symbol within max_age_days, if any."""
    now = now or datetime.now()
    newest: tuple[datetime, Path] | None = None
    if not trader_tmp.exists():
        return None
    for path in trader_tmp.glob(f"verdict_{symbol}_*.json"):
        match = _VERDICT_RE.fullmatch(path.name)
        if not match or match["symbol"] != symbol:
            continue
        generated = datetime.strptime(match["ts"], "%Y%m%d_%H%M%S")
        if now - generated > timedelta(days=max_age_days):
            continue
        if newest is None or generated > newest[0]:
            newest = (generated, path)
    return newest[1] if newest else None


def build_market_context(symbol: str, run_dir: Path, period: str) -> Path | None:
    """Fetch quote + history via check_stock and write a compact context file.

    Returns None when the fetch fails — the panel still runs, just ungrounded,
    matching the trader's standalone behaviour. Grounding the panel in real
    market data is what keeps the technical analyst's price levels honest.
    """
    logger = get_logger()
    try:
        quote_path = run_script(SCRIPTS["fetch_quote"], ["--symbol", symbol])
        history_path = run_script(
            SCRIPTS["fetch_history"], ["--symbol", symbol, "--period", period]
        )
    except StageError as exc:
        logger.error(f"{symbol}: market data fetch failed ({exc}) — panel runs without context")
        return None
    with Path(quote_path).open() as f:
        quote = json.load(f)
    with Path(history_path).open() as f:
        history = json.load(f)
    context_path = run_dir / f"context_{symbol}.md"
    context_path.write_text(context_mod.build_context(quote, history))
    logger.debug(f"{symbol}: market context written to {context_path}")
    return context_path


def run_trader(symbol: str, rounds: int, context_file: str | None = None) -> str:
    """Run the three trader stages for a symbol and return the verdict path."""
    panel_args = ["--symbol", symbol]
    if context_file:
        panel_args += ["--context-file", context_file]
    panel_path = run_script(SCRIPTS["run_panel"], panel_args)
    debate_path = run_script(
        SCRIPTS["run_debate"], ["--input", panel_path, "--rounds", str(rounds)]
    )
    return run_script(SCRIPTS["run_judge"], ["--input", debate_path])


# ── the pipeline ──────────────────────────────────────────────────────────────


def plan(config: dict) -> list[str]:
    """Human-readable description of what a run would do (used by --dry-run)."""
    return [
        f"fetch_news (--hours {config['news']['hours']})",
        f"analyze_news (--min-semantic {config['news']['min_semantic']})",
        f"extract_tickers (top {config['tickers']['top_n']})",
        "stock_portfolio (skipped unless TRADING_212_API_KEY/SECRET set)",
        "crypto_portfolio (skipped unless CRYPTO_API_KEY/SECRET set)",
        (
            f"select_candidates (|P&L| >= {config['portfolio']['min_abs_pnl_pct']}%, "
            f"max {config['portfolio']['max_candidates']})"
        ),
        (
            f"trader (max {config['trader']['max_runs']} runs, "
            f"verdict cache {config['trader']['verdict_cache_days']}d, "
            f"grounded on {config['trader']['history_period']} market data)"
        ),
        "build_report",
        "send_email (skipped unless SMTP_* configured)",
    ]


def run_pipeline(
    config: dict,
    date: str | None = None,
    max_trader_runs: int | None = None,
    skip_email: bool = False,
    with_summary: bool = True,
) -> dict:
    """Execute the full daily pipeline, resuming any completed stages.

    Args:
        config:          Pipeline config (see config.load_config).
        date:            Run date as YYYYMMDD. Defaults to today.
        max_trader_runs: Override for config trader.max_runs.
        skip_email:      Build the report but do not send it.
        with_summary:    Set False to skip the Claude executive summary.

    Returns:
        The final manifest dict. ``manifest["report"]`` holds the report path.

    Raises:
        StageError: When a required stage fails (news, report, email).
    """
    logger = get_logger()
    date = date or time.strftime("%Y%m%d")
    run_dir = TMP_DIR / f"run_{date}"
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(run_dir)
    manifest.setdefault("date", date)

    lock_path = acquire_lock(run_dir)
    try:
        # 1-2. news fetch + analysis (required)
        if not stage_done(manifest, "fetch_news"):
            output = run_script(SCRIPTS["fetch_news"], ["--hours", str(config["news"]["hours"])])
            record_stage(run_dir, manifest, "fetch_news", "done", output)
        if not stage_done(manifest, "analyze_news"):
            output = run_script(
                SCRIPTS["analyze_news"],
                [
                    "--input",
                    manifest["stages"]["fetch_news"]["output"],
                    "--min-semantic",
                    str(config["news"]["min_semantic"]),
                ],
            )
            record_stage(run_dir, manifest, "analyze_news", "done", output)
        analysis_path = manifest["stages"]["analyze_news"]["output"]

        # 3. ticker extraction (in-process)
        if not stage_done(manifest, "extract_tickers"):
            with Path(analysis_path).open() as f:
                articles = json.load(f)
            ticker_map = tickers_mod.load_ticker_map()
            top = tickers_mod.extract_tickers(articles, ticker_map, config["tickers"]["top_n"])
            tickers_path = run_dir / "tickers.json"
            tickers_path.write_text(json.dumps(top, indent=2))
            record_stage(run_dir, manifest, "extract_tickers", "done", str(tickers_path))
        with Path(manifest["stages"]["extract_tickers"]["output"]).open() as f:
            news_tickers = json.load(f)

        # 4-5. portfolios (optional — skipped without credentials)
        for stage_name, env_key in [
            ("stock_portfolio", "TRADING_212_API_KEY"),
            ("crypto_portfolio", "CRYPTO_API_KEY"),
        ]:
            if stage_done(manifest, stage_name):
                continue
            if not os.environ.get(env_key):
                logger.debug(f"{stage_name}: {env_key} not set — skipping")
                record_stage(run_dir, manifest, stage_name, "skipped")
                continue
            try:
                output = run_script(SCRIPTS[stage_name])
                record_stage(run_dir, manifest, stage_name, "done", output)
            except StageError as exc:
                logger.error(f"{stage_name} failed: {exc}")
                record_stage(run_dir, manifest, stage_name, "failed")

        # 6. portfolio-gated candidates (in-process)
        portfolio_path = manifest["stages"].get("stock_portfolio", {}).get("output")
        portfolio_candidates: list[dict] = []
        if portfolio_path and Path(portfolio_path).exists():
            with Path(portfolio_path).open() as f:
                portfolio = json.load(f)
            portfolio_candidates = candidates_mod.select_candidates(
                portfolio,
                config["portfolio"]["min_abs_pnl_pct"],
                config["portfolio"]["min_position_value"],
                config["portfolio"]["max_candidates"],
            )
        record_stage(
            run_dir,
            manifest,
            "select_candidates",
            "done" if portfolio_path else "skipped",
        )

        # 7. trader runs (news tickers first, then portfolio candidates)
        cap = max_trader_runs if max_trader_runs is not None else config["trader"]["max_runs"]
        symbols: list[str] = []
        for entry in news_tickers:
            if entry["symbol"] not in symbols:
                symbols.append(entry["symbol"])
        for candidate in portfolio_candidates:
            if candidate["symbol"] not in symbols:
                symbols.append(candidate["symbol"])
        symbols = symbols[:cap]
        logger.debug(f"trader symbols (capped at {cap}): {symbols}")

        for symbol in symbols:
            existing = manifest["trader"].get(symbol, {})
            if existing.get("status") == "done" and Path(existing.get("verdict", "")).exists():
                continue
            cached = find_cached_verdict(symbol, config["trader"]["verdict_cache_days"])
            if cached:
                logger.debug(f"{symbol}: reusing cached verdict {cached}")
                manifest["trader"][symbol] = {
                    "status": "done",
                    "verdict": str(cached),
                    "cached": True,
                }
                save_manifest(run_dir, manifest)
                continue
            context_path = build_market_context(symbol, run_dir, config["trader"]["history_period"])
            try:
                verdict_path = run_trader(
                    symbol,
                    config["trader"]["rounds"],
                    context_file=str(context_path) if context_path else None,
                )
                manifest["trader"][symbol] = {
                    "status": "done",
                    "verdict": verdict_path,
                    "cached": False,
                    "context": str(context_path) if context_path else None,
                }
            except StageError as exc:
                logger.error(f"trader failed for {symbol}: {exc}")
                manifest["trader"][symbol] = {"status": "failed", "error": str(exc)}
            save_manifest(run_dir, manifest)

        # 8. report (required)
        verdicts = [
            {"path": entry["verdict"], "cached": entry.get("cached", False)}
            for entry in manifest["trader"].values()
            if entry.get("status") == "done"
        ]
        crypto_path = manifest["stages"].get("crypto_portfolio", {}).get("output")
        if crypto_path and not Path(crypto_path).exists():
            crypto_path = None
        report_body = report_mod.build_report(
            date=f"{date[:4]}-{date[4:6]}-{date[6:]}",
            analysis_path=analysis_path,
            tickers_path=manifest["stages"]["extract_tickers"]["output"],
            portfolio_path=portfolio_path,
            verdicts=verdicts,
            stages=manifest["stages"],
            with_summary=with_summary,
            pricing=config.get("pricing"),
            crypto_path=crypto_path,
        )
        report_path = run_dir / "report.md"
        report_path.write_text(report_body)
        manifest["report"] = str(report_path)
        record_stage(run_dir, manifest, "build_report", "done", str(report_path))

        # 9. email
        if skip_email:
            record_stage(run_dir, manifest, "send_email", "skipped")
        elif stage_done(manifest, "send_email"):
            logger.debug("email already sent for this run")
        else:
            subject = f"{config['email']['subject_prefix']} — {date[:4]}-{date[4:6]}-{date[6:]}"
            try:
                send_report(subject, report_body)
                record_stage(run_dir, manifest, "send_email", "done")
            except Exception as exc:
                record_stage(run_dir, manifest, "send_email", "failed")
                raise StageError(f"email delivery failed: {exc}") from exc

        # 10. retention
        prune_old_runs(TMP_DIR, config["retention_days"])
        return manifest
    finally:
        lock_path.unlink(missing_ok=True)
