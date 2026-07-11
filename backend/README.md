# Reklam Kurgu

3 ajanlı reklam senaryosu + short video üretim hattı.

## AI görev dağılımı

| Ajan | Rol | Sağlayıcı |
|------|-----|-----------|
| AI1 | Reklam senaryosu (hook → pain → value → proof → CTA) | OpenRouter / Claude |
| AI2 | Her sahne için 9:16 reklam görseli | OpenRouter image (Flux / DALL·E) |
| AI3 | Görsel + ElevenLabs ses + kurgu → MP4 | FFmpeg (imageio-ffmpeg) |

Her aşamada OpenRouter bağlantısı doğrulanır; rate limit / 401 net hata döner.

## .env anahtarları

`backend/.env.example` dosyasına bak. Zorunlu canlı üretim için:

```
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=anthropic/claude-sonnet-4
OPENROUTER_IMAGE_MODEL=black-forest-labs/flux.2-pro
ELEVENLABS_API_KEY=...
ENCRYPTION_KEY=...   # Fernet
JWT_SECRET=...
MOCK_AI=false
ADMIN_EMAIL=senin@email.com
```

Geliştirmede `MOCK_AI=true` yeterli (sahte senaryo/görsel/ses).

## Çalıştırma

```bash
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Stüdyo: http://localhost:8000  
Admin: http://localhost:8000/admin

## Akış

1. **AI1: Reklam Senaryosu Yaz** (teklif + acı nokta + CTA)
2. Hook varyantı seç + dönüşüm skorunu kontrol et
3. **AI2+AI3: Görsel Üret & Kurguya Ver** → MP4 + Eleştiri Raporu
4. Eleştiri yaz → yalnız ilgili parça revize + yeniden kurgu
