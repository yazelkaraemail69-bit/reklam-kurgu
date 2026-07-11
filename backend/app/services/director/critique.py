"""Tartışma / Eleştiri modülü — rapor + kısmi revizyon hedefleri."""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User
from app.services.director.integration import resolve_openrouter_key, verify_openrouter
from app.services.refine import refine_script


def build_critique_report(script: dict[str, Any], *, is_mock: bool = False) -> dict[str, Any]:
    """Video sonrası otomatik eleştiri raporu (yönetmen notları)."""
    scenes = script.get("scenes") or []
    strengths: list[str] = []
    risks: list[str] = []
    suggestions: list[str] = []

    if script.get("hook"):
        strengths.append("Hook tanımlı — ilk 3 sn scroll’u kesmeye hazır.")
    else:
        risks.append("Hook zayıf veya eksik — reklamda ilk 3 sn kritik.")

    if script.get("cta"):
        strengths.append(f"CTA mevcut: “{script.get('cta')}”.")
    else:
        risks.append("CTA yok — tıklama/satış eylemi eklenmeli.")

    score = script.get("conversion_score") or {}
    if isinstance(score, dict) and score.get("total") is not None:
        total = int(score.get("total") or 0)
        if total >= 75:
            strengths.append(f"Dönüşüm skoru {total}/100 — yayına yakın.")
        elif total >= 50:
            suggestions.append(f"Dönüşüm skoru {total}/100 — hook veya CTA güçlendir.")
        else:
            risks.append(f"Dönüşüm skoru düşük ({total}/100).")

    if script.get("hook_variants"):
        strengths.append("3 hook varyantı var — A/B testi için hazır.")

    if len(scenes) < 4:
        risks.append("Sahne sayısı reklam için az; ritim zayıf kalabilir.")
    elif len(scenes) > 7:
        risks.append("Sahne sayısı yüksek; tempo yavaşlayabilir.")
    else:
        strengths.append(f"{len(scenes)} sahne — kısa form reklam ritmine uygun.")

    narrations = [str(s.get("narration") or "") for s in scenes]
    if len(narrations) >= 2 and len(set(narrations)) < len(narrations):
        risks.append("Bazı sahnelerde anlatım tekrarı var.")
        suggestions.append("Tekrarlayan narration’ları farklı role göre yeniden yaz.")

    for s in scenes:
        if not s.get("visual") or len(str(s.get("visual"))) < 20:
            risks.append(f"Sahne {s.get('index')}: görsel tarif zayıf.")
        if not s.get("image"):
            suggestions.append(f"Sahne {s.get('index')} için görsel yeniden üretilebilir.")

    if not suggestions:
        suggestions.extend(
            [
                "Tempo yavaşsa: ‘sahne X daha hızlı’ de — sadece o sahne kısalır.",
                "Görsel zayıfsa: ‘sahne X daha çarpıcı görsel’ de — AI2 yalnız o kareyi yeniler.",
                "CTA zayıfsa: yeni kapanış cümlesini yaz — kurgu yeniden birleşir.",
            ]
        )

    return {
        "title": "Eleştiri Raporu",
        "verdict": "revize_edilebilir" if risks else "yayına_yakın",
        "strengths": strengths,
        "risks": risks,
        "suggestions": suggestions,
        "scene_count": len(scenes),
        "mock": is_mock,
        "how_to_reply": (
            "Örn: ‘Hook daha sert olsun’, ‘Acı noktasını güçlendir’, "
            "‘CTA’yı DM at yap’, ‘Sahne 3 görselini UGC yap’"
        ),
    }


def parse_feedback_targets(instruction: str, script: dict[str, Any]) -> dict[str, Any]:
    """Kullanıcı eleştirisinden hangi parçaların yenileneceğini çıkar."""
    lower = instruction.lower()
    scene_ids: list[int] = []
    for m in re.finditer(r"(?:sahne|scene)\s*#?\s*(\d+)", lower):
        scene_ids.append(int(m.group(1)))

    want_visuals = any(
        k in lower
        for k in ("görsel", "visual", "image", "çarpıcı", "sinematik", "kare", "shot")
    )
    want_script = any(
        k in lower
        for k in (
            "yavaş",
            "hızlı",
            "tempo",
            "hook",
            "cta",
            "acı",
            "pain",
            "teklif",
            "metin",
            "anlat",
            "senaryo",
            "narration",
            "ses",
        )
    )
    # Varsayılan: metin revizyonu
    if not want_visuals and not want_script:
        want_script = True

    if want_visuals and not scene_ids:
        # tüm sahneler yerine son/orta sahne varsayımı yerine hepsi değil — ilk problem sahnesi
        scenes = script.get("scenes") or []
        if scenes:
            scene_ids = [int(scenes[min(1, len(scenes) - 1)].get("index") or 1)]

    return {
        "regen_script": want_script,
        "regen_visuals": want_visuals,
        "scene_indices": scene_ids,
        "regen_audio": want_script or any(k in lower for k in ("ses", "voice", "anlat")),
    }


async def apply_critique_feedback(
    db: Session,
    user: User,
    *,
    script: dict[str, Any],
    instruction: str,
) -> dict[str, Any]:
    settings = get_settings()
    api_key = resolve_openrouter_key(db, user)
    if not settings.mock_ai:
        await verify_openrouter(api_key)

    targets = parse_feedback_targets(instruction, script)
    result = await refine_script(db, user, script=script, instruction=instruction)
    return {
        "script": result["script"],
        "changed_fields": result.get("changed_fields") or [],
        "summary": result.get("summary") or "",
        "targets": targets,
    }
