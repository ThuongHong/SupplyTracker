from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.collectors.base import BaseCollector, CollectionResult
from app.config import get_settings
from app.db.models import Chokepoint, NewsItem, Port
from app.services.disruption import _CHOKEPOINT_LANE_MAP

logger = logging.getLogger(__name__)

_GNEWS_URL = "https://gnews.io/api/v4/search"
_PRUNE_DAYS = 90
_HTTP_TIMEOUT = 15


def _build_query(entity_type: str, name: str, locode_or_aliases: str | list[str]) -> str:
    if entity_type == "port":
        locode = locode_or_aliases if isinstance(locode_or_aliases, str) else ""
        parts = [f'"{name}"']
        if locode:
            parts.append(f"{locode} port")
        return " OR ".join(parts)
    else:
        aliases = locode_or_aliases if isinstance(locode_or_aliases, list) else []
        terms = [f'"{name}"'] + [f'"{alias}"' for alias in aliases]
        return " OR ".join(terms)


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()[:2048]).hexdigest()[:64]


def _chokepoint_aliases(cp_name: str) -> list[str]:
    key = cp_name.lower().replace(" ", "_")
    lane = _CHOKEPOINT_LANE_MAP.get(key)
    if lane is None:
        return []
    return [k for k, v in _CHOKEPOINT_LANE_MAP.items() if v == lane and k != key]


class GoogleNewsCollector(BaseCollector):
    source_name = "news"

    def collect(self, session: Session) -> CollectionResult:
        settings = get_settings()

        if not settings.news_fetch_enabled:
            logger.info("News fetch is disabled; skipping.")
            return CollectionResult(rows=0, errors=[])

        api_key = settings.gnews_api_key.get_secret_value()
        if not api_key:
            logger.warning("GNEWS_API_KEY not set; skipping news collection.")
            return CollectionResult(rows=0, errors=["GNEWS_API_KEY not configured"])

        max_items = settings.news_max_items_per_entity
        total_rows = 0
        errors: list[str] = []

        ports = session.query(Port).all()
        chokepoints = session.query(Chokepoint).all()

        with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
            for port in ports:
                entity_id = port.locode or port.name
                try:
                    inserted = self._fetch_and_upsert(
                        client=client,
                        session=session,
                        api_key=api_key,
                        entity_type="port",
                        entity_id=entity_id,
                        name=port.name,
                        locode_or_aliases=port.locode or "",
                        max_items=max_items,
                    )
                    total_rows += inserted
                except Exception as exc:
                    msg = f"port {entity_id}: {exc}"
                    logger.error("GoogleNewsCollector error — %s", msg)
                    errors.append(msg)

            for cp in chokepoints:
                entity_id = cp.name.lower().replace(" ", "_")
                try:
                    aliases = _chokepoint_aliases(cp.name)
                    inserted = self._fetch_and_upsert(
                        client=client,
                        session=session,
                        api_key=api_key,
                        entity_type="chokepoint",
                        entity_id=entity_id,
                        name=cp.name,
                        locode_or_aliases=aliases,
                        max_items=max_items,
                    )
                    total_rows += inserted
                except Exception as exc:
                    msg = f"chokepoint {entity_id}: {exc}"
                    logger.error("GoogleNewsCollector error — %s", msg)
                    errors.append(msg)

        cutoff = datetime.now(UTC) - timedelta(days=_PRUNE_DAYS)
        try:
            result = session.execute(
                delete(NewsItem).where(NewsItem.published_at < cutoff)
            )
            pruned = result.rowcount  # type: ignore[attr-defined]
            logger.info("GoogleNewsCollector pruned %d old news items", pruned)
        except Exception as exc:
            msg = f"prune error: {exc}"
            logger.error("GoogleNewsCollector prune failed — %s", msg)
            errors.append(msg)

        session.commit()
        return CollectionResult(rows=total_rows, errors=errors)

    def _fetch_and_upsert(
        self,
        client: httpx.Client,
        session: Session,
        api_key: str,
        entity_type: str,
        entity_id: str,
        name: str,
        locode_or_aliases: str | list[str],
        max_items: int,
    ) -> int:
        query = _build_query(entity_type, name, locode_or_aliases)
        params = {
            "q": query,
            "lang": "en",
            "max": min(max_items, 10),
            "apikey": api_key,
        }

        resp = client.get(_GNEWS_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

        articles = data.get("articles", [])
        if not articles:
            logger.debug("No news articles for %s %s", entity_type, entity_id)
            return 0

        inserted = 0
        now = datetime.now(UTC)

        for article in articles:
            url = article.get("url", "")
            if not url:
                continue

            title = article.get("title", "") or ""
            description = article.get("description") or None
            source_name = (article.get("source") or {}).get("name", "") or ""

            published_str = article.get("publishedAt", "")
            try:
                published_at = datetime.fromisoformat(
                    published_str.replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                published_at = now

            h = _url_hash(url)

            stmt = (
                pg_insert(NewsItem)
                .values(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    url_hash=h,
                    url=url,
                    title=title,
                    source=source_name[:128],
                    published_at=published_at,
                    summary=description,
                    language="en",
                    fetched_at=now,
                )
                .on_conflict_do_nothing(
                    index_elements=["entity_type", "entity_id", "url_hash"]
                )
            )
            result = session.execute(stmt)
            inserted += result.rowcount  # type: ignore[attr-defined]

        return inserted
