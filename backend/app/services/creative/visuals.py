"""Platform pazarlama görselleri üretimi."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import Session

from app.config import get_settings
from app.constitution import PLATFORM_CREATIVE_RULES, assert_ad_creative_intent, wrap_visual_prompt
from app.models import User
from app.services.creative.platforms import PLATFORMS
from app.services.director.ai2_visuals import _generate_via_openrouter
from app.services.director.integration import resolve_openrouter_key, verify_openrouter


def _font(size: int):
    for p in (
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
    ):
        if Path(p).exists():
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()


def _mock_platform_image(
    *,
    out_path: Path,
    width: int,
    height: int,
    platform_label: str,
    headline: str,
    product_name: str,
) -> None:
    img = Image.new("RGB", (width, height), (18, 22, 20))
    draw = ImageDraw.Draw(img)
    # soft gradient bars
    for y in range(height):
        t = y / max(1, height - 1)
        color = (
            int(30 + 40 * t),
            int(45 + 20 * (1 - t)),
            int(38 + 30 * t),
        )
        draw.line([(0, y), (width, y)], fill=color)

    pad = int(min(width, height) * 0.06)
    draw.rounded_rectangle(
        [pad, pad, width - pad, height - pad],
        radius=28,
        outline=(226, 168, 74),
        width=3,
    )
    title_font = _font(max(28, width // 18))
    small = _font(max(18, width // 32))
    draw.text((pad * 1.4, pad * 1.5), platform_label.upper(), font=small, fill=(159, 224, 198))
    # wrap headline roughly
    words = (headline or product_name or "Reklam").split()
    lines: list[str] = []
    cur = ""
    for w in words:
        test = f"{cur} {w}".strip()
        if len(test) > max(12, width // 40):
            if cur:
                lines.append(cur)
            cur = w
        else:
            cur = test
    if cur:
        lines.append(cur)
    y = height * 0.38
    for line in lines[:5]:
        draw.text((pad * 1.4, y), line, font=title_font, fill=(243, 239, 230))
        y += title_font.size + 10
    draw.text(
        (pad * 1.4, height - pad * 2.2),
        (product_name or "Reklam Kurgu")[:40],
        font=small,
        fill=(168, 176, 166),
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PNG")


def _visual_prompt(
    *,
    platform_id: str,
    platform: dict[str, Any],
    analysis: dict[str, Any],
    offer: str,
    style: str,
    language: str,
    product_image_base64: str | None = None,
) -> str:
    name = analysis.get("product_name") or "product"
    desc = analysis.get("visual_description") or ""
    colors = ", ".join(analysis.get("colors") or [])
    mood = analysis.get("mood_style") or "clean commercial"
    points = ", ".join((analysis.get("key_selling_points") or [])[:3])
    raw = (
        f"Create a publish-ready paid social AD creative for {platform.get('label')} "
        f"({platform.get('ratio')}, {platform.get('width')}x{platform.get('height')}). "
        f"Product hero: {name}. Offer: {offer or name}. "
        f"Selling points: {points or 'clarity and quality'}. "
        f"Look/mood: {mood}. Palette cues: {colors}. "
        f"Visual reference from product photo analysis: {desc}. "
        f"Campaign angle: {style}. "
        f"Agency-grade lighting, sharp product focus, conversion composition, "
        f"no watermark, no UI chrome, no long paragraphs on image. "
        f"Language context: {language}. "
        f"Extra platform craft: {PLATFORM_CREATIVE_RULES.get(platform_id, '')}"
    )
    # TODO: product_image_base64 varsa img2img/controlnet reference olarak ekle
    return wrap_visual_prompt(raw, platform_id=platform_id)


async def generate_platform_visuals(
    db: Session,
    user: User,
    *,
    media_root: Path,
    analysis: dict[str, Any],
    platforms: list[str],
    language: str = "tr",
    offer: str = "",
    style: str = "pas",
    product_image_base64: str | None = None,
) -> list[dict[str, Any]]:
    ids = [p for p in platforms if p in PLATFORMS]
    if not ids:
        raise HTTPException(status_code=400, detail="En az bir platform seçin")

    settings = get_settings()
    job_id = uuid.uuid4().hex[:12]
    out_dir = media_root / "creative" / str(user.id) / job_id
    out_dir.mkdir(parents=True, exist_ok=True)

    api_key = None
    if not settings.mock_ai:
        api_key = resolve_openrouter_key(db, user)
        if not api_key:
            raise HTTPException(status_code=400, detail="OpenRouter anahtarı gerekli (veya MOCK_AI=true).")
        await verify_openrouter(api_key)

    results: list[dict[str, Any]] = []
    for pid in ids:
        spec = PLATFORMS[pid]
        filename = f"{pid}.png"
        path = out_dir / filename
        if settings.mock_ai:
            _mock_platform_image(
                out_path=path,
                width=int(spec["width"]),
                height=int(spec["height"]),
                platform_label=str(spec["label"]),
                headline=offer or str(analysis.get("product_name") or "Kampanya"),
                product_name=str(analysis.get("product_name") or ""),
            )
        else:
            prompt = _visual_prompt(
                platform_id=pid,
                platform=spec,
                analysis=analysis,
                offer=offer,
                style=style,
                language=language,
                product_image_base64=product_image_base64,
            )
            # generate then resize to exact platform size
            tmp = out_dir / f"_tmp_{pid}.png"
            await _generate_via_openrouter(api_key or "", prompt, tmp)
            with Image.open(tmp) as im:
                im = im.convert("RGB")
                im = im.resize((int(spec["width"]), int(spec["height"])), getattr(Image, "Resampling", Image).LANCZOS)
                im.save(path, format="PNG")
            if tmp.exists():
                tmp.unlink(missing_ok=True)

        rel = f"/media/creative/{user.id}/{job_id}/{filename}"
        results.append(
            assert_ad_creative_intent(
                {
                    "platform": pid,
                    "label": spec["label"],
                    "width": spec["width"],
                    "height": spec["height"],
                    "ratio": spec["ratio"],
                    "url": rel,
                    "quality_bar": "agency_paid_social",
                }
            )
        )
    return results
