from typing import List, Optional, Literal
from pydantic import BaseModel, Field, model_validator
from enum import Enum

# --- Candidate-related models (matching candidates.json) ---

class Member(BaseModel):
    id: str
    name: str
    jobRole: str
    yearsExperience: int
    education: str
    status: str  # e.g., "COMPLETED"

class Mission(BaseModel):
    day: int
    title: str
    passed: bool
    attempts: int
    skipped: Optional[bool] = None  # 'skipped' may be absent

class Signals(BaseModel):
    commitDays: int
    missionsCompleted: int
    missionsFirstTry: int

class Candidate(BaseModel):
    member: Member
    missions: List[Mission]
    signals: Signals

# --- Request Models ---

class InterviewRequest(BaseModel):
    sessionId: str
    candidate: Optional[Candidate] = None
    message: Optional[str] = None

    @model_validator(mode='after')
    def check_start_or_turn(self) -> 'InterviewRequest':
        # Exactly one of candidate or message must be present
        has_candidate = self.candidate is not None
        has_message = self.message is not None
        if has_candidate == has_message:
            raise ValueError(
                "Request must contain either 'candidate' (for start) or 'message' (for turn), but not both."
            )
        return self

# --- Response Models ---

class Feedback(BaseModel):
    summary: str
    strengths: List[str]
    gaps: List[str]
    next: List[str]

class InterviewResponse(BaseModel):
    reply: str
    done: bool
    feedback: Optional[Feedback] = None

    @model_validator(mode='after')
    def feedback_required_if_done(self) -> 'InterviewResponse':
        if self.done and self.feedback is None:
            raise ValueError("When 'done' is True, 'feedback' must be provided.")
        return self