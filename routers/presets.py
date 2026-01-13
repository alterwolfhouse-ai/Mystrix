from __future__ import annotations

from typing import Dict

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from engine.presets import save_preset, get_presets


router = APIRouter(prefix="/api", tags=["presets"])


class SavePresetReq(BaseModel):
    product: str = Field(default="mystrix")
    symbol: str
    slot: str  # arbitrary slot name per asset
    params: Dict


@router.post("/presets/save")
def presets_save(req: SavePresetReq) -> Dict:
    try:
        slot = req.slot.strip()
        if not slot:
            raise HTTPException(400, "slot cannot be empty")
        save_preset(req.product, req.symbol, slot, req.params)
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/presets/get")
def presets_get(product: str = Query("mystrix"), symbol: str = Query(...)) -> Dict:
    try:
        data = get_presets(product, symbol)
        return {"product": product, "symbol": symbol, "presets": data}
    except Exception as e:
        raise HTTPException(500, str(e))

class DeletePresetReq(BaseModel):
    product: str = Field(default="mystrix")
    symbol: str
    slot: str

@router.post("/presets/delete")
def presets_delete(req: DeletePresetReq) -> Dict:
    from engine.presets import delete_preset
    try:
        slot = req.slot.strip()
        if not slot:
            raise HTTPException(400, "slot cannot be empty")
        delete_preset(req.product, req.symbol, slot)
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
