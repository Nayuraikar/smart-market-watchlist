import uuid
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


def _error_body(code: str, message: str, request_id: str) -> dict:
    return {"error": {"code": code, "message": message, "request_id": request_id}}


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = str(uuid.uuid4())

    # if the raiser already gave us a structured {"error": {...}} body (like get_current_user does),
    # respect it but stamp a fresh request_id rather than trusting a None placeholder
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        body = exc.detail
        body["error"]["request_id"] = request_id
    else:
        body = _error_body(code="HTTP_ERROR", message=str(exc.detail), request_id=request_id)

    return JSONResponse(status_code=exc.status_code, content=body)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = str(uuid.uuid4())
    first_error = exc.errors()[0] if exc.errors() else {}
    message = first_error.get("msg", "Validation failed")
    return JSONResponse(
        status_code=422,
        content=_error_body(code="VALIDATION_ERROR", message=message, request_id=request_id),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = str(uuid.uuid4())
    # never leak internal exception details (str(exc)) to the client — log server-side only
    print(f"[UNHANDLED ERROR] request_id={request_id} error={exc!r}")
    return JSONResponse(
        status_code=500,
        content=_error_body(code="INTERNAL_ERROR", message="An unexpected error occurred", request_id=request_id),
    )


def register_exception_handlers(app):
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
