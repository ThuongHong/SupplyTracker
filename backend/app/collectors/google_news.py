from __future__ import annotations

import calendar
import hashlib
import logging
from datetime import UTC, datetime, timedelta
from urllib.parse import quote_plus

import feedparser
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.collectors.base import BaseCollector, CollectionResult
from app.config import get_settings
from app.db.models import Chokepoint, NewsItem, Port
from app.services.disruption import _CHOKEPOINT_LANE_MAP

logger = logging.getLogger(__name__)

_GOOGLE_NEWS_URL = (
    "https://news.google.com/rss/search?q={query}&hl=en&gl=US&ceid=US:en"
)
_USER_AGENT = "Mozilla/5.0 (compatible; SupplyTracker/1.0)"

# Set feedparser's global user agent so all fetches use it.
feedparser.USER_AGENT = _USER_AGENT

_PRUNE_DAYS = 90


def _build_query(entity_type: str, name: str, locode_or_aliases: str | list[str]) -> str:
    """Build a Google News RSS search query string.

    For ports: locode_or_aliases is the LOCODE string (or empty string).
    For chokepoints: locode_or_aliases is a list of alias terms.
    """
    if entity_type == "port":
        locode = locode_or_aliases if isinstance(locode_or_aliases, str) else ""
        parts = [f'"{name}"']
        if locode:
            parts.append(f"{locode} port")
        return " OR ".join(parts)
    else:
        # chokepoint: name + alias terms
        aliases = locode_or_aliases if isinstance(locode_or_aliases, list) else []
        terms = [f'"{name}"'] + [f'"{alias}"' for alias in aliases]
        return " OR ".join(terms)


def _parse_published_at(entry: feedparser.FeedParserDict) -> datetime:
    """Parse published_at from a feedparser entry, falling back to now(UTC)."""
    parsed = getattr(entry, "published_parsed", None)
    if parsed is not None:
        try:
            return datetime.fromtimestamp(calendar.timegm(parsed), tz=UTC)
        except Exception:
            pass
    return datetime.now(UTC)


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()[:2048]).hexdigest()[:64]


def _chokepoint_aliases(cp_name: str) -> list[str]:
    """Return alias terms for the given chokepoint name (excluding the name itself).

    Finds the lane for this chokepoint, then collects all other keys that map
    to the same lane.
    """
    key = cp_name.lower().replace(" ", "_")
    lane = _CHOKEPOINT_LANE_MAP.get(key)
    if lane is None:
        return []
    # Gather all keys that map to the same lane, excluding the current key
    return [k for k, v in _CHOKEPOINT_LANE_MAP.items() if v == lane and k != key]


class GoogleNewsCollector(BaseCollector):
    source_name = "news"

    def collect(self, session: Session) -> CollectionResult:
        settings = get_settings()

        if not settings.news_fetch_enabled:
            logger.info("News fetch is disabled; skipping.")
            return CollectionResult(rows=0, errors=[])

        max_items = settings.news_max_items_per_entity
        total_rows = 0
        errors: list[str] = []

        ports = session.query(Port).all()
        chokepoints = session.query(Chokepoint).all()

        # Process ports
        for port in ports:
            entity_id = port.locode or port.name
            try:
                inserted = self._fetch_and_upsert(
                    session=session,
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

        # Process chokepoints
        for cp in chokepoints:
            entity_id = cp.name.lower().replace(" ", "_")
            try:
                aliases = _chokepoint_aliases(cp.name)
                inserted = self._fetch_and_upsert(
                    session=session,
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

        # Prune rows older than 90 days (once, after all entities)
        cutoff = datetime.now(UTC) - timedelta(days=_PRUNE_DAYS)
        try:
            result = session.execute(
                delete(NewsItem).where(NewsItem.published_at < cutoff)
            )
            pruned = result.rowcount
            logger.info("GoogleNewsCollector pruned %d old news items", pruned)
        except Exception as exc:
            msg = f"prune error: {exc}"
            logger.error("GoogleNewsCollector prune failed — %s", msg)
            errors.append(msg)

        session.commit()
        return CollectionResult(rows=total_rows, errors=errors)

    def _fetch_and_upsert(
        self,
        session: Session,
        entity_type: str,
        entity_id: str,
        name: str,
        locode_or_aliases: str | list[str],
        max_items: int,
    ) -> int:
        query = _build_query(entity_type, name, locode_or_aliases)
        encoded_query = quote_plus(query)
        url = _GOOGLE_NEWS_URL.format(query=encoded_query)

        try:
            feed = feedparser.parse(url)
        except Exception as exc:
            raise RuntimeError(f"feedparser.parse failed for {url!r}: {exc}") from exc

        if getattr(feed, "bozo", False) and not feed.entries:
            exc = getattr(feed, "bozo_exception", None)
            raise RuntimeError(f"Feed parse error for {entity_id!r}: {exc}")

        entries = feed.entries
        if not entries:
            logger.debug("No news entries for %s %s", entity_type, entity_id)
            return 0

        # Parse published_at for all entries so we can sort and cap
        parsed_entries = []
        for entry in entries:
            published_at = _parse_published_at(entry)
            parsed_entries.append((published_at, entry))

        # Sort descending by published_at and cap to max_items
        parsed_entries.sort(key=lambda t: t[0], reverse=True)
        parsed_entries = parsed_entries[:max_items]

        inserted = 0
        now = datetime.now(UTC)
        for published_at, entry in parsed_entries:
            link = getattr(entry, "link", None) or ""
            if not link:
                continue

            title = getattr(entry, "title", "") or ""
            summary = getattr(entry, "summary", None)
            source_title = ""
            raw_source = getattr(entry, "source", None)
            if raw_source is not None:
                source_title = getattr(raw_source, "title", "") or ""

            h = _url_hash(link)

            stmt = (
                pg_insert(NewsItem)
                .values(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    url_hash=h,
                    url=link,
                    title=title,
                    source=source_title[:128],
                    published_at=published_at,
                    summary=summary,
                    language="en",
                    fetched_at=now,
                )
                .on_conflict_do_nothing(
                    index_elements=["entity_type", "entity_id", "url_hash"]
                )
            )
            result = session.execute(stmt)
            inserted += result.rowcount

        return inserted
