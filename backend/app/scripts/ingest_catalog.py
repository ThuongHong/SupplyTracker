"""Ingest the full PortWatch port/chokepoint metadata catalog (no metrics).

Run synchronously (no Celery) for one-off / manual catalog refresh:

    python -m app.scripts.ingest_catalog
"""
from __future__ import annotations

import logging

from app.collectors.catalog import CatalogCollector
from app.db.session import get_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    db_gen = get_db()
    session = next(db_gen)
    try:
        result = CatalogCollector().run(session)
        logger.info(
            "Catalog ingest complete: rows=%d errors=%d", result.rows, len(result.errors)
        )
        for err in result.errors:
            logger.warning("  %s", err)
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass


if __name__ == "__main__":
    main()
