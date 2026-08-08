"""
AI and retrieval interfaces for the Interview Agent.

Provides question generation, answer evaluation, and feedback generation
using Groq (free tier), grounded in curriculum retrieval.
"""

import os
import json
from typing import List, Dict, Any, Optional
from pathlib import Path

from groq import AsyncGroq

_client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY", ""))
MODEL = "llama-3.3-70b-versatile"

_curriculum_data = None


def _load_curriculum() -> dict:
    """Load curriculum.json once and cache it."""
    global _curriculum_data
    if _curriculum_data is None:
        path = Path(__file__).parent.parent.parent / "curriculum.json"
        with open(path) as f:
            _curriculum_data = json.load(f)
    return _curriculum_data


def build_candidate_context(profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a structured candidate context from a raw candidate profile.

    Returns a dict with name, job_role, years_experience, education,
    strong_days, weak_days, skipped_days, gap_days, and a summary_string
    suitable for injection into prompts.
    """
    member = profile.get("member", {})
    missions = profile.get("missions", [])
    signals = profile.get("signals", {})

    name = member.get("name", "Candidate")
    job_role = member.get("jobRole", "Unknown")
    years_experience = member.get("yearsExperience", 0)
    education = member.get("education", "Unknown")

    strong_days = []
    weak_days = []
    skipped_days = []
    failed_days = []

    for m in missions:
        day = m.get("day")
        if m.get("skipped"):
            skipped_days.append(day)
        elif not m.get("passed", False):
            failed_days.append(day)
        elif m.get("attempts", 1) <= 2:
            strong_days.append(day)
        elif m.get("attempts", 1) >= 4:
            weak_days.append(day)

    summary = (
        f"{name} is a {job_role} with {years_experience} years of experience. "
        f"Education: {education}. "
    )
    if strong_days:
        summary += f"They confidently completed days {strong_days} on the first try. "
    if weak_days:
        summary += f"They struggled with days {weak_days} (multiple attempts). "
    if skipped_days:
        summary += f"They skipped days {skipped_days}. "
    if failed_days:
        summary += f"They failed days {failed_days}."

    return {
        "name": name,
        "job_role": job_role,
        "years_experience": years_experience,
        "education": education,
        "strong_days": strong_days,
        "weak_days": weak_days,
        "skipped_days": skipped_days,
        "failed_days": failed_days,
        "summary_string": summary,
    }


def select_topics(
    candidate: Dict[str, Any],
    target_count: int = 5
) -> List[Dict[str, Any]]:
    """
    Select interview topics based on candidate's mission history.

    Returns topics sorted confident-first (easy wins → weak areas).
    Skipped/failed missions are excluded (not ambushed in interview).
    """
    curriculum = _load_curriculum()
    missions = candidate.get("missions", [])

    topic_pool = []
    for m in missions:
        if m.get("skipped") or not m.get("passed", False):
            continue
        topic_pool.append({
            "day": m["day"],
            "title": m["title"],
            "attempts": m.get("attempts", 1),
        })

    topic_pool.sort(key=lambda x: x["attempts"])

    selected = []
    for t in topic_pool[:target_count]:
        for day in curriculum.get("days", []):
            if day["day"] == t["day"]:
                selected.append({
                    "day": t["day"],
                    "title": t["title"],
                    "attempts": t["attempts"],
                    "objectives": day.get("objectives", []),
                    "tools": day.get("tools", []),
                })
                break

    return selected


async def retrieve(topic: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """
    Retrieve relevant curriculum content for a topic.
    """
    curriculum = _load_curriculum()
    matches = []
    for day in curriculum.get("days", []):
        if topic.lower() in day.get("title", "").lower():
            objectives = "\n".join(f"- {o}" for o in day.get("objectives", []))
            tools = ", ".join(day.get("tools", []))
            matches.append({
                "text": (
                    f"Day {day['day']}: {day['title']}\n"
                    f"Type: {day.get('type', 'N/A')}\n"
                    f"Tools: {tools}\n"
                    f"Objectives:\n{objectives}"
                ),
                "metadata": {"day": day["day"], "type": day.get("type", "")}
            })
    if matches:
        return matches[:top_k]
    return [{"text": f"Curriculum content for {topic}", "metadata": {}}]


async def open_topic(
    topic: Dict[str, Any],
    candidate_profile: Dict[str, Any],
    conversation_history: List[Dict[str, str]]
) -> str:
    """
    Generate the first question for a new topic.
    """
    try:
        ctx = build_candidate_context(candidate_profile)
        objectives = "\n".join(f"- {o}" for o in topic.get("objectives", []))
        tools = ", ".join(topic.get("tools", []))

        recent = conversation_history[-6:] if conversation_history else []
        history_text = "\n".join(f"{m['role']}: {m['content']}" for m in recent)

        system_prompt = (
            "You are Alex, a senior technical interviewer. You are warm but probing. "
            "Ask ONE question at a time. Never number your questions. "
            "Reference the candidate's experience when relevant. "
            "Do not give hints or答案. If the candidate says 'I don't know', "
            "gracefully pivot to a simpler angle on the same topic."
        )

        user_prompt = (
            f"Candidate: {ctx['summary_string']}\n\n"
            f"Topic: Day {topic['day']} — {topic['title']}\n"
            f"Tools: {tools}\n"
            f"Curriculum objectives:\n{objectives}\n\n"
            f"Recent conversation:\n{history_text}\n\n"
            f"Generate the opening question for this topic. Return ONLY the question text."
        )

        response = await _client.chat.completions.create(
            model=MODEL,
            max_tokens=256,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
        )
        question = response.choices[0].message.content.strip()
        return question if question else f"Tell me about your experience with {topic['title']}."
    except Exception:
        return f"Tell me about your experience with {topic['title']}."


async def generate_followup(
    topic: Dict[str, Any],
    candidate_answer: str,
    conversation_history: List[Dict[str, str]]
) -> str:
    """
    Generate a follow-up question based on the candidate's answer.
    """
    try:
        recent = conversation_history[-8:] if conversation_history else []
        history_text = "\n".join(f"{m['role']}: {m['content']}" for m in recent)

        system_prompt = (
            "You are Alex, a senior technical interviewer. "
            "Generate a follow-up question to probe deeper into the candidate's answer. "
            "Be specific — reference something they said. "
            "Do not repeat the same question. One question only."
        )

        user_prompt = (
            f"Topic: {topic['title']}\n"
            f"Candidate's last answer: {candidate_answer}\n\n"
            f"Conversation so far:\n{history_text}\n\n"
            "Generate a follow-up question. Return ONLY the question text."
        )

        response = await _client.chat.completions.create(
            model=MODEL,
            max_tokens=256,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
        )
        question = response.choices[0].message.content.strip()
        return question if question else "Can you elaborate on that?"
    except Exception:
        return "Can you elaborate on that?"


async def classify_answer(
    question: str,
    answer: str,
    topic: Dict[str, Any]
) -> str:
    """
    Classify the candidate's answer into:
      A — answer was shallow, needs follow-up
      B — answer was solid, move to next topic
      C — candidate is confused, pivot to simpler angle
    """
    try:
        system_prompt = (
            "You are evaluating a candidate's interview answer. "
            "Classify it as exactly ONE letter:\n"
            "A — answer is shallow or incomplete, needs a follow-up question\n"
            "B — answer is solid and demonstrates understanding, move on\n"
            "C — candidate is confused or doesn't know, pivot to simpler angle\n\n"
            "Return ONLY the letter A, B, or C. Nothing else."
        )

        user_prompt = (
            f"Topic: {topic['title']}\n"
            f"Question: {question}\n"
            f"Candidate answer: {answer}\n\n"
            "Classify this answer. Return ONLY A, B, or C."
        )

        response = await _client.chat.completions.create(
            model=MODEL,
            max_tokens=8,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
        )
        verdict = response.choices[0].message.content.strip().upper()
        return verdict if verdict in ("A", "B", "C") else "B"
    except Exception:
        return "B"


async def evaluate_answer(
    question: str,
    answer: str,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Evaluate the candidate's answer to a question.
    Returns a dict with score, feedback, follow_up_needed, follow_up_question.
    """
    try:
        history = context.get("conversation_history", [])
        history_text = "\n".join(
            f"{m['role']}: {m['content']}" for m in history[-10:]
        )

        system_prompt = (
            "You are a technical interviewer evaluating a candidate's answer. "
            "Score from 0 to 10 based on depth, accuracy, and practical understanding. "
            "Decide if a follow-up question is needed to probe deeper.\n\n"
            "Return ONLY a JSON object with exactly these keys:\n"
            '{"score": <float 0-10>, "feedback": "<brief string>", '
            '"follow_up_needed": <bool>, "follow_up_question": <string or null>}\n\n'
            "Rules:\n"
            "- follow_up_question MUST be a non-null string if follow_up_needed is true.\n"
            "- Keep feedback under 2 sentences.\n"
            "- Do NOT include anything outside the JSON object."
        )

        user_prompt = (
            f"Question: {question}\n\n"
            f"Candidate answer: {answer}\n\n"
            f"Recent conversation:\n{history_text}\n\n"
            "Evaluate this answer. Return ONLY the JSON object."
        )

        response = await _client.chat.completions.create(
            model=MODEL,
            max_tokens=300,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
        )

        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        result = json.loads(raw)

        score = float(result.get("score", 5.0))
        score = max(0.0, min(10.0, score))
        follow_up = bool(result.get("follow_up_needed", False))
        follow_up_q = result.get("follow_up_question") if follow_up else None

        return {
            "score": score,
            "feedback": str(result.get("feedback", "")),
            "follow_up_needed": follow_up,
            "follow_up_question": follow_up_q,
        }
    except Exception:
        return {
            "score": 5.0,
            "feedback": "Unable to evaluate.",
            "follow_up_needed": False,
            "follow_up_question": None,
        }


async def generate_feedback(
    questions_asked: List[Dict[str, Any]],
    candidate_profile: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate structured feedback for the entire interview.
    Returns summary, strengths, gaps, next.
    """
    try:
        ctx = build_candidate_context(candidate_profile)

        qa_log = []
        for i, q in enumerate(questions_asked, 1):
            tag = " [follow-up]" if q.get("is_follow_up") else ""
            qa_log.append(
                f"Q{i} (topic: {q.get('topic', 'N/A')}{tag}):\n"
                f"  Question: {q.get('question', '')}\n"
                f"  Answer: {q.get('answer', '')}"
            )
        qa_text = "\n\n".join(qa_log)

        system_prompt = (
            "You are a senior technical interviewer generating final interview feedback. "
            "Be specific — reference actual topics and curriculum days. "
            "Return ONLY a JSON object with exactly these keys:\n"
            '{"summary": "<2-4 sentence overview>", '
            '"strengths": ["<specific strength>", ...], '
            '"gaps": ["<specific gap with day references>", ...], '
            '"next": ["<actionable next step>", ...]}\n\n'
            "Rules:\n"
            "- Summary must be an objective assessment of overall performance.\n"
            "- Strengths and gaps must reference specific curriculum topics or days.\n"
            "- 'next' must contain 2-4 actionable recommendations with day references.\n"
            "- Do NOT include anything outside the JSON object."
        )

        user_prompt = (
            f"Candidate: {ctx['summary_string']}\n\n"
            f"Questions and answers:\n{qa_text}\n\n"
            "Generate structured interview feedback. Return ONLY the JSON object."
        )

        response = await _client.chat.completions.create(
            model=MODEL,
            max_tokens=600,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
        )

        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        result = json.loads(raw)

        return {
            "summary": str(result.get("summary", "Interview complete.")),
            "strengths": list(result.get("strengths", [])),
            "gaps": list(result.get("gaps", [])),
            "next": list(result.get("next", [])),
        }
    except Exception:
        return {
            "summary": "Interview complete.",
            "strengths": [],
            "gaps": [],
            "next": [],
        }
