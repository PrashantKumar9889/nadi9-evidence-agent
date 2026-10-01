"""Errors the pipeline is expected to catch and record."""


class NadiError(Exception):
    """Base error for this project."""


class ToolFailure(NadiError):
    """A retrieval, transcription, or validation tool could not finish."""


class LLMFailure(NadiError):
    """The language-model provider failed or is not configured."""


class BudgetExceeded(NadiError):
    """The run hit the model-call or tool-call cap."""


class DataError(NadiError):
    """The evidence pack is missing a file or is not valid JSON."""
