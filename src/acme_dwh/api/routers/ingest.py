"""/ingest endpoint — run the ETL pipeline from the UI."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from acme_dwh.api.schemas import IngestRequest, IngestStatsModel
from acme_dwh.config import get_settings
from acme_dwh.ingestion.load import Ingestor
from acme_dwh.ingestion.providers import build_extractor

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("", response_model=list[IngestStatsModel], summary="Ingest symbols from a provider")
def run_ingest(body: IngestRequest) -> list[IngestStatsModel]:
    settings = get_settings()
    try:
        extractor = build_extractor(body.provider, settings)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        ingestor = Ingestor(extractor)
        results: list[IngestStatsModel] = []
        for symbol in body.symbols:
            s = ingestor.ingest_symbol(symbol, body.start, body.end)
            results.append(
                IngestStatsModel(
                    symbol=s.symbol,
                    assetId=s.asset_id,
                    dataSourceId=s.data_source_id,
                    fetched=s.fetched,
                    transformed=s.transformed,
                    stored=s.stored,
                    skipped=s.skipped,
                    failed=s.failed,
                    attributes=s.attributes,
                )
            )
        return results
    except Exception as exc:  # noqa: BLE001 - provider/network failures surface as 502
        raise HTTPException(status_code=502, detail=f"Ingestion failed: {exc}")
    finally:
        close = getattr(extractor, "close", None)
        if callable(close):
            close()
