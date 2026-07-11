# Reklam Kurgu

İşletmeler için AI reklam senaryosu, ürün metni ve sosyal medya görselleri.

## Ne yapar?

1. **Senaryo** — Shorts/Reels: Hook → Pain → Value → Proof → CTA + hook A/B + dönüşüm skoru  
2. **Ürün analizi** — ürün görselini yükle, AI görseli analiz eder  
3. **Pazarlama metinleri** — tanıtım, Instagram, Facebook, LinkedIn, WhatsApp, fayda listesi, landing  
4. **Platform görselleri** — Instagram, TikTok/Shorts, Facebook, LinkedIn, Pinterest ölçüleri  

Video üretimi geri planda; odak senaryo + metin + pazarlama görseli.

## Reklam brief alanları

- Ürün / teklif  
- Müşteri acı noktası  
- Hedef aksiyon (DM, link, satın al, form, WhatsApp)  
- Format (PAS, UGC, önce/sonra, teklif+aciliyet, sosyal kanıt)  

## Hızlı başlangıç

```bash
cd backend
python -m venv .venv
# Windows:
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

`.env` içine anahtarlarını yaz (detay: [`backend/.env.example`](backend/.env.example)):

- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL=anthropic/claude-sonnet-4`
- `OPENROUTER_IMAGE_MODEL=black-forest-labs/flux.2-pro`
- `ELEVENLABS_API_KEY`
- `ENCRYPTION_KEY` (Fernet)
- `JWT_SECRET`
- `ADMIN_EMAIL` (sonsuz kredi + admin panel)
- `MOCK_AI=false` (canlı) veya `true` (geliştirme)

```bash
uvicorn app.main:app --reload --port 8000
```

- Stüdyo: http://localhost:8000  
- Admin: http://localhost:8000/admin  
- API docs: http://localhost:8000/docs  

Daha fazla: [`backend/README.md`](backend/README.md)
