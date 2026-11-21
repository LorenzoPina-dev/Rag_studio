"""Core exceptions for RAG STUDIO backend."""


class RagStudioError(Exception):
    """Base application error."""


class NotFoundError(RagStudioError):
    """Requested entity was not found."""


class ValidationFailedError(RagStudioError):
    """Domain/graph validation failed."""


class ConflictError(RagStudioError):
    """Operation conflicts with current state."""


class ProviderError(RagStudioError):
    """External/provider adapter error."""


class ExecutionError(RagStudioError):
    """Execution/runtime error."""
