from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
