"""Ürün analizi, pazarlama metinleri ve platform görselleri."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.constitution import CONSTITUTION_ID, assert_ad_creative_intent
from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import (
    CopyGenerateRequest,
    CopyGenerateOut,
    CreativeCatalogOut,
    ProductAnalyzeOut,
    VisualGenerateRequest,
    VisualGenerateOut,
)
from app.services.credits import apply_credit_change
from app.services.creative.copywriter import generate_marketing_copies
from app.services.creative.platforms import COPY_TYPES, PLATFORMS
from app.services.creative.product_vision import analyze_product_image
from app.services.creative.visuals import generate_platform_visuals
from app.services.pricing import analyze_credit_cost, copy_gen_credit_cost, visual_credit_cost

router = APIRouter(prefix="/creative", tags=["creative"])

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}
MAX_BYTES = 8 * 1024 * 1024


def _media_root() -> Path:
    root = Path(get_settings().media_dir)
    if not root.is_absolute():
        root = Path(__file__).resolve().parent.parent.parent / root
    root.mkdir(parents=True, exist_ok=True)
    return root


@router.get("/catalog", response_model=CreativeCatalogOut)
def catalog() -> CreativeCatalogOut:
    return CreativeCatalogOut(
        platforms=[
            {
                "id": k,
                "label": v["label"],
                "width": v["width"],
                "height": v["height"],
                "ratio": v["ratio"],
            }
            for k, v in PLATFORMS.items()
        ],
        copy_types=[
            {"id": k, "label": v["label"], "hint": v["hint"]} for k, v in COPY_TYPES.items()
        ],
        costs={
            "analyze": analyze_credit_cost(),
            "copy": copy_gen_credit_cost(),
            "visual_per_platform": visual_credit_cost(1),
        },
        constitution_id=CONSTITUTION_ID,
        constitution_locked=True,
        deviation_allowed=False,
    )


@router.post("/analyze-product", response_model=ProductAnalyzeOut)
async def analyze_product(
    file: UploadFile = File(...),
    language: str = Form(default="tr"),
    extra_context: str = Form(default=""),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProductAnalyzeOut:
    suffix = Path(file.filename or "product.jpg").suffix.lower()
    if suffix not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail="Sadece jpg/png/webp yükleyin")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Boş dosya")
    if len(raw) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="Dosya 8MB’dan büyük olamaz")

    cost = analyze_credit_cost()
    apply_credit_change(
        db,
        user,
        -cost,
        "Ürün görseli analizi",
        reference_type="creative_analyze",
        reference_id=None,
    )

    upload_dir = _media_root() / "uploads" / str(user.id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex[:12]}{suffix}"
    path = upload_dir / name
    path.write_bytes(raw)

    try:
        analysis = await analyze_product_image(
            db,
            user,
            image_path=path,
            language=language,
            extra_context=extra_context.strip(),
        )
    except Exception as exc:  # noqa: BLE001
        apply_credit_change(
            db,
            user,
            cost,
            "Analiz iadesi",
            reference_type="refund",
            reference_id=None,
            allow_negative=True,
        )
        db.commit()
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Analiz hatası: {exc}") from exc

    db.commit()
    image_url = f"/media/uploads/{user.id}/{name}"
    return ProductAnalyzeOut(
        image_url=image_url,
        analysis=analysis,
        credit_cost=cost,
    )


@router.post("/generate-copy", response_model=CopyGenerateOut)
async def generate_copy(
    payload: CopyGenerateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CopyGenerateOut:
    cost = copy_gen_credit_cost()
    apply_credit_change(
        db,
        user,
        -cost,
        "Pazarlama metni üretimi",
        reference_type="creative_copy",
        reference_id=None,
    )
    try:
        result = await generate_marketing_copies(
            db,
            user,
            analysis=payload.analysis,
            copy_types=payload.copy_types,
            language=payload.language,
            offer=payload.offer,
            pain_point=payload.pain_point,
            desired_action=payload.desired_action,
            audience=payload.audience or "",
            extra_brief=payload.extra_brief or "",
        )
    except Exception as exc:  # noqa: BLE001
        apply_credit_change(
            db,
            user,
            cost,
            "Metin iadesi",
            reference_type="refund",
            reference_id=None,
            allow_negative=True,
        )
        db.commit()
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Metin hatası: {exc}") from exc

    db.commit()
    return CopyGenerateOut(copies=result.get("copies") or {}, mock=bool(result.get("mock")), credit_cost=cost)


@router.post("/generate-visuals", response_model=VisualGenerateOut)
async def generate_visuals(
    payload: VisualGenerateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VisualGenerateOut:
    n = max(1, len(payload.platforms))
    cost = visual_credit_cost(n)
    apply_credit_change(
        db,
        user,
        -cost,
        f"Platform görseli x{n}",
        reference_type="creative_visual",
        reference_id=None,
    )
    try:
        items = await generate_platform_visuals(
            db,
            user,
            media_root=_media_root(),
            analysis=payload.analysis,
            platforms=payload.platforms,
            language=payload.language,
            offer=payload.offer,
            style=payload.style,
        )
    except Exception as exc:  # noqa: BLE001
        apply_credit_change(
            db,
            user,
            cost,
            "Görsel iadesi",
            reference_type="refund",
            reference_id=None,
            allow_negative=True,
        )
        db.commit()
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Görsel hatası: {exc}") from exc

    db.commit()
    return VisualGenerateOut(
        visuals=items,
        mock=get_settings().mock_ai,
        credit_cost=cost,
    )
