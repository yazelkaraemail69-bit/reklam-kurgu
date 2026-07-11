"""Ürün/hizmet pazarlama metinleri — analiz + brief’ten üretir."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.constitution import wrap_system_prompt
from app.models import User
from app.services.creative.platforms import COPY_TYPES
from app.services.director.integration import resolve_openrouter_key

COPY_SYSTEM = wrap_system_prompt(
    """
Sen 10+ yıllık performance copywriter + sosyal medya metin yazarısın.
Ürün analizini ve brief’i kullanarak seçilen metin türlerini yaz.
Satış/tıklama odaklı ol; jargon ve boş slogan yasak.
Her tür için ayrı, platforma uygun uzunluk kullan.
Metinler, profesyonel reklam görselleriyle birlikte çalışacak şekilde yazılsın.
Yanıt SADECE JSON:
{
  "copies": {
    "<type_id>": {
      "title": "kısa başlık",
      "body": "ana metin",
      "cta": "tek net CTA",
      "hashtags": ["..."],
      "notes": "1 cümle kullanım notu"
    }
  }
}
""".strip()
)


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _mock_copies(
    *,
    analysis: dict[str, Any],
    copy_types: list[str],
    offer: str,
    pain_point: str,
    desired_action: str,
    language: str,
) -> dict[str, Any]:
    name = analysis.get("product_name") or "Ürün"
    points = analysis.get("key_selling_points") or ["Kalite", "Kolay kullanım"]
    en = language.lower().startswith("en")
    action = {
        "dm": ("DM me", "Hemen DM at"),
        "link_click": ("Tap the link", "Linke tıkla"),
        "buy": ("Buy now", "Hemen satın al"),
        "lead_form": ("Fill the form", "Formu doldur"),
        "whatsapp": ("WhatsApp us", "WhatsApp’tan yaz"),
    }.get(desired_action, ("Act now", "Hemen harekete geç"))
    cta = action[0] if en else action[1]
    pain = pain_point or (analysis.get("target_audience_guess") or "")
    offer_t = offer or name

    templates: dict[str, dict[str, Any]] = {
        "product_intro": {
            "title": name if not en else name,
            "body": (
                f"{name} — {offer_t}. "
                f"{'Designed for people tired of ' + pain + '. ' if en else pain + ' derdine net çözüm. '}"
                f"{'Key points: ' if en else 'Öne çıkanlar: '}{'; '.join(points[:3])}."
            ),
            "cta": cta,
            "hashtags": [],
            "notes": "Web / katalog tanıtım bloğu",
        },
        "instagram_post": {
            "title": f"{'Stop scrolling' if en else 'Dur'} — {name}",
            "body": (
                f"{'Still dealing with' if en else 'Hâlâ'} {pain}?\n\n"
                f"{offer_t}.\n"
                f"{'Why it works' if en else 'Neden işe yarar'}: {points[0]}.\n\n"
                f"{cta} {'today' if en else 'bugün'}."
            ),
            "cta": cta,
            "hashtags": ["#reklam", "#urun", "#kesfet"] if not en else ["#product", "#ads", "#fyp"],
            "notes": "Feed post — ilk satır hook",
        },
        "instagram_story": {
            "title": name,
            "body": f"{pain} → {offer_t}. {cta}.",
            "cta": cta,
            "hashtags": [],
            "notes": "Story / Reels overlay — max kısa",
        },
        "facebook_ad": {
            "title": offer_t[:40],
            "body": f"{pain}. {offer_t}. {points[0]}.",
            "cta": cta,
            "hashtags": [],
            "notes": "Primary text + headline olarak title kullan",
        },
        "linkedin_post": {
            "title": name,
            "body": (
                f"{'Most teams still struggle with' if en else 'Birçok işletme hâlâ şununla uğraşıyor:'} {pain}.\n\n"
                f"{offer_t}.\n\n"
                f"{'Outcome' if en else 'Sonuç'}: {points[0]}."
            ),
            "cta": cta,
            "hashtags": ["#marketing", "#growth"],
            "notes": "B2B ton",
        },
        "whatsapp": {
            "title": name,
            "body": f"Merhaba! {offer_t} ile {pain} sorununa pratik çözüm. {cta} 👋"
            if not en
            else f"Hi! {offer_t} fixes {pain}. {cta}",
            "cta": cta,
            "hashtags": [],
            "notes": "Tek mesaj, samimi",
        },
        "benefits": {
            "title": f"{name} {'benefits' if en else 'faydaları'}",
            "body": "\n".join(f"• {p}" for p in points[:6]),
            "cta": cta,
            "hashtags": [],
            "notes": "Bullet liste",
        },
        "landing_headline": {
            "title": offer_t[:60],
            "body": f"{pain} — {points[0]}.",
            "cta": cta,
            "hashtags": [],
            "notes": "H1=title, sub=body",
        },
    }

    copies = {t: templates.get(t, templates["product_intro"]) for t in copy_types if t in COPY_TYPES}
    return {"copies": copies, "mock": True}


async def generate_marketing_copies(
    db: Session,
    user: User,
    *,
    analysis: dict[str, Any],
    copy_types: list[str],
    language: str = "tr",
    offer: str = "",
    pain_point: str = "",
    desired_action: str = "dm",
    audience: str = "",
    extra_brief: str = "",
) -> dict[str, Any]:
    types = [t for t in copy_types if t in COPY_TYPES]
    if not types:
        raise HTTPException(status_code=400, detail="En az bir metin türü seçin")

    settings = get_settings()
    if settings.mock_ai:
        return _mock_copies(
            analysis=analysis,
            copy_types=types,
            offer=offer,
            pain_point=pain_point,
            desired_action=desired_action,
            language=language,
        )

    api_key = resolve_openrouter_key(db, user)
    if not api_key:
        raise HTTPException(status_code=400, detail="OpenRouter anahtarı gerekli (veya MOCK_AI=true).")

    payload = {
        "language": language,
        "copy_types": {t: COPY_TYPES[t] for t in types},
        "product_analysis": analysis,
        "offer": offer,
        "pain_point": pain_point,
        "desired_action": desired_action,
        "audience": audience,
        "extra_brief": extra_brief,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8021",
        "X-Title": settings.app_name,
    }
    body = {
        "model": settings.openrouter_model,
        "messages": [
            {"role": "system", "content": COPY_SYSTEM},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        "temperature": 0.7,
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
        raise HTTPException(status_code=502, detail=f"Copy bağlantı hatası: {exc}") from exc

    if resp.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Copy hata ({resp.status_code}): {resp.text[:400]}")

    try:
        data = _extract_json(resp.json()["choices"][0]["message"]["content"])
    except (KeyError, IndexError, json.JSONDecodeError, TypeError) as exc:
        raise HTTPException(status_code=502, detail="Copy yanıtı parse edilemedi") from exc

    copies = data.get("copies") if isinstance(data, dict) else None
    if not isinstance(copies, dict):
        raise HTTPException(status_code=502, detail="Copy şeması geçersiz")
    return {"copies": copies, "mock": False}
