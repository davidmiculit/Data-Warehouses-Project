"""/analytics endpoints — read the Spark output tables, and run the Spark jobs."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from acme_dwh.analytics.run_job import SparkJobError, run_spark_job
from acme_dwh.api.deps import get_analytics_repo
from acme_dwh.api.schemas import PredictionRow, RunJobRequest, RunJobResult, TotalRow
from acme_dwh.dal.analytics_repository import AnalyticsRepository

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/totals", response_model=list[TotalRow], summary="Per-year aggregates (Spark job)")
def totals(
    assetId: str = Query(...),
    dataSourceId: str = Query(...),
    repo: AnalyticsRepository = Depends(get_analytics_repo),
) -> list[TotalRow]:
    return repo.totals(assetId, dataSourceId)


@router.get("/predictions", response_model=list[PredictionRow], summary="Regression predictions (Spark ML)")
def predictions(
    assetId: str = Query(...),
    dataSourceId: str = Query(...),
    limit: int = Query(200, ge=1, le=2000),
    repo: AnalyticsRepository = Depends(get_analytics_repo),
) -> list[PredictionRow]:
    return repo.predictions(assetId, dataSourceId, limit)


@router.post("/run", response_model=RunJobResult, summary="Run a Spark job (aggregation/regression) on demand")
def run_job(body: RunJobRequest) -> RunJobResult:
    """Launch a Spark workload inside the spark container and wait for it to finish.

    ``aggregation`` recomputes the per-year ``totals`` for all pairs; ``regression``
    trains/predicts for one asset+source. Results upsert, so re-running is safe.
    """
    if body.job not in ("aggregation", "regression"):
        raise HTTPException(status_code=400, detail="job must be 'aggregation' or 'regression'")
    try:
        result = run_spark_job(body.job, body.assetId, body.dataSourceId)
    except SparkJobError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    if not result["ok"]:
        # surface the spark log tail so the UI can show what went wrong
        raise HTTPException(status_code=502, detail=result.get("log") or "Spark job failed")
    return RunJobResult(**result)
