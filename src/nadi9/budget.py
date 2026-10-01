"""Counts model calls and tool calls so a run cannot wander past the cap."""

from nadi9.errors import BudgetExceeded


class Budget:
    def __init__(self, max_model_calls: int = 25, max_tool_calls: int = 50) -> None:
        self.max_model_calls = max_model_calls
        self.max_tool_calls = max_tool_calls
        self.model_calls = 0
        self.tool_calls = 0

    def model(self, name: str) -> None:
        if self.model_calls >= self.max_model_calls:
            raise BudgetExceeded(f"model call budget exhausted before {name}")
        self.model_calls += 1

    def tool(self, name: str) -> None:
        if self.tool_calls >= self.max_tool_calls:
            raise BudgetExceeded(f"tool call budget exhausted before {name}")
        self.tool_calls += 1
