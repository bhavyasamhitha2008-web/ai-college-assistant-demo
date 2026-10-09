from pathlib import Path
from typing import Any, Protocol

from app.knowledge import retrieve_passage


INSUFFICIENT_INFORMATION = (
    "The available college documents do not provide enough information."
)


class LLMConfigurationError(RuntimeError):
    """Raised when the configured language model is unavailable."""


class LLMProviderError(RuntimeError):
    """Raised when a language model request fails."""


class PolicyModel(Protocol):
    def generate(self, question: str, context: str) -> str:
        """Generate an answer grounded only in the supplied policy context."""


class PolicySearchTool(Protocol):
    def search_policy(self, question: str) -> dict[str, Any]:
        """Return a retrieved policy passage and its source."""


def answer_policy_question(
    question: str,
    documents_dir: str | Path,
    model: PolicyModel | None = None,
    search_tool: PolicySearchTool | None = None,
) -> dict[str, object]:
    if search_tool is None:
        retrieved = retrieve_passage(question, documents_dir)
    else:
        retrieved = search_tool.search_policy(question)
    return answer_retrieved_policy(question, retrieved, model)


def answer_retrieved_policy(
    question: str,
    retrieved: dict[str, Any],
    model: PolicyModel | None = None,
) -> dict[str, object]:
    found = retrieved["found"]
    if not found:
        return {
            "found": False,
            "answer": INSUFFICIENT_INFORMATION,
            "source": None,
            "sources": [],
        }

    if model is None:
        from app.providers.openai_provider import OpenAIChatModel

        model = OpenAIChatModel.from_environment()

    answer = model.generate(question, str(retrieved["passage"])).strip()
    if not answer:
        raise ValueError("The policy model returned an empty answer.")

    source = str(retrieved["source"])
    return {
        "found": True,
        "answer": answer,
        "source": source,
        "sources": [{"document": source}],
    }
