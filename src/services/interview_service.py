"""
Interview service orchestrates the conversation flow, state transitions,
and integration with AI/retrieval functions.
"""

from typing import Dict, Any, Tuple, List
from src.state.models import InterviewState, InterviewSession
from src.state.store import session_store
from src.core import interfaces


class InterviewService:
    """Handles the interview lifecycle and state transitions."""

    @staticmethod
    async def start_interview(session_id: str, candidate_data: Dict[str, Any]) -> Tuple[InterviewSession, str]:
        """
        Initialize a new interview session and return the greeting.
        """
        session = await session_store.create_session(session_id, candidate_data)

        session.current_state = InterviewState.GREETING

        greeting = await InterviewService._generate_greeting(candidate_data)
        session.conversation_history.append({"role": "assistant", "content": greeting})

        topic_queue = interfaces.select_topics(candidate_data, target_count=5)
        session.topic_queue = topic_queue

        await session_store.update_session(session)
        return session, greeting

    @staticmethod
    async def process_turn(session_id: str, user_message: str) -> Tuple[InterviewSession, Dict[str, Any]]:
        """
        Process a user's message and transition the interview state.
        """
        session = await session_store.get_session(session_id)

        session.conversation_history.append({"role": "user", "content": user_message})

        if session.current_state == InterviewState.GREETING:
            reply, next_state = await InterviewService._handle_greeting(session, user_message)
        elif session.current_state == InterviewState.QUESTIONING:
            reply, next_state, *extra = await InterviewService._handle_questioning(session, user_message)
            extra_val = extra[0] if extra else None
        elif session.current_state == InterviewState.FOLLOW_UP:
            reply, next_state, *extra = await InterviewService._handle_follow_up(session, user_message)
            extra_val = extra[0] if extra else None
        elif session.current_state == InterviewState.CLOSING:
            reply, next_state = await InterviewService._handle_closing(session, user_message)
            extra_val = None
        else:
            reply = "I'm sorry, something went wrong. Let's reset."
            next_state = InterviewState.START
            extra_val = None

        session.current_state = next_state

        response: Dict[str, Any] = {"reply": reply, "done": False}

        if next_state == InterviewState.FEEDBACK:
            feedback_data = await interfaces.generate_feedback(
                questions_asked=[q.__dict__ for q in session.questions_asked],
                candidate_profile=session.candidate
            )
            response["done"] = True
            response["feedback"] = feedback_data
            session.is_complete = True

        session.conversation_history.append({"role": "assistant", "content": reply})
        await session_store.update_session(session)

        return session, response

    @staticmethod
    async def _generate_greeting(candidate_data: Dict[str, Any]) -> str:
        name = candidate_data.get("member", {}).get("name", "Candidate")
        return f"Hello {name}! Welcome to your technical interview. Let's begin."

    @staticmethod
    async def _handle_greeting(session: InterviewSession, user_message: str) -> Tuple[str, InterviewState]:
        topic_queue = getattr(session, "topic_queue", [])
        if not topic_queue:
            topic_queue = interfaces.select_topics(session.candidate, target_count=5)
            session.topic_queue = topic_queue

        first_topic = topic_queue[0] if topic_queue else {"day": 7, "title": "Embeddings Explained", "objectives": [], "tools": []}
        session.current_topic = first_topic

        question = await interfaces.open_topic(
            topic=first_topic,
            candidate_profile=session.candidate,
            conversation_history=session.conversation_history
        )
        return question, InterviewState.QUESTIONING

    @staticmethod
    async def _handle_questioning(session: InterviewSession, user_message: str):
        last_question = ""
        for msg in reversed(session.conversation_history):
            if msg["role"] == "assistant":
                last_question = msg["content"]
                break

        topic = getattr(session, "current_topic", {"title": "General", "day": 0, "objectives": [], "tools": []})

        verdict = await interfaces.classify_answer(
            question=last_question,
            answer=user_message,
            topic=topic
        )

        session.add_question(
            question=last_question,
            answer=user_message,
            topic=topic.get("title", "General"),
            is_follow_up=False
        )

        if verdict == "A":
            follow_up = await interfaces.generate_followup(
                topic=topic,
                candidate_answer=user_message,
                conversation_history=session.conversation_history
            )
            return follow_up, InterviewState.FOLLOW_UP

        topic_queue = getattr(session, "topic_queue", [])
        if topic_queue:
            topic_queue.pop(0)

        if session.meets_requirements(min_questions=8, min_topics=4) or not topic_queue:
            closing = "We've covered enough ground. Let me wrap up the interview."
            return closing, InterviewState.CLOSING

        next_topic = topic_queue[0]
        session.current_topic = next_topic

        next_question = await interfaces.open_topic(
            topic=next_topic,
            candidate_profile=session.candidate,
            conversation_history=session.conversation_history
        )
        return next_question, InterviewState.QUESTIONING

    @staticmethod
    async def _handle_follow_up(session: InterviewSession, user_message: str):
        last_question = ""
        for msg in reversed(session.conversation_history):
            if msg["role"] == "assistant":
                last_question = msg["content"]
                break

        topic = getattr(session, "current_topic", {"title": "General", "day": 0, "objectives": [], "tools": []})

        session.add_question(
            question=last_question,
            answer=user_message,
            topic=topic.get("title", "General"),
            is_follow_up=True
        )

        topic_queue = getattr(session, "topic_queue", [])
        if session.meets_requirements(min_questions=8, min_topics=4) or not topic_queue:
            closing = "We've covered enough ground. Let me wrap up the interview."
            return closing, InterviewState.CLOSING

        if topic_queue:
            topic_queue.pop(0)

        next_topic = topic_queue[0] if topic_queue else {"title": "General", "day": 0, "objectives": [], "tools": []}
        session.current_topic = next_topic

        next_question = await interfaces.open_topic(
            topic=next_topic,
            candidate_profile=session.candidate,
            conversation_history=session.conversation_history
        )
        return next_question, InterviewState.QUESTIONING

    @staticmethod
    async def _handle_closing(session: InterviewSession, user_message: str) -> Tuple[str, InterviewState]:
        return "Thank you. Now generating your feedback.", InterviewState.FEEDBACK
