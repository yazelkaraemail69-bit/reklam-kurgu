from __future__ import annotations

import json
import re
from typing import Any

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ApiKey, ApiProvider, User
from app.security import decrypt_api_key
from app.services.shorts_prompt import SHORTS_SYSTEM_PROMPT, SHORTS_USER_PREFIX


def _get_user_openrouter_key(db: Session, user: User) -> str | None:
    row = db.scalar(
        select(ApiKey).where(
            ApiKey.user_id == user.id,
            ApiKey.provider == ApiProvider.openrouter,
        )
    )
    if row:
        return decrypt_api_key(row.key_encrypted)
    return get_settings().openrouter_api_key or None


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _topic_seed(raw_input: str) -> str:
    """Brief'ten kısa konu çekirdeği — tekrar için değil, bağlam için."""
    cleaned = re.sub(r"\s+", " ", raw_input.strip())
    return cleaned[:90]


def _scene_plan(duration_seconds: int) -> list[tuple[str, int]]:
    """(role, süre_sn) — reklam ritmi."""
    if duration_seconds <= 15:
        return [("hook", 3), ("pain", 4), ("value", 4), ("cta", 4)]
    if duration_seconds <= 30:
        return [
            ("hook", 3),
            ("pain", 5),
            ("value", 7),
            ("proof", 7),
            ("cta", 5),
        ]
    if duration_seconds <= 45:
        return [
            ("hook", 3),
            ("pain", 6),
            ("value", 8),
            ("proof", 10),
            ("cta", 6),
        ]
    return [
        ("hook", 3),
        ("pain", 7),
        ("value", 10),
        ("proof", 12),
        ("cta", 8),
    ]


def _action_label(desired_action: str, *, en: bool) -> str:
    labels = {
        "dm": ("DM me now", "Hemen DM at"),
        "link_click": ("Tap the link", "Linke tıkla"),
        "buy": ("Buy now", "Hemen satın al"),
        "lead_form": ("Fill the form", "Formu doldur"),
        "whatsapp": ("Message on WhatsApp", "WhatsApp’tan yaz"),
    }
    pair = labels.get(desired_action, labels["dm"])
    return pair[0] if en else pair[1]


def _mock_script(
    *,
    language: str,
    title: str | None,
    duration_seconds: int,
    style: str,
    audience: str | None,
    raw_input: str,
    offer: str = "",
    pain_point: str = "",
    desired_action: str = "dm",
) -> dict[str, Any]:
    """Dönüşüm odaklı mock reklam senaryosu."""
    en = language.lower().startswith("en")
    topic = _topic_seed(raw_input)
    who = audience or ("buyers" if en else "müşteri")
    offer_t = (offer or topic)[:80]
    pain_t = (pain_point or topic)[:80]
    cta_t = _action_label(desired_action, en=en)
    plan = _scene_plan(duration_seconds)

    if en:
        hooks = [
            {"id": "A", "text": f"Still stuck with {pain_t}?", "angle": "pain"},
            {"id": "B", "text": f"What if {offer_t} fixed that in days?", "angle": "result"},
            {"id": "C", "text": f"Stop scrolling if you want {offer_t}.", "angle": "pattern_interrupt"},
        ]
        beats = {
            "hook": (
                hooks[0]["text"],
                "UGC close-up, snap zoom, high contrast text",
                "WAIT.",
                "zoom-punch",
            ),
            "pain": (
                f"Most {who} keep paying for the wrong fix — and {pain_t} stays.",
                "Handheld frustration, quick jump cuts",
                "The real pain",
                "hard-cut",
            ),
            "value": (
                f"Here's the shift: {offer_t} — built for {who}.",
                "Product insert + clean text-pop",
                "The offer",
                "match-cut",
            ),
            "proof": (
                "Same problem, clearer result — one simple move, visible payoff.",
                "Before/after split, punch-in on result",
                "Proof",
                "hard-cut",
            ),
            "cta": (
                f"{cta_t}. Do it before you forget.",
                "End card, bold CTA text, subtle push-in",
                cta_t,
                "zoom-punch",
            ),
        }
        lang_title = title or "Ad Script"
        music = "105bpm dry punchy, conversion energy"
        edit_notes = "Hard cuts every 2–4s, captions on, CTA readable in last 3s."
    else:
        hooks = [
            {"id": "A", "text": f"Hâlâ {pain_t} ile mi uğraşıyorsun?", "angle": "pain"},
            {"id": "B", "text": f"{offer_t} bunu günler içinde çözse?", "angle": "result"},
            {"id": "C", "text": f"{offer_t} istiyorsan kaydırmayı bırak.", "angle": "pattern_interrupt"},
        ]
        beats = {
            "hook": (
                hooks[0]["text"],
                "UGC close-up, ani zoom-punch, yüksek kontrast yazı",
                "DUR.",
                "zoom-punch",
            ),
            "pain": (
                f"Çoğu {who} yanlış çözüme para yakıyor — {pain_t} bitmiyor.",
                "El kamerası montaj, hızlı jump-cut",
                "Asıl acı",
                "hard-cut",
            ),
            "value": (
                f"Kırılma: {offer_t} — {who} için net çözüm.",
                "Ürün insert + temiz text-pop",
                "Teklif",
                "match-cut",
            ),
            "proof": (
                "Aynı sorun, daha net sonuç — tek hareket, görünür payoff.",
                "Önce/sonra split, sonuca punch-in",
                "Kanıt",
                "hard-cut",
            ),
            "cta": (
                f"{cta_t}. Unutmadan şimdi yap.",
                "End card, kalın CTA yazısı, hafif push-in",
                cta_t,
                "zoom-punch",
            ),
        }
        lang_title = title or "Reklam Senaryosu"
        music = "105bpm kuru vuruşlu, dönüşüm enerjisi"
        edit_notes = "2–4 sn’de hard-cut, caption açık, son 3 sn CTA okunaklı."

    scenes: list[dict[str, Any]] = []
    t = 0
    narrations: list[str] = []
    for i, (role, dur) in enumerate(plan):
        narration, visual, on_screen, cut = beats[role]
        if i == len(plan) - 1:
            dur = max(2, duration_seconds - t)
        end = t + dur
        scenes.append(
            {
                "index": i + 1,
                "role": role,
                "timecode": f"{t}-{end}s",
                "visual": visual,
                "narration": narration,
                "on_screen_text": on_screen,
                "cut": cut,
            }
        )
        narrations.append(narration)
        t = end

    return {
        "title": lang_title,
        "format": "ads_9x16",
        "hook": hooks[0]["text"],
        "hook_variants": hooks,
        "conversion_score": {
            "total": 78,
            "hook_strength": 82,
            "offer_clarity": 80,
            "cta_clarity": 74,
            "note": "Hook acıyı yakalıyor; CTA net. Kanıt sahnesi güçlendirilebilir."
            if not en
            else "Hook hits the pain; CTA is clear. Proof beat can be stronger.",
        },
        "voiceover_full": " ".join(narrations),
        "music_mood": music,
        "cta": cta_t,
        "edit_notes": edit_notes,
        "brief": {
            "offer": offer,
            "pain_point": pain_point,
            "desired_action": desired_action,
            "ad_format": style,
        },
        "scenes": scenes,
        "_mock": True,
    }


async def professionalize_prompt(
    db: Session,
    user: User,
    *,
    language: str,
    title: str | None,
    duration_seconds: int,
    style: str,
    audience: str | None,
    raw_input: str,
    offer: str = "",
    pain_point: str = "",
    desired_action: str = "dm",
) -> dict[str, Any]:
    settings = get_settings()
    api_key = _get_user_openrouter_key(db, user)

    if settings.mock_ai:
        return _mock_script(
            language=language,
            title=title,
            duration_seconds=duration_seconds,
            style=style,
            audience=audience,
            raw_input=raw_input,
            offer=offer,
            pain_point=pain_point,
            desired_action=desired_action,
        )

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "OpenRouter API anahtarı bulunamadı. "
                "Ayarlardan kaydedin veya MOCK_AI=true kullanın."
            ),
        )

    user_payload = {
        "language": language,
        "title": title,
        "duration_seconds": duration_seconds,
        "ad_format": style,
        "audience": audience,
        "offer": offer,
        "pain_point": pain_point,
        "desired_action": desired_action,
        "format": "ads_9x16",
        "user_brief": raw_input,
        "editor_mandate": (
            "Brief'i tekrar etme. Performance reklamcı gibi "
            "hook→pain→value→proof→cta ritminde yeniden yaz. "
            "3 hook varyantı + conversion_score zorunlu."
        ),
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": settings.app_name,
    }
    body = {
        "model": settings.openrouter_model,
        "messages": [
            {"role": "system", "content": SHORTS_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": SHORTS_USER_PREFIX
                + "\n\n"
                + json.dumps(user_payload, ensure_ascii=False, indent=2),
            },
        ],
        "temperature": 0.75,
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
            detail=f"OpenRouter bağlantı hatası: {exc}",
        ) from exc

    if resp.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenRouter hata ({resp.status_code}): {resp.text[:400]}",
        )

    data = resp.json()
    try:
        content = data["choices"][0]["message"]["content"]
        script = _extract_json(content)
    except (KeyError, IndexError, json.JSONDecodeError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenRouter yanıtı parse edilemedi",
        ) from exc

    if not isinstance(script, dict) or "scenes" not in script:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Senaryo şeması geçersiz",
        )
    script.setdefault("format", "ads_9x16")
    script.setdefault(
        "brief",
        {
            "offer": offer,
            "pain_point": pain_point,
            "desired_action": desired_action,
            "ad_format": style,
        },
    )
    if not script.get("hook_variants"):
        hook = str(script.get("hook") or "")
        script["hook_variants"] = [
            {"id": "A", "text": hook, "angle": "pain"},
            {"id": "B", "text": hook, "angle": "result"},
            {"id": "C", "text": hook, "angle": "curiosity"},
        ]
    if not script.get("conversion_score"):
        script["conversion_score"] = {
            "total": 70,
            "hook_strength": 70,
            "offer_clarity": 70,
            "cta_clarity": 70,
            "note": "Skor model yanıtında eksikti; varsayılan atandı.",
        }
    else:
        score = script["conversion_score"]
        if isinstance(score, dict):
            for k in ("total", "hook_strength", "offer_clarity", "cta_clarity"):
                try:
                    score[k] = max(0, min(100, int(float(score.get(k, 0)))))
                except (TypeError, ValueError):
                    score[k] = 0
            score.setdefault("note", "")
            script["conversion_score"] = score
    return script
