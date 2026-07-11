"""Sosyal medya platform görsel ölçüleri ve metin türleri."""

from __future__ import annotations

from typing import Any

# platform_id -> spec
PLATFORMS: dict[str, dict[str, Any]] = {
    "instagram_post": {
        "label": "Instagram Post",
        "width": 1080,
        "height": 1080,
        "ratio": "1:1",
        "use": "feed",
    },
    "instagram_story": {
        "label": "Instagram / Reels Story",
        "width": 1080,
        "height": 1920,
        "ratio": "9:16",
        "use": "story",
    },
    "tiktok": {
        "label": "TikTok / Shorts kapak",
        "width": 1080,
        "height": 1920,
        "ratio": "9:16",
        "use": "vertical",
    },
    "facebook_feed": {
        "label": "Facebook / Meta Feed",
        "width": 1200,
        "height": 630,
        "ratio": "1.91:1",
        "use": "feed",
    },
    "linkedin": {
        "label": "LinkedIn Post",
        "width": 1200,
        "height": 627,
        "ratio": "1.91:1",
        "use": "b2b",
    },
    "pinterest": {
        "label": "Pinterest Pin",
        "width": 1000,
        "height": 1500,
        "ratio": "2:3",
        "use": "pin",
    },
}

COPY_TYPES: dict[str, dict[str, str]] = {
    "product_intro": {
        "label": "Ürün tanıtım metni",
        "hint": "Web / katalog için net ürün tanıtımı",
    },
    "instagram_post": {
        "label": "Instagram post metni",
        "hint": "Hook + fayda + CTA + hashtag",
    },
    "instagram_story": {
        "label": "Story / Reels metni",
        "hint": "Kısa, punchy, swipe-up / DM odaklı",
    },
    "facebook_ad": {
        "label": "Facebook reklam metni",
        "hint": "Primary text + headline + description",
    },
    "linkedin_post": {
        "label": "LinkedIn post",
        "hint": "Profesyonel ton, B2B fayda",
    },
    "whatsapp": {
        "label": "WhatsApp satış mesajı",
        "hint": "Kısa, samimi, tek CTA",
    },
    "benefits": {
        "label": "Fayda maddeleri",
        "hint": "3–6 bullet fayda listesi",
    },
    "landing_headline": {
        "label": "Landing başlık + alt başlık",
        "hint": "H1 + supporting line + CTA",
    },
}


def platform_ids() -> list[str]:
    return list(PLATFORMS.keys())


def copy_type_ids() -> list[str]:
    return list(COPY_TYPES.keys())
