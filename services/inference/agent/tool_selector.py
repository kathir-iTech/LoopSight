"""
LoopSight — bounded agent tool selection.

IMPORTANT — honesty note about what's actually been tested in this
environment: this sandbox has no network access and no Gemini API key, so
the real `call_gemini()` path below has NOT been executed here. It's
written against the documented Gemini API shape, but per spec Section 11's
Revision 2 note, the exact current model name/quotas need verifying in
Google AI Studio before this is trusted. What HAS been tested (see
tests/test_tool_selector.py) is everything around that call: the
whitelist enforcement, the reason_code validation, and the mock mode —
which is also exactly what a real build should use for routine test runs
per spec Section 27, calling the live API only when specifically testing
the agent-integration path itself.
"""

from __future__ import annotations

from dataclasses import dataclass
import json

from cv.first_pass import FirstPassResult, ALL_TOOLS

ALLOWED_TOOLS = set(ALL_TOOLS)


@dataclass
class ToolCall:
    tool: str
    arguments: dict
    reason_code: str


class InvalidToolCallError(Exception):
    """Raised when the agent (or a mock/fixture standing in for it) returns
    something outside the whitelist or malformed. Callers should catch this
    and fall back to a deterministic default tool, never crash the pipeline
    on it — see spec Section 20's risk register."""


def validate_tool_call(raw: dict) -> ToolCall:
    """Enforce the whitelist a SECOND time here, independent of whatever
    schema validation happened upstream — spec Section 12's data-contract
    principle: never trust a single validation layer for something that
    gates an actual action."""
    if not isinstance(raw, dict):
        raise InvalidToolCallError(f"tool call must be a dict, got {type(raw)}")
    tool = raw.get("tool")
    if tool not in ALLOWED_TOOLS:
        raise InvalidToolCallError(f"tool '{tool}' is not in the whitelist {sorted(ALLOWED_TOOLS)}")
    reason_code = raw.get("reason_code")
    if not isinstance(reason_code, str) or not reason_code:
        raise InvalidToolCallError("reason_code must be a non-empty string")
    arguments = raw.get("arguments", {})
    if not isinstance(arguments, dict):
        raise InvalidToolCallError("arguments must be a dict")
    return ToolCall(tool=tool, arguments=arguments, reason_code=reason_code)


def _build_prompt(first_pass: FirstPassResult) -> str:
    evidence_gap = first_pass.evidence_gap
    region_summaries = [
        {"edge_continuity": r.edge_continuity, "reference_similarity": r.reference_similarity, "local_contrast": r.local_contrast}
        for r in first_pass.regions
    ]
    return (
        "Given this inspection evidence gap, choose exactly one tool from "
        f"{sorted(ALLOWED_TOOLS)} to resolve the ambiguity. Respond as JSON: "
        '{"tool": "...", "arguments": {...}, "reason_code": "..."}. '
        f"Evidence gap: {evidence_gap}. Region measurements: {region_summaries}."
    )


def call_gemini(first_pass: FirstPassResult, api_key: str, model: str = "gemini-3.7-flash") -> ToolCall:
    """UNTESTED IN THIS ENVIRONMENT (no network/API key here) — see module
    docstring. Written against the documented structured-output API shape;
    verify the exact model name and response_schema behavior directly
    against a real API key before relying on this in a demo."""
    from google import genai  # deferred import — this package isn't installed in this sandbox

    client = genai.Client(api_key=api_key)
    prompt = _build_prompt(first_pass)
    response = client.models.generate_content(
        model=model,
        contents=[{"text": prompt}],
        config={"response_mime_type": "application/json"},
    )
    raw = json.loads(response.text)
    return validate_tool_call(raw)


def select_tool_mock(first_pass: FirstPassResult, fixture: dict) -> ToolCall:
    """Test/dev path — replays a recorded or hand-written response instead
    of calling the live API. This is the path exercised by this repo's
    test suite right now, and it's also the recommended pattern for
    routine CI runs per spec Section 27 (avoid burning API quota on every
    test run; only hit the live model when specifically testing that
    integration)."""
    return validate_tool_call(fixture)


def select_tool(
    first_pass: FirstPassResult,
    *,
    api_key: str | None = None,
    mock_fixture: dict | None = None,
    default_tool: str = "reinspect_roi",
) -> ToolCall:
    """Top-level entry point with a deterministic fallback baked in.
    Per spec Section 20's risk register: a malformed or failed agent
    response should never crash the pipeline — it should fall back to a
    sane deterministic default, logged as a fallback, not silently
    swallowed."""
    try:
        if mock_fixture is not None:
            return select_tool_mock(first_pass, mock_fixture)
        if api_key is not None:
            return call_gemini(first_pass, api_key)
        raise InvalidToolCallError("no api_key or mock_fixture provided")
    except InvalidToolCallError:
        return ToolCall(
            tool=default_tool,
            arguments={},
            reason_code="FALLBACK_AFTER_INVALID_AGENT_RESPONSE",
        )
    except Exception as exc:
        # Deliberately broad: a real deployment WILL see 429s, timeouts,
        # and transient network errors under concurrent judge/tester
        # traffic on a free-tier API key — none of those are
        # InvalidToolCallError, and none of them should crash the request.
        # Same fallback contract either way; the reason_code says which
        # kind of failure it was, for the CloudWatch logs to distinguish.
        return ToolCall(
            tool=default_tool,
            arguments={},
            reason_code=f"FALLBACK_AFTER_AGENT_CALL_ERROR:{type(exc).__name__}",
        )
