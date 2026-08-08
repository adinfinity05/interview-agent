"""
Custom exceptions and global exception handlers for the Interview Agent API.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


# --- Custom Exceptions ---

class InterviewError(Exception):
    """Base exception for interview-related errors."""
    pass


class SessionNotFoundError(InterviewError):
    """Raised when a session ID does not exist."""
    pass


class SessionAlreadyExistsError(InterviewError):
    """Raised when trying to create a session that already exists."""
    pass


class InvalidStateTransitionError(InterviewError):
    """Raised when an action is invalid for the current state."""
    pass


# --- Exception Handlers ---

def add_exception_handlers(app: FastAPI) -> None:
    """
    Register global exception handlers for the FastAPI app.
    """

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """Handle HTTP exceptions (e.g., 404, 400) with a clean JSON response."""
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail}
        )

    @app.exception_handler(InterviewError)
    async def interview_error_handler(request: Request, exc: InterviewError):
        """Handle custom interview errors."""
        status_code = status.HTTP_400_BAD_REQUEST
        if isinstance(exc, SessionNotFoundError):
            status_code = status.HTTP_404_NOT_FOUND
        elif isinstance(exc, SessionAlreadyExistsError):
            status_code = status.HTTP_409_CONFLICT

        return JSONResponse(
            status_code=status_code,
            content={"detail": str(exc)}
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        """Catch-all for unexpected errors (prevents stack trace leaks)."""
        # Log the error here in production
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An unexpected error occurred."}
        )