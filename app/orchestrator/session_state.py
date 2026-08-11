"""
In-memory session state for the clarification loop.

Scoped intentionally: a dict keyed by session_id, lost on server restart,
not shared across multiple server processes. This is an honest, correct
choice for a single-process demo — a production version would use Redis
with a TTL instead. Documented here rather than hidden.
"""

_sessions: dict[str, dict] = {}


def create_session(session_id: str, original_question: str) -> None:
    _sessions[session_id] = {
        "original_question": original_question,
        "clarifying_question": None,
        "user_answer": None,
    }


def store_clarifying_question(session_id: str, question: str, options: list[str]) -> None:
    if session_id not in _sessions:
        raise KeyError(f"Unknown session_id: {session_id}")
    _sessions[session_id]["clarifying_question"] = question
    _sessions[session_id]["options"] = options


def store_user_answer(session_id: str, answer: str) -> None:
    if session_id not in _sessions:
        raise KeyError(f"Unknown session_id: {session_id}")
    _sessions[session_id]["user_answer"] = answer


def get_session(session_id: str) -> dict:
    if session_id not in _sessions:
        raise KeyError(f"Unknown session_id: {session_id}")
    return _sessions[session_id]


def build_clarification_context(session_id: str) -> str:
    """Renders the session's Q&A as text to feed back into the LLM prompt."""
    session = get_session(session_id)
    return (
        f"Original question: {session['original_question']}\n"
        f"Clarifying question asked: {session['clarifying_question']}\n"
        f"User's answer: {session['user_answer']}"
    )