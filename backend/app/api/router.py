from __future__ import annotations

from fastapi import APIRouter

from app.api.routes.chat import router as chat_router
from app.api.routes.brief import router as brief_router
from app.api.routes.chokepoints import router as chokepoints_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.health import router as health_router
from app.api.routes.indices import router as indices_router
from app.api.routes.insights import router as insights_router
from app.api.routes.market import router as market_router
from app.api.routes.news import router as news_router
from app.api.routes.ports import router as ports_router
from app.api.routes.risk import router as risk_router
from app.api.routes.stats import router as stats_router
from app.api.routes.story import router as story_router
from app.api.routes.sync import router as sync_router

router = APIRouter()

router.include_router(health_router)
router.include_router(ports_router)
router.include_router(chokepoints_router)
router.include_router(indices_router)
router.include_router(risk_router)
router.include_router(story_router)
router.include_router(brief_router)
router.include_router(news_router)
router.include_router(dashboard_router)
router.include_router(insights_router)
router.include_router(market_router)
router.include_router(stats_router)
router.include_router(sync_router)
router.include_router(chat_router)
