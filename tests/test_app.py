from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

from src.query import (
    GenerationError,
    QueryConfigurationError,
    RetrievalExecutionError,
    RetrievalInitializationError,
)
from src.retrieval import QueryTooLongError


class FakeComponent:
    def __init__(self, *args: object, **kwargs: object) -> None:
        self.args = args
        self.kwargs = kwargs
        self.events: list[tuple[str, object, object, object]] = []

    def click(self, *, fn: object, inputs: object, outputs: object) -> None:
        self.events.append(("click", fn, inputs, outputs))

    def submit(self, *, fn: object, inputs: object, outputs: object) -> None:
        self.events.append(("submit", fn, inputs, outputs))


class FakeBlocks(FakeComponent):
    def __enter__(self) -> "FakeBlocks":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def queue(self) -> "FakeBlocks":
        return self

    def launch(self, **_: object) -> None:
        return None


def fake_gradio_module() -> ModuleType:
    module = ModuleType("gradio")
    module.components = []

    def component_factory(component_type: type[FakeComponent]):
        def build(*args: object, **kwargs: object) -> FakeComponent:
            component = component_type(*args, **kwargs)
            module.components.append(component)
            return component

        return build

    module.Blocks = component_factory(FakeBlocks)
    module.Markdown = component_factory(FakeComponent)
    module.Chatbot = component_factory(FakeComponent)
    module.Textbox = component_factory(FakeComponent)
    module.Button = component_factory(FakeComponent)
    return module


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fake_gradio = fake_gradio_module()
        sys.modules.pop("app", None)
        with patch.dict(sys.modules, {"gradio": cls.fake_gradio}):
            cls.app = importlib.import_module("app")

    def setUp(self) -> None:
        self.memory_directory = tempfile.TemporaryDirectory()
        self.memory_path = Path(self.memory_directory.name) / "memory.md"
        self.memory_patch = patch("src.query.MEMORY_PATH", self.memory_path)
        self.memory_patch.start()

    def tearDown(self) -> None:
        self.memory_patch.stop()
        self.memory_directory.cleanup()

    def test_chat_appends_question_and_answer_without_sending_history_to_retrieval(self) -> None:
        prior = [{"role": "user", "content": "Earlier question"}]
        with patch.object(
            self.app,
            "ask",
            return_value={"answer": "According to *organ*, supported.", "sources": ["organ.txt"]},
        ) as ask_mock:
            message, history = self.app.handle_chat("What is an organ?", prior)

        self.assertEqual(message, "")
        self.assertEqual(
            history,
            [
                *prior,
                {"role": "user", "content": "What is an organ?"},
                {"role": "assistant", "content": "According to *organ*, supported."},
            ],
        )
        ask_mock.assert_called_once_with("What is an organ?", debug=True)

    def test_completed_chat_appends_the_displayed_exchange_to_session_memory(self) -> None:
        with patch.object(
            self.app,
            "ask",
            return_value={"answer": "A supported answer.", "sources": ["organ.txt", "violin.txt"]},
        ):
            self.app.handle_chat("What is a coach-horn?", [])

        self.assertEqual(
            self.memory_path.read_text(encoding="utf-8"),
            "## Question\nWhat is a coach-horn?\n\n## Answer\nA supported answer.\n\n"
            "## Sources\n- organ.txt\n- violin.txt\n\n",
        )

    def test_empty_and_overlong_input_append_safe_assistant_messages(self) -> None:
        with patch.object(self.app, "ask") as ask_mock:
            _, empty_history = self.app.handle_chat("   ", [])
            _, overlong_history = self.app.handle_chat(
                "x" * (self.app.MAX_QUESTION_CHARACTERS + 1), []
            )

        self.assertEqual(empty_history, [{"role": "assistant", "content": "Please enter a question."}])
        self.assertEqual(
            overlong_history,
            [{"role": "assistant", "content": "Your question is too long. Please shorten it and try again."}],
        )
        ask_mock.assert_not_called()
        self.assertEqual(
            self.memory_path.read_text(encoding="utf-8"),
            "## Question\n   \n\n## Answer\nPlease enter a question.\n\n"
            f"## Question\n{'x' * (self.app.MAX_QUESTION_CHARACTERS + 1)}\n\n"
            "## Answer\nYour question is too long. Please shorten it and try again.\n\n",
        )

    def test_backend_errors_append_sanitized_assistant_messages(self) -> None:
        cases = [
            (QueryConfigurationError("secret"), "The answer service is not configured. Set GROQ_API_KEY and try again."),
            (RetrievalInitializationError("private"), "The document index is unavailable. Build the index and try again."),
            (RetrievalExecutionError("database"), "The document search failed. Please try again."),
            (QueryTooLongError("tokens"), "Your question is too long. Please shorten it and try again."),
            (GenerationError("provider secret"), "The answer service failed. Please try again."),
        ]
        for error, expected in cases:
            with self.subTest(error=type(error).__name__):
                with patch.object(self.app, "ask", side_effect=error):
                    _, history = self.app.handle_chat("Question", [])
                self.assertEqual(history[-1], {"role": "assistant", "content": expected})
                self.assertNotIn(str(error), history[-1]["content"])

    def test_chatbot_and_music_decorations_bind_submit_and_click_to_the_same_handler(self) -> None:
        markdown = next(component for component in self.fake_gradio.components if component.args)
        chat = next(
            component
            for component in self.fake_gradio.components
            if component.kwargs.get("label") == "Conversation"
        )
        question = next(
            component
            for component in self.fake_gradio.components
            if component.kwargs.get("label") == "Ask about music"
        )
        button = next(component for component in self.fake_gradio.components if component.args == ("♫ Ask",))

        self.assertIn("♫", markdown.args[0])
        self.assertNotIn("type", chat.kwargs)
        self.assertEqual(question.events[0][0:2], ("submit", self.app.handle_chat))
        self.assertEqual(button.events[0][0:2], ("click", self.app.handle_chat))
        self.assertEqual(question.events[0][2], [question, chat])
        self.assertEqual(button.events[0][2], [question, chat])
        self.assertEqual(question.events[0][3], [question, chat])
        self.assertEqual(button.events[0][3], [question, chat])


if __name__ == "__main__":
    unittest.main()
