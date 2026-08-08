"""
FastAPI route handlers for the interview agent.
"""

from fastapi import APIRouter, HTTPException, status
from src.schemas.models import InterviewRequest, InterviewResponse
from src.services.interview_service import InterviewService
from src.state.store import session_store


router = APIRouter(prefix="/api", tags=["interview"])


@router.post("/interview", response_model=InterviewResponse)
async def interview_endpoint(request: InterviewRequest):
    """
    Single endpoint for starting and continuing interviews.

    - First request must include `candidate` object.
    - Subsequent requests must include `message` string.
    - Returns the agent's reply, a `done` flag, and optional feedback when complete.
    """
    session_id = request.sessionId

    # Check if this is a new session (has candidate) or existing (has message)
    if request.candidate is not None:
        # START: Initialize a new interview
        # Check if session already exists
        if await session_store.session_exists(session_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Session {session_id} already exists. Use message to continue."
            )

        # Start the interview
        session, greeting = await InterviewService.start_interview(
            session_id=session_id,
            candidate_data=request.candidate.model_dump()
        )

        return InterviewResponse(
            reply=greeting,
            done=False,
            feedback=None
        )

    elif request.message is not None:
        # TURN: Process a candidate message in an existing session
        # Check if session exists
        if not await session_store.session_exists(session_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found. Start a new interview with candidate data."
            )

        # Process the turn
        session, response_data = await InterviewService.process_turn(
            session_id=session_id,
            user_message=request.message
        )

        # Build response
        return InterviewResponse(
            reply=response_data["reply"],
            done=response_data["done"],
            feedback=response_data.get("feedback")
        )

    else:
        # Should never happen due to Pydantic validation, but just in case
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request must contain either 'candidate' (for start) or 'message' (for turn)."
        )