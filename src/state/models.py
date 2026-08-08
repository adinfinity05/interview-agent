from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum


class InterviewState(str, Enum):
    """Explicit interview phases."""
    START = "START"
    GREETING = "GREETING"
    QUESTIONING = "QUESTIONING"
    FOLLOW_UP = "FOLLOW_UP"
    CLOSING = "CLOSING"
    FEEDBACK = "FEEDBACK"


@dataclass
class QuestionRecord:
    """Stores a single question-answer pair with metadata."""
    question: str
    answer: str
    topic: str
    is_follow_up: bool = False


@dataclass
class InterviewSession:
    """In-memory session state for an interview."""
    session_id: str
    candidate: Optional[dict] = None
    current_state: InterviewState = InterviewState.START
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    questions_asked: List[QuestionRecord] = field(default_factory=list)
    topics_covered: Dict[str, int] = field(default_factory=dict)
    question_count: int = 0
    is_complete: bool = False
    pending_topic: Optional[str] = None
    topic_queue: List[Dict[str, Any]] = field(default_factory=list)
    current_topic: Optional[Dict[str, Any]] = None

    def add_question(self, question: str, answer: str, topic: str, is_follow_up: bool = False) -> None:
        """Helper to add a question and update topic coverage.
        Note: conversation_history is managed by process_turn — only append Q here."""
        record = QuestionRecord(question, answer, topic, is_follow_up)
        self.questions_asked.append(record)
        self.question_count += 1
        self.topics_covered[topic] = self.topics_covered.get(topic, 0) + 1

    def get_topics_covered_count(self) -> int:
        """Number of distinct topics covered."""
        return len(self.topics_covered)

    def meets_requirements(self, min_questions: int = 8, min_topics: int = 4) -> bool:
        """Check if we've asked enough questions across enough topics."""
        return self.question_count >= min_questions and self.get_topics_covered_count() >= min_topics