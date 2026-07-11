from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.constitution import CONSTITUTION_ID, VISUAL_CONSTITUTION, assert_ad_creative_intent
from app.config import get_settings
from app.database import init_db
from app.routers import admin, api_keys, auth, creative, credits, jobs, media, scenarios

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
MEDIA_DIR = Path(__file__).resolve().parent.parent / "data" / "media"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    if settings.jwt_secret in ("", "change-me-to-a-long-random-string"):
        print("WARNING: JWT_SECRET varsayılan — üretimde güçlü bir secret kullanın.")
    if not settings.encryption_key:
        print("WARNING: ENCRYPTION_KEY boş — API anahtarları güvenli şifrelenemez.")
    init_db()
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description=(
            "Reklam Kurgu — profesyonel görsel tasarımcı anayasası: "
            "tüm platformlar için en kaliteli reklam görselleri. Sapma yok."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:8000",
            "http://localhost:8000",
            "http://127.0.0.1:8020",
            "http://localhost:8020",
            "http://127.0.0.1:8022",
            "http://localhost:8022",
            "http://127.0.0.1:8023",
            "http://localhost:8023",
            "http://127.0.0.1:8024",
            "http://localhost:8024",
            "http://127.0.0.1:8010",
            "http://127.0.0.1:8011",
            "http://127.0.0.1:8012",
            "http://127.0.0.1:8013",
            "http://127.0.0.1:8014",
            "http://127.0.0.1:8015",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth.router, prefix="/api")
    app.include_router(api_keys.router, prefix="/api")
    app.include_router(credits.router, prefix="/api")
    app.include_router(scenarios.router, prefix="/api")
    app.include_router(creative.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    app.include_router(admin.router, prefix="/api")
    app.include_router(media.router)

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "product": "reklam_kurgu",
            "constitution_id": CONSTITUTION_ID,
            "constitution_locked": True,
            "role": "professional_ad_visual_designer",
            "mandate": "highest_quality_platform_ad_creatives_only",
            "deviation_allowed": False,
            "agents": ["AI1_scenario", "product_vision", "copywriter", "platform_visuals"],
            "mock_ai": settings.mock_ai,
        }

    @app.get("/api/constitution")
    def constitution():
        return assert_ad_creative_intent(
            {
                "id": CONSTITUTION_ID,
                "text": VISUAL_CONSTITUTION,
                "locked": True,
                "applies_to": [
                    "platform_visuals",
                    "product_vision",
                    "copywriter",
                    "scenario",
                    "scene_stills",
                ],
            }
        )

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

        @app.get("/")
        def studio():
            return FileResponse(
                STATIC_DIR / "index.html",
                headers={"Cache-Control": "no-store, max-age=0"},
            )

        @app.get("/admin")
        def admin_panel():
            return FileResponse(
                STATIC_DIR / "admin.html",
                headers={"Cache-Control": "no-store, max-age=0"},
            )

    return app


app = create_app()
