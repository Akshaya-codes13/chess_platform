from fastapi import Request, status
from fastapi.responses import JSONResponse


class ServiceError(Exception):
    """A business-rule failure raised by a service, mapped to an HTTP error.

    Services raise these instead of ``HTTPException`` so they stay usable
    outside a request; the handler in ``app.main`` turns them into responses
    shaped like FastAPI's own errors: ``{"detail": "..."}``.
    """

    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class NotFoundError(ServiceError):
    # Also used for resources owned by another trainer, so their existence
    # is not revealed.
    status_code = status.HTTP_404_NOT_FOUND


class PermissionDeniedError(ServiceError):
    status_code = status.HTTP_403_FORBIDDEN


class ConflictError(ServiceError):
    status_code = status.HTTP_409_CONFLICT


class ValidationError(ServiceError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT


async def service_error_handler(request: Request, exc: ServiceError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )
