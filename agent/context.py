"""Context window management -- compaction, masking, and token estimation.

Keeps the conversation within budget without losing important context.
"""

import json
import logging

log = logging.getLogger(__name__)

MASK_THRESHOLD = 1500  # chars -- tool results larger than this get masked


def estimate_tokens(messages: list[dict]) -> int:
    """Rough token estimate (~4 chars per token)."""
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += len(content) // 4
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    total += len(str(item.get("content", ""))) // 4
                elif hasattr(item, "text"):
                    total += len(item.text) // 4
                elif hasattr(item, "input"):
                    total += len(str(item.input)) // 4
                else:
                    total += len(str(item)) // 4
    return total


def summarize_dropped(messages: list[dict]) -> str:
    """Build a structured summary of dropped messages for context continuity.

    Extracts: user requests, tool calls made, key decisions/results,
    and workflow state.
    """
    sections = {
        "user_requests": [],
        "tools_called": [],
        "key_results": [],
        "workflow_info": None,
    }

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if role == "user" and isinstance(content, str):
            text = content.strip()
            if text and not text.startswith("["):
                sections["user_requests"].append(text[:100])

        elif role == "user" and isinstance(content, list):
            for block in content:
                if not isinstance(block, dict) or block.get("type") != "tool_result":
                    continue
                result_text = block.get("content", "")
                if not isinstance(result_text, str):
                    continue
                if '"loaded_path"' in result_text or '"saved"' in result_text:
                    try:
                        data = json.loads(result_text)
                        path = (
                            data.get("loaded_path")
                            or data.get("saved")
                            or data.get("file")
                        )
                        if path:
                            sections["workflow_info"] = path
                    except Exception as e:
                        log.debug(
                            "Could not parse tool result for context summary: %s",
                            type(e).__name__,
                        )

        elif role == "assistant" and isinstance(content, list):
            for block in content:
                if hasattr(block, "type") and block.type == "tool_use":
                    sections["tools_called"].append(block.name)
                elif isinstance(block, dict) and block.get("type") == "tool_use":
                    sections["tools_called"].append(block.get("name", "?"))

    lines = ["[Context Summary - earlier messages compacted]"]

    if sections["user_requests"]:
        lines.append(
            "Topics discussed: " + "; ".join(sections["user_requests"][:5])
        )

    if sections["tools_called"]:
        seen = set()
        unique = []
        for t in sections["tools_called"]:
            if t not in seen:
                seen.add(t)
                unique.append(t)
        lines.append("Tools used: " + ", ".join(unique))

    if sections["workflow_info"]:
        lines.append(f"Workflow context: {sections['workflow_info']}")

    lines.append("Recent conversation follows.")
    return "\n".join(lines)


def compact(messages: list[dict], threshold: int) -> list[dict]:
    """Compact messages to stay within context budget.

    Strategy:
      1. Truncate large tool results > 2000 chars
      2. Drop oldest exchanges with structured summary, keeping 6 recent
    """
    estimated = estimate_tokens(messages)
    if estimated <= threshold:
        return messages

    log.info(
        "Context at ~%d tokens, compacting (threshold: %d)", estimated, threshold
    )

    # Pass 1: Truncate large tool results
    compacted = []
    for msg in messages:
        if msg["role"] == "user" and isinstance(msg.get("content"), list):
            new_content = []
            for block in msg["content"]:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    content = block.get("content", "")
                    if isinstance(content, str) and len(content) > 2000:
                        block = {
                            **block,
                            "content": content[:2000] + "\n[...truncated]",
                        }
                new_content.append(block)
            compacted.append({**msg, "content": new_content})
        else:
            compacted.append(msg)

    estimated = estimate_tokens(compacted)
    if estimated <= threshold:
        log.info("Compacted to ~%d tokens via tool result truncation", estimated)
        return compacted

    # Pass 2: Drop oldest exchanges with structured summary
    keep_recent = 6
    if len(compacted) > keep_recent:
        dropped = compacted[:-keep_recent]
        dropped_count = len(dropped)
        summary_text = summarize_dropped(dropped)
        summary_msg = {"role": "user", "content": summary_text}
        compacted = [summary_msg] + compacted[-keep_recent:]
        log.info(
            "Dropped %d older messages, keeping %d recent",
            dropped_count,
            keep_recent,
        )

    return compacted


def mask_processed_results(messages: list[dict]) -> list[dict]:
    """Replace large tool results in older turns with compact summaries.

    Only masks results from turns that have already been processed
    (i.e., there's a subsequent assistant message). The most recent
    tool results are kept intact since the model hasn't responded yet.
    """
    if len(messages) < 3:
        return messages

    last_tool_result_idx = -1
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        if msg["role"] == "user" and isinstance(msg.get("content"), list):
            has_tool_result = any(
                isinstance(b, dict) and b.get("type") == "tool_result"
                for b in msg["content"]
            )
            if has_tool_result:
                last_tool_result_idx = i
                break

    masked = []
    for i, msg in enumerate(messages):
        if (
            i < last_tool_result_idx
            and msg["role"] == "user"
            and isinstance(msg.get("content"), list)
        ):
            new_content = []
            for block in msg["content"]:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    content = block.get("content", "")
                    if isinstance(content, str) and len(content) > MASK_THRESHOLD:
                        preview = content[:200]
                        char_count = len(content)
                        block = {
                            **block,
                            "content": (
                                f"[Processed result ({char_count} chars)]\n"
                                f"{preview}...\n"
                                f"[Full output was processed in prior turn]"
                            ),
                        }
                new_content.append(block)
            masked.append({**msg, "content": new_content})
        else:
            masked.append(msg)

    return masked
