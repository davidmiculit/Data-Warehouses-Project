"""CLI entry point for ingestion.

Examples:
    python -m acme_dwh.ingestion.run_ingestion BTCUSD ETHUSD
    python -m acme_dwh.ingestion.run_ingestion BTCUSD --start 2020-01-01 --end 2021-01-01
    python -m acme_dwh.ingestion.run_ingestion BTCUSD --provider nasdaq_data_link
"""
from __future__ import annotations

import argparse
import logging
from datetime import date

from acme_dwh.config import get_settings
from acme_dwh.ingestion.load import Ingestor
from acme_dwh.ingestion.providers import build_extractor


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()

    parser = argparse.ArgumentParser(description="Ingest financial time-series into the Acme DWH.")
    parser.add_argument("symbols", nargs="+", help="provider symbols, e.g. BTCUSD ETHUSD")
    parser.add_argument(
        "--provider", default=settings.ingest_provider, help="bitfinex | nasdaq_data_link"
    )
    parser.add_argument("--start", type=date.fromisoformat, default=None, help="YYYY-MM-DD (inclusive)")
    parser.add_argument("--end", type=date.fromisoformat, default=None, help="YYYY-MM-DD (exclusive)")
    args = parser.parse_args(argv)

    extractor = build_extractor(args.provider, settings)
    try:
        ingestor = Ingestor(extractor)
        for symbol in args.symbols:
            stats = ingestor.ingest_symbol(symbol, args.start, args.end)
            print(stats)
    finally:
        close = getattr(extractor, "close", None)
        if callable(close):
            close()


if __name__ == "__main__":
    main()
