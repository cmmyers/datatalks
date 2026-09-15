from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .routers.boards import router as boards_router

app = FastAPI(title="Hex Tracker API")
app.include_router(boards_router)


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
