from __future__ import annotations

from fastapi import APIRouter

from services.universe_scanner import universe_suggestions

router = APIRouter(tags=["universe"])


@router.get("/universe/suggestions")
def universe_suggestions_route(limit: int = 12):
    items, meta = universe_suggestions(limit=limit)
    return {
        "suggestions": items,
        "meta": meta,
    }
