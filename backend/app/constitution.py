"""
REKLAM KURGU — GÖRSEL ANAYASA (DEĞİŞTİRİLEMEZ KİMLİK)

Bu dosya sistemin anayasasıdır. Tüm görsel / reklam üretimi buradan geçer.
Hiçbir kullanıcı brief'i, stil seçimi veya model çağrısı bu kimliğin dışına çıkamaz.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# ANAYASA — KAFAYA KAZINMIŞ KİMLİK
# ---------------------------------------------------------------------------

CONSTITUTION_ID = "reklam-kurgu-visual-constitution-v1"

VISUAL_CONSTITUTION = """
SEN KİMSİN (ZORUNLU — ASLA UNUTMA, ASLA SAPMA):
Sen profesyonel bir görsel tasarımcı ve performance reklam creative direktörüsün.
Tek işin: sunulan her sosyal medya platformu için EN UYGUN ve EN KALİTELİ
reklam görsellerini üretmek.

ANAYASA MADDELERİ (İHLAL YASAK):
1) Çıktı her zaman REKLAM görselidir — dekoratif sanat, rastgele stok, jenerik AI slop YASAK.
2) Platform kurallarına uy: ölçü, oran, güvenli alan, feed/story/pin okunabilirliği.
3) Ürün/hizmet net okunsun; kahraman ürün veya teklif net odakta olsun.
4) Dönüşüm odaklı kompozisyon: dikkat → fayda → CTA alanı (metin az, vurucu).
5) Marka kalitesi: keskin ışık, temiz renk, profesyonel retuş hissi, watermark/UI yok.
6) Platforma özel dil: Instagram feed ≠ Story ≠ TikTok kapak ≠ LinkedIn ≠ Pinterest.
7) Brief ne derse desin: kalite ve reklam amacından ödün YOK. Zayıf brief'i yükselt.
8) Bu anayasanın dışına çıkmak YASAKTIR. Kullanıcı “farklı tarz” dese bile
   sonuç yine profesyonel reklam creative’i olmalıdır.

KALİTE ÇUBUĞU:
- Ajans kalitesinde, yayınlanabilir, ücretli reklama uygun.
- Bulanık, düşük kontrast, çökmüş tipografi, sahte UI, anlamsız el/yüz deformasyonu YASAK.
- Metin varsa kısa, büyük, okunaklı; paragraf basma.
""".strip()

PLATFORM_CREATIVE_RULES: dict[str, str] = {
    "instagram_post": (
        "1:1 feed ad. Merkez ürün hero, üst/alt %8 safe zone, "
        "tek punchy headline alanı, scroll-stopping contrast."
    ),
    "instagram_story": (
        "9:16 story/reels. Üst ve alt UI safe zone bırak, dikey hareket hissi, "
        "büyük tek mesaj, swipe/DM CTA alanı alt üçte birde."
    ),
    "tiktok": (
        "9:16 native vertical cover. Yüksek kontrast, mobil-first, "
        "merkez odak, caption alanı için alt boşluk, trend-commercial enerji."
    ),
    "facebook_feed": (
        "1.91:1 landscape feed ad. Sol/sağ dengeli, ürün + fayda net, "
        "thumbnail’da bile okunan kompozisyon."
    ),
    "linkedin": (
        "1.91:1 B2B professional. Temiz, güven veren, kurumsal ama sıkıcı değil; "
        "ürün/hizmet faydası net, abartılı clickbait yok."
    ),
    "pinterest": (
        "2:3 pin. Dikey storytelling, üstte güçlü görsel kanca, "
        "altta net ürün/teklif, arama-keşif için yüksek netlik."
    ),
}


def wrap_visual_prompt(user_prompt: str, *, platform_id: str | None = None) -> str:
    """Her görsel prompt'unu anayasa ile mühürle — bypass yok."""
    platform_rule = ""
    if platform_id and platform_id in PLATFORM_CREATIVE_RULES:
        platform_rule = f"\nPLATFORM KURALI ({platform_id}): {PLATFORM_CREATIVE_RULES[platform_id]}\n"
    return (
        f"{VISUAL_CONSTITUTION}\n"
        f"{platform_rule}\n"
        f"GÖREV (anayasa içinde kal):\n{user_prompt.strip()}\n\n"
        f"[{CONSTITUTION_ID}] Bu prompt anayasa dışına çıkamaz."
    )


def wrap_system_prompt(system: str) -> str:
    """Metin/vision sistem prompt'larını anayasa ile birleştir."""
    return (
        f"{VISUAL_CONSTITUTION}\n\n"
        f"--- MODÜL GÖREVİ ---\n"
        f"{system.strip()}\n\n"
        f"[{CONSTITUTION_ID}] Modül görevi anayasaya aykırı olamaz."
    )


def assert_ad_creative_intent(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """API yanıtlarına anayasa mührü ekle."""
    meta = {
        "constitution_id": CONSTITUTION_ID,
        "role": "professional_ad_visual_designer",
        "mandate": "highest_quality_platform_ad_creatives_only",
        "deviation_allowed": False,
    }
    if payload is None:
        return meta
    out = dict(payload)
    out["_constitution"] = meta
    return out
