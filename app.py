"""Local chat interface for the grounded music-knowledge RAG pipeline."""

from __future__ import annotations

from typing import Any

import gradio as gr

from src.query import (
    GenerationError,
    QueryConfigurationError,
    RetrievalExecutionError,
    RetrievalInitializationError,
    ask,
)
from src.retrieval import QueryTooLongError


MAX_QUESTION_CHARACTERS = 4_000


def _error_message(error: Exception) -> str:
    if isinstance(error, QueryTooLongError):
        return "Your question is too long. Please shorten it and try again."
    if isinstance(error, QueryConfigurationError):
        return "The answer service is not configured. Set GROQ_API_KEY and try again."
    if isinstance(error, RetrievalInitializationError):
        return "The document index is unavailable. Build the index and try again."
    if isinstance(error, RetrievalExecutionError):
        return "The document search failed. Please try again."
    if isinstance(error, GenerationError):
        return "The answer service failed. Please try again."
    return "Something went wrong. Please try again."


def handle_chat(question: str, history: list[dict[str, Any]] | None) -> tuple[str, list[dict[str, str]]]:
    """Append one independent grounded exchange to the visible chat history."""
    messages: list[dict[str, str]] = list(history or [])
    if not isinstance(question, str) or not question.strip():
        messages.append({"role": "assistant", "content": "Please enter a question."})
        return "", messages
    if len(question) > MAX_QUESTION_CHARACTERS:
        messages.append(
            {
                "role": "assistant",
                "content": "Your question is too long. Please shorten it and try again.",
            }
        )
        return "", messages

    try:
        result = ask(question, debug=True)
        answer = result["answer"]
    except Exception as error:
        answer = _error_message(error)
    messages.extend(
        (
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        )
    )
    return "", messages


def create_demo() -> gr.Blocks:
    """Build the local chat interface."""
    with gr.Blocks(title="♫ Music Knowledge Guide") as demo:
        gr.Markdown("# ♫ Music Knowledge Guide\n*Grounded answers from the indexed music library.*")
        chat = gr.Chatbot(label="Conversation", height=520)
        question = gr.Textbox(
            label="Ask about music",
            placeholder="Ask about the indexed instruments, history, or techniques… ♪",
            lines=2,
            max_lines=6,
        )
        ask_button = gr.Button("♫ Ask", variant="primary")
        outputs = [question, chat]
        question.submit(fn=handle_chat, inputs=[question, chat], outputs=outputs)
        ask_button.click(fn=handle_chat, inputs=[question, chat], outputs=outputs)
        gr.Markdown("♪ Each answer is grounded in retrieved historical documents.")
    return demo


demo = create_demo()


if __name__ == "__main__":
    demo.queue().launch(show_error=False)
