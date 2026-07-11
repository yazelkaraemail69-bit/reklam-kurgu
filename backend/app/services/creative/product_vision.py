"""Ürün görseli analizi — vision (OpenRouter) + mock."""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.constitution import wrap_system_prompt
from app.models import User
from app.services.director.integration import resolve_openrouter_key

VISION_SYSTEM = wrap_system_prompt(
    """
Sen profesyonel bir ürün fotoğrafı ve marka analistisin.
Amacın: sonraki adımda EN KALİTELİ reklam görselleri ve satış metinleri üretilebilsin.
Görseli dikkatle incele; uydurma özellik yazma — gördüğünü ve makul çıkarımları ayır.
Yanıt SADECE JSON:
{
  "product_name": "string",
  "category": "string",
  "visual_description": "2-3 cümle görsel tarif",
  "colors": ["..."],
  "materials_or_texture": "string",
  "packaging": "string",
  "target_audience_guess": "string",
  "key_selling_points": ["..."],
  "mood_style": "string",
  "text_on_image": "görseldeki yazı varsa, yoksa boş",
  "marketing_angles": ["pain", "aspirational", "social_proof", "..."],
  "warnings": ["görselden net olmayan noktalar"]
}
""".strip()
)


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _mock_analysis(filename: str) -> dict[str, Any]:
    stem = Path(filename).stem.replace("_", " ")[:40] or "Ürün"
    return {
        "product_name": stem.title(),
        "category": "genel tüketici ürünü",
        "visual_description": (
            f"Temiz stüdyo ışığında çekilmiş {stem} görseli; "
            "ürün net odakta, arka plan sade, satışa uygun kompozisyon."
        ),
        "colors": ["krem", "mat siyah", "sıcak accent"],
        "materials_or_texture": "premium mat yüzey hissi",
        "packaging": "minimal etiket, okunaklı marka alanı",
        "target_audience_guess": "kalite arayan 25–40 yaş şehirli tüketiciler",
        "key_selling_points": [
            "Görselde net ürün kimliği",
            "Premium algı",
            "Sosyal medya feed’ine uygun çerçeve",
        ],
        "mood_style": "clean commercial / soft lifestyle",
        "text_on_image": "",
        "marketing_angles": ["aspirational", "quality", "convenience"],
        "warnings": ["Mock analiz — canlı vision için MOCK_AI=false ve OpenRouter gerekir"],
        "mock": True,
    }


async def analyze_product_image(
    db: Session,
    user: User,
    *,
    image_path: Path,
    language: str = "tr",
    extra_context: str = "",
) -> dict[str, Any]:
    settings = get_settings()
    if settings.mock_ai:
        data = _mock_analysis(image_path.name)
        data["language"] = language
        if extra_context:
            data["extra_context"] = extra_context[:500]
        return data

    api_key = resolve_openrouter_key(db, user)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OpenRouter anahtarı gerekli (veya MOCK_AI=true).",
        )

    raw = image_path.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    suffix = image_path.suffix.lower().lstrip(".") or "jpeg"
    mime = "image/png" if suffix == "png" else "image/webp" if suffix == "webp" else "image/jpeg"
    data_url = f"data:{mime};base64,{b64}"

    model = getattr(settings, "openrouter_vision_model", None) or settings.openrouter_model
    user_text = (
        f"Dil: {language}. Ürün görselini analiz et. "
        f"Ek bağlam: {extra_context or 'yok'}."
    )
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8021",
        "X-Title": settings.app_name,
    }
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": VISION_SYSTEM},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                f"{settings.openrouter_base_url}/chat/completions",
                headers=headers,
                json=body,
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Vision bağlantı hatası: {exc}",
        ) from exc

    if resp.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Vision hata ({resp.status_code}): {resp.text[:400]}",
        )

    try:
        content = resp.json()["choices"][0]["message"]["content"]
        data = _extract_json(content)
    except (KeyError, IndexError, json.JSONDecodeError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Vision yanıtı parse edilemedi",
        ) from exc

    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="Vision şeması geçersiz")
    data["mock"] = False
    data["language"] = language
    return data
