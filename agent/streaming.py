"""Streaming event handler protocol.

One class, sensible defaults. Override only what you need.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class StreamHandler(Protocol):
    """Handler for agent streaming events."""

    def on_text(self, text: str) -> None: ...
    def on_thinking(self, text: str) -> None: ...
    def on_tool_call(self, name: str, input: dict) -> None: ...
    def on_tool_result(self, name: str, input: dict, result: str) -> None: ...
    def on_stream_end(self) -> None: ...
    def on_input(self) -> str | None: ...


class NullHandler:
    """Default no-op handler. Subclass and override what you need."""

    def on_text(self, text: str) -> None:
        pass

    def on_thinking(self, text: str) -> None:
        pass

    def on_tool_call(self, name: str, input: dict) -> None:
        pass

    def on_tool_result(self, name: str, input: dict, result: str) -> None:
        pass

    def on_stream_end(self) -> None:
        pass

    def on_input(self) -> str | None:
        return input("> ")
