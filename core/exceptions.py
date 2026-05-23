from __future__ import annotations


class SchedulerError(RuntimeError):
    """Base error for scheduling pipeline failures."""


class ConfigurationError(SchedulerError):
    """Raised when required runtime configuration is missing or invalid."""


class LLMProviderError(SchedulerError):
    """Raised when an LLM provider call fails or returns invalid data."""


class ReplayConflictError(SchedulerError):
    """Raised when an idempotency key is reused for a different request."""
