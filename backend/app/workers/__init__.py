"""Worker/runtime infrastructure package."""

try:
    from .celery_app import celery_app, get_celery_app
except Exception:  # pragma: no cover - optional dependency/runtime
    celery_app = None  # type: ignore[assignment]

    def get_celery_app():  # type: ignore[no-redef]
        raise RuntimeError("Celery is not available in this environment")

__all__ = ["celery_app", "get_celery_app"]
