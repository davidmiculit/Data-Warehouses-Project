"""Provider adapters + a factory selecting one by name."""
from __future__ import annotations

from acme_dwh.config import Settings, get_settings
from acme_dwh.ingestion.providers.base import Extractor, RawPoint, SourceDescriptor

__all__ = ["Extractor", "RawPoint", "SourceDescriptor", "build_extractor"]


def build_extractor(provider: str | None = None, settings: Settings | None = None) -> Extractor:
    s = settings or get_settings()
    name = (provider or s.ingest_provider).lower()
    if name == "bitfinex":
        from acme_dwh.ingestion.providers.bitfinex import BitfinexExtractor

        return BitfinexExtractor()
    if name in ("nasdaq_data_link", "ndl", "nasdaq", "quandl"):
        from acme_dwh.ingestion.providers.nasdaq_data_link import NasdaqDataLinkExtractor

        return NasdaqDataLinkExtractor(api_key=s.ndl_api_key)
    raise ValueError(f"Unknown ingest provider: {provider!r} (use 'bitfinex' or 'nasdaq_data_link')")
