# 🎙️ The Interview Agent

**AI-powered technical interview system for VICODATHON 2026**  
Conducts multi-turn technical interviews based on a candidate's progress through a 31-day AI cohort curriculum.

---

## 📖 Overview

The Interview Agent is a backend API that orchestrates intelligent, multi-turn technical interviews. It:

- Starts an interview with a candidate profile (from the cohort curriculum).
- Asks a minimum of **8 technical questions** across at least **4 curriculum topics**.
- Tracks conversation history, topic coverage, and question count.
- Detects when to ask follow-up questions.
- Generates structured feedback at the end of the interview.

The system uses a **state machine** (6 explicit states) and **in-memory session storage** (no database – exactly as specified).

---

## 🛠️ Tech Stack

- **FastAPI** – async web framework
- **Pydantic v2** – request/response validation
- **Uvicorn** – ASGI server
- **In-memory session store** – thread-safe with `asyncio.Lock`
- **Async architecture** – all AI/retrieval calls are `async`

---


## 🔁 State Machine

The interview follows this explicit state flow:
- **START** – Session initialized.
- **GREETING** – Welcome message sent.
- **QUESTIONING** – Ask main questions (minimum 8).
- **FOLLOW_UP** – Ask a follow-up question (if needed).
- **CLOSING** – Wrap up the interview.
- **FEEDBACK** – Generate structured feedback.



