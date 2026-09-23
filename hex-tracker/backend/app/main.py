from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from .routers.boards import router as boards_router

app = FastAPI(title="Hex Tracker API")
app.include_router(boards_router)

# Vite's dev server picks a free port if its default is taken, so allow any
# localhost port rather than hardcoding one. No credentials are used (no
# auth — see docs/SPEC.md non-goals), so a wildcard-ish origin match is fine.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness check for orchestration (Docker Compose healthcheck, load
    balancer target health, CI/CD deploy verification) — infra concern, not
    part of the frontend-backend contract, so it's not in openapi.yaml."""
    return {"status": "ok"}


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Reshape FastAPI's default validation error into the {detail: string}
    shape declared in openapi.yaml's Error schema, instead of the default
    {detail: [...]} list of error objects."""
    message = "; ".join(
        f"{'.'.join(str(part) for part in error['loc'] if part != 'body')}: {error['msg']}"
        for error in exc.errors()
    )
    return JSONResponse(status_code=422, content={"detail": message})


# The production Docker image copies the frontend's built assets here (see
# Dockerfile); in local dev this directory doesn't exist, since the frontend
# runs separately under Vite, so serving it is skipped entirely.
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "static"

if FRONTEND_DIST.is_dir():

    def _spa_shell() -> FileResponse:
        response = FileResponse(FRONTEND_DIST / "index.html")
        # Vary: Accept is load-bearing, not decorative — GET /boards/{id} is
        # served two different ways from the exact same URL depending on
        # Accept (see the middleware below). Without this header, a
        # browser's HTTP cache has no reason to treat those as different
        # cache entries: the page-load response (HTML) gets cached and then
        # incorrectly reused for the app's own same-URL fetch() moments
        # later, which sends a different Accept and expects JSON back.
        response.headers["Vary"] = "Accept"
        return response

    class SpaFallbackMiddleware(BaseHTTPMiddleware):
        """The frontend's client-side router and the API share the same
        origin and, in one case, the same path shape: GET /boards/{id} is
        both "fetch this board's JSON" (API) and "render the board page"
        (frontend route). A real browser navigation — pasting/opening a
        shared board link, or reloading one — asks for that path with
        `Accept: text/html` and needs the app shell, not the JSON the API
        route would otherwise return for the exact same URL. A same-origin
        `fetch()` from the already-loaded app doesn't send that Accept
        value, so it still reaches the API normally. Runs before routing,
        so it pre-empts the API route entirely for page loads."""

        async def dispatch(self, request: Request, call_next) -> Response:
            if (
                request.method == "GET"
                and "text/html" in request.headers.get("accept", "")
                and not request.url.path.startswith("/assets")
            ):
                return _spa_shell()
            return await call_next(request)

    app.add_middleware(SpaFallbackMiddleware)
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str) -> FileResponse:
        """Catches whatever the middleware above doesn't: real static files
        at the dist root that aren't fetched as a page navigation, like
        /favicon.ico or /robots.txt. Falls back to index.html for anything
        else non-API that reaches this point."""
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return _spa_shell()
