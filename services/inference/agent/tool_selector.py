"""
LoopSight v2 — bounded agent tool selection & MCP tool schema definitions.

Enforces double-layer whitelist validation, passes full multi-domain OpenCV 5
telemetry (pattern_visibility, glare_ratio, skew_deg, stratification_delta,
crack_width_px, crack_severity_score, edge_continuity, local_contrast) into
the Gemini prompt, and provides MCP-compatible tool descriptors for the
OpenCV AI Competition 2026 Agentic Vision & MCP track.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
import json
import math

from cv.first_pass import FirstPassResult, ALL_TOOLS

ALLOWED_TOOLS = set(ALL_TOOLS)
MAX_TOOL_CHAIN_LENGTH = 4

TOOL_ARGUMENT_LIMITS = {
    "reinspect_roi": {"scale": (1.0, 4.0)},
    "inpaint_specular_glare": {"radius": (1.0, 15.0)},
    "measure_edge_continuity": {"low": (0, 255), "high": (0, 255)},
}

MCP_TOOL_DESCRIPTORS = [
    {
        "name": "inpaint_specular_glare",
        "description": "Masks high-luminance low-saturation HSV specular glass reflections, runs Navier-Stokes/Telea inpainting (cv2.inpaint) + CLAHE contrast recovery, and re-measures pattern visibility.",
        "inputSchema": {
            "type": "object",
            "properties": {"radius": {"type": "number", "default": 5.0}},
        },
    },
    {
        "name": "rectify_perspective_homography",
        "description": "Detects perspective-skewed calibration target corners, computes a planar homography (cv2.getPerspectiveTransform + cv2.warpPerspective), and re-measures fronto-parallel visibility.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "analyze_vertical_stratification",
        "description": "Splits liquid column into 3 horizontal strata (top supernatant, middle suspension, bottom sediment layer) to isolate settled turbidity from clear upper water.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "skeletonize_crack_metrology",
        "description": "Removes low-frequency shadow gradients via homomorphic Gaussian division and measures image-space line width in pixels via Euclidean distance transform (cv2.distanceTransform).",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "track_across_frames",
        "description": "Compares multi-lighting (ambient vs backlight/flash) or temporal frames, computing persistence_std and sub-pixel cv2.phaseCorrelate registration shift.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "reinspect_roi",
        "description": "Upsamples the ROI via 2x bicubic interpolation (cv2.INTER_CUBIC) to resolve borderline high-frequency pattern or edge detail.",
        "inputSchema": {
            "type": "object",
            "properties": {"scale": {"type": "number", "default": 2.0}},
        },
    },
    {
        "name": "measure_edge_continuity",
        "description": "Re-evaluates Canny edge continuity at sensitive thresholds (low=30, high=100) when default thresholds miss subtle boundaries.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "low": {"type": "integer", "default": 30},
                "high": {"type": "integer", "default": 100},
            },
        },
    },
    {
        "name": "compare_to_reference",
        "description": "Runs histogram-equalized absdiff comparison against a known-good reference image.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]

# Declare the image inputs that the RPC endpoint actually accepts.
for _descriptor in MCP_TOOL_DESCRIPTORS:
    _schema = _descriptor["inputSchema"]
    _properties = _schema["properties"]
    _properties.update({
        "sample_id": {"type": "string", "description": "Synthetic benchmark ID; used only when no image is supplied."},
        "image_base64": {"type": "string", "description": "Base64-encoded uploaded image (10 MiB maximum decoded)."},
    })
    for _name, (_minimum, _maximum) in TOOL_ARGUMENT_LIMITS.get(_descriptor["name"], {}).items():
        _properties[_name].update({"minimum": _minimum, "maximum": _maximum})
    if _descriptor["name"] == "track_across_frames":
        _properties["second_image_base64"] = {"type": "string", "description": "A distinct second captured image."}
        _schema["required"] = ["second_image_base64"]
    _schema["additionalProperties"] = False


@dataclass
class ToolCall:
    tool: str
    arguments: dict
    reason_code: str
    tool_chain: list[str] = field(default_factory=list)


class InvalidToolCallError(Exception):
    """Raised when the agent (or a mock/fixture standing in for it) returns
    something outside the whitelist or malformed."""


def validate_tool_call(raw: dict, allowed_tools: set[str] | None = None) -> ToolCall:
    """Enforce the whitelist a SECOND time here, independent of whatever
    schema validation happened upstream. Supports both atomic tools and
    multi-tool composite chains."""
    if not isinstance(raw, dict):
        raise InvalidToolCallError(f"tool call must be a dict, got {type(raw)}")

    tool = raw.get("tool")
    tool_chain_raw = raw.get("tool_chain")

    if isinstance(tool, str) and (" -> " in tool or "," in tool):
        delims = " -> " if " -> " in tool else ","
        chain = [t.strip() for t in tool.split(delims) if t.strip()]
    elif isinstance(tool_chain_raw, list) and tool_chain_raw:
        chain = [str(t).strip() for t in tool_chain_raw if str(t).strip()]
        tool = chain[0] if len(chain) == 1 else " -> ".join(chain)
    elif isinstance(tool, str) and tool in ALLOWED_TOOLS:
        chain = [tool]
    else:
        raise InvalidToolCallError(f"tool '{tool}' is not in the whitelist {sorted(ALLOWED_TOOLS)}")

    if not 1 <= len(chain) <= MAX_TOOL_CHAIN_LENGTH or len(set(chain)) != len(chain):
        raise InvalidToolCallError("tool chains require one to four distinct tools")
    permitted = ALLOWED_TOOLS if allowed_tools is None else ALLOWED_TOOLS & allowed_tools
    for t in chain:
        if t not in permitted:
            raise InvalidToolCallError(f"tool '{t}' in chain is not in the whitelist {sorted(ALLOWED_TOOLS)}")

    reason_code = raw.get("reason_code")
    if not isinstance(reason_code, str) or not reason_code.strip() or len(reason_code) > 256:
        raise InvalidToolCallError("reason_code must contain 1 to 256 characters")
    arguments = raw.get("arguments", {})
    if not isinstance(arguments, dict):
        raise InvalidToolCallError("arguments must be a dict")
    limits = {key: bounds for name in chain for key, bounds in TOOL_ARGUMENT_LIMITS.get(name, {}).items()}
    for name, value in arguments.items():
        if name not in limits:
            raise InvalidToolCallError(f"unsupported argument '{name}' for selected tools")
        low, high = limits[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise InvalidToolCallError(f"argument '{name}' must be a finite number")
        if not low <= value <= high:
            raise InvalidToolCallError(f"argument '{name}' must be between {low} and {high}")
        if name in ("low", "high") and not isinstance(value, int):
            raise InvalidToolCallError(f"argument '{name}' must be an integer")
    if "measure_edge_continuity" in chain and arguments.get("low", 30) >= arguments.get("high", 100):
        raise InvalidToolCallError("Canny low threshold must be below high threshold")
    return ToolCall(tool=" -> ".join(chain), arguments=arguments, reason_code=reason_code, tool_chain=chain)


def _build_prompt(first_pass: FirstPassResult) -> str:
    evidence_gap = first_pass.evidence_gap
    candidate_tools = sorted(set(first_pass.allowed_tools) & ALLOWED_TOOLS) if first_pass.allowed_tools else sorted(ALLOWED_TOOLS)
    region_summaries = [
        {
            "edge_continuity": round(float(r.edge_continuity), 4),
            "reference_similarity": round(float(r.reference_similarity), 4),
            "local_contrast": round(float(r.local_contrast), 4),
            "pattern_visibility": round(float(getattr(r, "pattern_visibility", 0.0)), 4),
            "pattern_sharpness": round(float(getattr(r, "pattern_sharpness", 0.0)), 4),
            "pattern_found": bool(getattr(r, "pattern_found", False)),
            "glare_ratio": round(float(getattr(r, "glare_ratio", 0.0)), 4),
            "skew_deg": round(float(getattr(r, "skew_deg", 0.0)), 2),
            "stratification_delta": round(float(getattr(r, "stratification_delta", 0.0)), 4),
            "crack_width_px": round(float(getattr(r, "crack_width_px", 0.0)), 3),
            "crack_severity_score": round(float(getattr(r, "crack_severity_score", 0.0)), 4),
        }
        for r in first_pass.regions
    ]
    return (
        "You are the bounded active-perception controller for LoopSight (OpenCV 5). "
        "Given this first-pass evidence gap and region telemetry, choose exactly one OpenCV tool from "
        f"{candidate_tools} to resolve the visual ambiguity. Respond strictly as JSON: "
        '{"tool": "...", "arguments": {...}, "reason_code": "..."}. '
        f"Evidence gap: {evidence_gap}. Region telemetry: {region_summaries}."
    )


def call_gemini(first_pass: FirstPassResult, api_key: str, model: str = "gemini-3.6-flash") -> ToolCall:
    """One bounded Gemini request; failures use the local policy fallback."""
    from google import genai  # deferred import

    timeout_sec = float(os.environ.get("GEMINI_TIMEOUT_SECONDS", "15").strip() or 15)
    if not math.isfinite(timeout_sec) or not 0.1 <= timeout_sec <= 20:
        raise ValueError("GEMINI_TIMEOUT_SECONDS must be between 0.1 and 20")
    client = genai.Client(
        api_key=api_key,
        http_options={"timeout": round(timeout_sec * 1000), "retry_options": {"attempts": 1}},
    )
    prompt = _build_prompt(first_pass)
    try:
        response = client.models.generate_content(
            model=model,
            contents=[{"text": prompt}],
            config={"response_mime_type": "application/json"},
        )
        return validate_tool_call(json.loads(response.text), allowed_tools=set(first_pass.allowed_tools))
    finally:
        client.close()


def select_tool_mock(first_pass: FirstPassResult, fixture: dict) -> ToolCall:
    """Deterministic offline/CI tool selection path validated through the same whitelist."""
    return validate_tool_call(fixture, allowed_tools=set(first_pass.allowed_tools))


def select_tool(
    first_pass: FirstPassResult,
    *,
    api_key: str | None = None,
    mock_fixture: dict | None = None,
    default_tool: str = "reinspect_roi",
) -> ToolCall:
    """Top-level entry point with deterministic fallback."""
    permitted = set(first_pass.allowed_tools) & ALLOWED_TOOLS
    if default_tool not in permitted:
        if not permitted:
            raise InvalidToolCallError("no tools permitted for this inspection")
        default_tool = sorted(permitted)[0]
    try:
        if mock_fixture is not None:
            return select_tool_mock(first_pass, mock_fixture)
        if api_key is not None:
            return call_gemini(first_pass, api_key, model=os.environ.get("GEMINI_MODEL", "gemini-3.6-flash"))
        raise InvalidToolCallError("no api_key or mock_fixture provided")
    except InvalidToolCallError:
        return ToolCall(
            tool=default_tool,
            arguments={},
            reason_code="FALLBACK_AFTER_INVALID_AGENT_RESPONSE",
        )
    except Exception as exc:
        return ToolCall(
            tool=default_tool,
            arguments={},
            reason_code=f"FALLBACK_AFTER_AGENT_CALL_ERROR:{type(exc).__name__}",
        )
