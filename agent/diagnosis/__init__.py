"""Deterministic, keyless run diagnosis (Mile 1-A·demo).

Every fired trigger is explained; checker silence under a trigger produces
unknown_gap, never nothing. No LLM anywhere in this path.
"""

from .diagnosis import install_subscriber, smoke_check  # noqa: F401
