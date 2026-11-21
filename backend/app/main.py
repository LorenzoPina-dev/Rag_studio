import hmac
import math

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core import bootstrap  # noqa: F401  # initialize registries/container
from app.core.config import settings
from app.core.observability import setup_observability


def _json_safe(value):
    """Keep validation errors JSON-serializable even for NaN/Infinity inputs."""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.app_debug,
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    @app.middleware("http")
    async def require_api_token(request: Request, call_next):
        token = settings.api_access_token
        if token and request.method in {"POST", "PATCH", "PUT", "DELETE"}:
            path = request.url.path
            if path not in {"/docs", "/redoc", "/health"} and not path.endswith("/openapi.json"):
                provided = request.headers.get("x-api-token", "")
                if not hmac.compare_digest(provided.encode("utf-8"), token.encode("utf-8")):
                    return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        return await call_next(request)

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(request: Request, exc: RequestValidationError):
        errors = []
        for error in exc.errors():
            item = dict(error)
            if "ctx" in item and "error" in item["ctx"]:
                item["ctx"] = dict(item["ctx"])
                item["ctx"]["error"] = str(item["ctx"]["error"])
            errors.append(item)
        return JSONResponse(status_code=422, content={"detail": _json_safe(jsonable_encoder(errors))})

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    setup_observability(app)

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
