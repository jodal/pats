import uvicorn

from pats import settings


uvicorn.run(
    "pats.app:app", host="0.0.0.0", port=settings.PORT, reload=settings.DEBUG
)
