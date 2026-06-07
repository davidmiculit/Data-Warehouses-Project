"""Launch the Spark analytics/ML jobs on demand from the API.

The Spark workloads normally run via ``docker compose exec spark spark-submit`` from a
shell (see README). This module wraps that same invocation so the UI can trigger it,
making every capability usable through the interface. The job runs inside the existing
``acme-spark`` container; we shell out to ``docker exec`` (argv list — never a shell
string, so ids can't inject) and return a structured result with a log tail.
"""
from __future__ import annotations

import re
import subprocess
import time
from typing import Literal

from acme_dwh.config import get_settings

Job = Literal["aggregation", "regression"]

_JOB_SCRIPT = {
    "aggregation": "/opt/jobs/aggregation_job.py",
    "regression": "/opt/jobs/regression_job.py",
}
# ids embedded in `docker exec -e KEY=VALUE` argv; keep them to a safe charset.
_ID_RE = re.compile(r"^[A-Za-z0-9._/\-]{1,128}$")


class SparkJobError(RuntimeError):
    pass


def _tail(text: str, n: int = 24) -> str:
    lines = [ln for ln in (text or "").splitlines() if ln.strip()]
    return "\n".join(lines[-n:])


def _summary(stdout: str) -> str | None:
    """Pull the job's own one-line result (the `[aggregation]`/`[regression]` print)."""
    for ln in reversed((stdout or "").splitlines()):
        s = ln.strip()
        if s.startswith("[aggregation]") or s.startswith("[regression]"):
            return s
    return None


def run_spark_job(
    job: Job,
    asset_id: str | None = None,
    data_source_id: str | None = None,
) -> dict:
    """Run a Spark job to completion inside the spark container. Returns a result dict.

    aggregation: recomputes per-year `totals` for every (asset, source) pair.
    regression : trains/predicts for one asset+source (ASSET_ID / DATA_SOURCE_ID env).
    """
    settings = get_settings()
    script = _JOB_SCRIPT.get(job)
    if script is None:
        raise SparkJobError(f"unknown job '{job}'")

    env_flags: list[str] = ["-e", f"CASSANDRA_KEYSPACE={settings.cassandra_keyspace}"]
    if job == "regression":
        aid = asset_id or "BTCUSD"
        sid = data_source_id or "BITFINEX"
        for value in (aid, sid):
            if not _ID_RE.match(value):
                raise SparkJobError(f"invalid id '{value}'")
        env_flags += ["-e", f"ASSET_ID={aid}", "-e", f"DATA_SOURCE_ID={sid}"]

    cmd = [
        settings.docker_bin, "exec", *env_flags, settings.spark_container,
        settings.spark_submit_path,
        "--master", "local[*]",
        "--packages", settings.spark_connector_package,
        "--conf", "spark.jars.ivy=/tmp/.ivy2",
        "--conf", f"spark.cassandra.connection.host={settings.spark_cassandra_host}",
        "--conf", "spark.log.level=WARN",
        script,
    ]

    started = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=settings.spark_job_timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise SparkJobError(
            f"Spark job timed out after {settings.spark_job_timeout}s"
        ) from exc
    except FileNotFoundError as exc:
        raise SparkJobError(
            f"'{settings.docker_bin}' not found — is Docker on PATH for the API process?"
        ) from exc

    duration = round(time.monotonic() - started, 1)
    ok = proc.returncode == 0 and _summary(proc.stdout) is not None

    return {
        "job": job,
        "ok": ok,
        "returncode": proc.returncode,
        "durationSec": duration,
        "summary": _summary(proc.stdout),
        # spark logs go to stderr; the job's own prints go to stdout
        "log": _tail(proc.stdout + "\n" + proc.stderr, 24),
    }
