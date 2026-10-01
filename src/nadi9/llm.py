"""Model providers. Mock mode is the default and needs no API key."""

import json
import os

from nadi9.errors import LLMFailure


class MockLLM:
    """Returns a fixed proposal, including one rule the evidence does not support.

    The learner must reject that rule. The mock never writes a translation.
    """

    def __init__(self) -> None:
        self.last_prompt = ""

    def complete(self, prompt: str) -> str:
        self.last_prompt = prompt
        payload = {
            "proposals": [
                {
                    "id": "mock-sov",
                    "statement": "Word order is subject-object-verb.",
                    "confidence": 0.7,
                },
                {
                    "id": "mock-plural-zo",
                    "statement": "Every noun takes plural suffix -zo.",
                    "confidence": 0.99,
                },
            ]
        }
        return json.dumps(payload)


class LiveLLM:
    """Optional live provider. This demo refuses to call a network model."""

    def __init__(self) -> None:
        self.last_prompt = ""

    def complete(self, prompt: str) -> str:
        self.last_prompt = prompt
        if not os.environ.get("NADI9_API_KEY"):
            raise LLMFailure(
                "No NADI9_API_KEY is set. Re-run with --mode mock. "
                "Mock mode is the supported path for this project."
            )
        raise LLMFailure(
            "A live model is intentionally not called from this demo. "
            "Translations stay on the evidence path."
        )


def provider_for_mode(mode: str) -> MockLLM | LiveLLM:
    if mode == "live":
        return LiveLLM()
    if mode == "mock":
        return MockLLM()
    raise LLMFailure(f"Unknown mode: {mode}")
