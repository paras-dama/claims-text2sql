import requests
import streamlit as st

API_BASE_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="Claims Text-to-SQL", page_icon="📋", layout="wide")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_clarification" not in st.session_state:
    st.session_state.pending_clarification = None

with st.sidebar:
    st.title("📋 Claims Text-to-SQL")
    st.caption("Ask questions about claims and reserves data.")
    provider = st.selectbox(
        "LLM Provider",
        options=["groq", "gemini", "openai"],
        index=0,
    )
    st.divider()
    if st.button("Clear conversation"):
        st.session_state.messages = []
        st.session_state.pending_clarification = None
        st.rerun()

def call_query_api(question: str, provider: str) -> dict:
    response = requests.post(
        f"{API_BASE_URL}/query",
        json={"question": question, "provider": provider},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def call_clarify_api(session_id: str, answer: str, provider: str) -> dict:
    response = requests.post(
        f"{API_BASE_URL}/clarify",
        json={"session_id": session_id, "answer": answer, "provider": provider},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()

def render_result(result: dict):
    if result["status"] == "ready":
        st.markdown(result["explanation"]["summary"])

        if result["explanation"]["assumptions_stated"]:
            with st.expander("Assumptions made"):
                for a in result["explanation"]["assumptions_stated"]:
                    st.markdown(f"- {a}")

        if result["explanation"]["caveats"]:
            for c in result["explanation"]["caveats"]:
                st.info(c)

        with st.expander("View SQL and raw results"):
            st.code(result["generated_sql"], language="sql")
            if result["rows"]:
                st.dataframe(result["rows"])
            else:
                st.caption("No rows returned.")
            if result["truncated"]:
                st.caption(f"Results truncated to {result['row_count']} rows.")

    elif result["status"] == "still_ambiguous":
        st.warning(
            "Still unclear even after clarification. "
            f"{result['reasoning']}"
        )

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant" and "result" in msg:
            render_result(msg["result"])
        else:
            st.markdown(msg["content"])

if st.session_state.pending_clarification:
    clar = st.session_state.pending_clarification
    with st.chat_message("assistant"):
        st.markdown(f"**{clar['clarifying_question']}**")
        cols = st.columns(len(clar["options"]))
        for i, option in enumerate(clar["options"]):
            if cols[i].button(option, key=f"clar_option_{i}"):
                st.session_state.messages.append(
                    {"role": "user", "content": f"(chose) {option}"}
                )
                with st.spinner("Applying your answer..."):
                    result = call_clarify_api(
                        clar["session_id"], option, provider
                    )
                st.session_state.messages.append(
                    {"role": "assistant", "content": "", "result": result}
                )
                st.session_state.pending_clarification = None
                st.rerun()

question = st.chat_input("Ask a question about claims or reserves...")

if question:
    st.session_state.messages.append({"role": "user", "content": question})

    with st.spinner("Thinking..."):
        try:
            result = call_query_api(question, provider)
        except requests.exceptions.RequestException as e:
            st.session_state.messages.append(
                {"role": "assistant", "content": f"Error calling API: {e}"}
            )
            st.rerun()

    if result["status"] == "needs_clarification":
        st.session_state.pending_clarification = {
            "session_id": result["session_id"],
            "clarifying_question": result["clarifying_question"],
            "options": result["options"],
        }
        st.session_state.messages.append(
            {"role": "assistant", "content": "I need a bit more information."}
        )
    else:
        st.session_state.messages.append(
            {"role": "assistant", "content": "", "result": result}
        )

    st.rerun()