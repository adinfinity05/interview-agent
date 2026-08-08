import asyncio
from typing import Dict, Optional
from src.state.models import InterviewSession
from src.api.errors import SessionNotFoundError, SessionAlreadyExistsError


class SessionStore:
    """Thread-safe in-memory store for interview sessions."""

    def __init__(self):
        self._sessions: Dict[str, InterviewSession] = {}
        self._lock = asyncio.Lock()

    async def create_session(self, session_id: str, candidate: dict) -> InterviewSession:
        """Create a new session with the given ID and candidate data."""
        async with self._lock:
            if session_id in self._sessions:
                raise SessionAlreadyExistsError(f"Session {session_id} already exists.")
            session = InterviewSession(session_id=session_id, candidate=candidate)
            self._sessions[session_id] = session
            return session

    async def get_session(self, session_id: str) -> InterviewSession:
        """Retrieve a session by ID. Raises SessionNotFoundError if not found."""
        async with self._lock:
            if session_id not in self._sessions:
                raise SessionNotFoundError(f"Session {session_id} not found.")
            return self._sessions[session_id]

    async def update_session(self, session: InterviewSession) -> None:
        """Update the store with a modified session object."""
        async with self._lock:
            if session.session_id not in self._sessions:
                raise SessionNotFoundError(f"Session {session.session_id} not found.")
            self._sessions[session.session_id] = session

    async def delete_session(self, session_id: str) -> bool:
        """Remove a session. Returns True if existed, False otherwise."""
        async with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    async def session_exists(self, session_id: str) -> bool:
        """Check if a session exists."""
        async with self._lock:
            return session_id in self._sessions


# Global singleton instance
session_store = SessionStore()