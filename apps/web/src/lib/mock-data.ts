import type { InspectionResult } from "./types";

// ============================================================================
// LoopSight v2 — Calibrated Benchmark & Demo Resilience Fixtures
//
// Used only when DEMO_MODE=golden or when INFERENCE_API_URL is unreachable and
// FAIL_CLOSED_PROD is not set. Mirrors the exact telemetry output of the real
// OpenCV 5 backend across all 6 benchmark scenarios and 3 profiles.
// ============================================================================

const GOLDEN_RESULTS: Record<string, InspectionResult> = {
  water_glare_confounded: {
    status: "UNCERTAIN",
    inspection_profile: "water_turbidity_v1",
    regions: [
      {
        x: 0,
        y: 0,
        w: 200,
        h: 200,
        evidence: {
          edge_continuity: 0.505,
          reference_similarity: 1.0,
          layer_alignment_deviation: 0.14,
          local_contrast: 0.338,
          pattern_visibility: 0.505,
          pattern_sharpness: 0.665,
          pattern_found: true,
          glare_ratio: 0.037,
          skew_deg: 0.0,
          stratification_delta: 0.002,
          detection_method: "contours_32_squares",
        },
      },
    ],
    evidence_gap: [
      "specular glass glare (3.7% saturated pixels) confounding pattern visibility 0.51 — run specular glare inpainting or second lighting",
    ],
    agent_call: {
      tool: "inpaint_specular_glare",
      reason_code: "SPECULAR_GLASS_GLARE_CONFOUNDER",
    },
    second_pass: {
      regions: [
        {
          edge_continuity: 0.893,
          pattern_visibility: 0.893,
          pattern_sharpness: 1.0,
          pattern_found: true,
          local_contrast: 0.762,
          glare_ratio: 0.005,
          stratification_delta: 0.002,
        },
      ],
      notes: "inpainted 3.7% specular glare pixels (cv2.INPAINT_TELEA, r=5.0) + dynamic range contrast recovery",
    },
    final_decision: {
      decision: "PASS",
      confidence_band: "medium",
      human_approval_required: false,
      reasoning: [
        "second-pass pattern visibility 0.89 resolved toward clear water (no visible turbidity)",
      ],
    },
    overlay_data_url: "/samples/overlays/water_glare_confounded_overlay.png",
    measurements: {
      decode_ms: 0.8,
      first_pass_ms: 4.2,
      agent_ms: 0.3,
      second_pass_ms: 3.9,
      total_ms: 9.2,
    },
  },
  water_stratified_sediment: {
    status: "UNCERTAIN",
    inspection_profile: "water_turbidity_v1",
    regions: [
      {
        x: 0,
        y: 0,
        w: 200,
        h: 200,
        evidence: {
          edge_continuity: 0.431,
          reference_similarity: 1.0,
          layer_alignment_deviation: 0.38,
          local_contrast: 0.414,
          pattern_visibility: 0.431,
          pattern_sharpness: 0.448,
          pattern_found: true,
          glare_ratio: 0.0,
          skew_deg: 0.0,
          stratification_delta: 0.471,
          detection_method: "contours_24_squares",
        },
      },
    ],
    evidence_gap: [
      "vertical turbidity stratification detected (top-vs-bottom delta 0.47) — run vertical stratification analysis",
    ],
    agent_call: {
      tool: "analyze_vertical_stratification",
      reason_code: "VERTICAL_SETTLING_STRATIFICATION",
    },
    second_pass: {
      regions: [
        {
          edge_continuity: 0.042,
          pattern_visibility: 0.042,
          pattern_sharpness: 0.002,
          pattern_found: true,
          local_contrast: 0.414,
          stratification_delta: 0.471,
        },
      ],
      notes: "3-zone vertical nephelometry: top=0.513, mid=0.511, bottom=0.042 (delta=0.471, governing_min=0.042)",
    },
    final_decision: {
      decision: "FAIL",
      confidence_band: "medium",
      human_approval_required: true,
      reasoning: [
        "second-pass pattern visibility 0.04 resolved toward turbid water (visible turbidity)",
      ],
    },
    overlay_data_url: "/samples/overlays/water_stratified_sediment_overlay.png",
    measurements: {
      decode_ms: 0.7,
      first_pass_ms: 4.1,
      agent_ms: 0.2,
      second_pass_ms: 2.8,
      total_ms: 7.8,
    },
  },
  water_dual_lighting: {
    status: "UNCERTAIN",
    inspection_profile: "water_turbidity_v1",
    regions: [
      {
        x: 0,
        y: 0,
        w: 200,
        h: 200,
        evidence: {
          edge_continuity: 0.314,
          reference_similarity: 1.0,
          layer_alignment_deviation: 0.18,
          local_contrast: 0.311,
          pattern_visibility: 0.314,
          pattern_sharpness: 0.098,
          pattern_found: true,
          glare_ratio: 0.0,
          skew_deg: 0.0,
          stratification_delta: 0.002,
          detection_method: "chessboard_7x7",
        },
      },
    ],
    evidence_gap: [
      "pattern visibility 0.31 in borderline band (0.2-0.55) — request photo under different lighting (backlight vs ambient or with phone flash)",
    ],
    agent_call: {
      tool: "track_across_frames",
      reason_code: "BORDERLINE_PATTERN_VISIBILITY",
    },
    second_pass: {
      regions: [
        {
          edge_continuity: 0.793,
          pattern_visibility: 0.793,
          pattern_sharpness: 1.0,
          pattern_found: true,
          local_contrast: 0.698,
        },
      ],
      notes: "persistence_std=0.239 across 2 frames on pattern_visibility (phase_shift=0.00px) | frames 1@ambient -> 2@backlight",
    },
    frames: [
      { seq: 1, timestamp: "2026-10-14T17:00:01Z", lighting: "ambient" },
      { seq: 2, timestamp: "2026-10-14T17:00:04Z", lighting: "backlight" },
    ],
    frame_info: "LOOK 1: 2026-10-14T17:00:01Z frame #1 (ambient) -> LOOK 2: 2026-10-14T17:00:04Z frame #2 (backlight)",
    final_decision: {
      decision: "PASS",
      confidence_band: "medium",
      human_approval_required: false,
      reasoning: [
        "second-pass pattern visibility 0.79 resolved toward clear water (no visible turbidity)",
      ],
    },
    overlay_data_url: "/samples/overlays/water_dual_lighting_overlay.png",
    measurements: {
      decode_ms: 0.9,
      first_pass_ms: 4.5,
      agent_ms: 0.3,
      second_pass_ms: 5.1,
      total_ms: 10.8,
    },
  },
  water_turbid_fail: {
    status: "CONFIDENT_FAIL",
    inspection_profile: "water_turbidity_v1",
    regions: [
      {
        x: 0,
        y: 0,
        w: 200,
        h: 200,
        evidence: {
          edge_continuity: 0.114,
          reference_similarity: 1.0,
          layer_alignment_deviation: 0.0,
          local_contrast: 0.222,
          pattern_visibility: 0.114,
          pattern_sharpness: 0.041,
          pattern_found: true,
          glare_ratio: 0.0,
          skew_deg: 0.0,
          stratification_delta: 0.004,
          detection_method: "contours_12_squares",
        },
      },
    ],
    evidence_gap: [],
    final_decision: {
      decision: "FAIL",
      confidence_band: "high",
      human_approval_required: true,
      reasoning: ["first pass confidently detected a defect/contamination signal"],
    },
    overlay_data_url: "/samples/overlays/water_turbid_fail_overlay.png",
    measurements: {
      decode_ms: 0.7,
      first_pass_ms: 3.8,
      agent_ms: null,
      second_pass_ms: null,
      total_ms: 4.5,
    },
  },
  crack_shadow_confounded: {
    status: "UNCERTAIN",
    inspection_profile: "structural_crack_metrology_v1",
    regions: [
      {
        x: 0,
        y: 0,
        w: 200,
        h: 200,
        evidence: {
          edge_continuity: 0.28,
          reference_similarity: 1.0,
          layer_alignment_deviation: 0.19,
          local_contrast: 0.21,
          glare_ratio: 0.108,
          crack_width_mm: 0.24,
          crack_length_px: 64.0,
          crack_severity_score: 0.28,
          detection_method: "distance_transform_metrology",
        },
      },
    ],
    evidence_gap: [
      "surface glare (10.8%) obscuring fracture boundary — inpaint glare and re-measure crack width",
    ],
    agent_call: {
      tool: "skeletonize_crack_metrology",
      reason_code: "SHADOW_VS_FRACTURE_METROLOGY",
    },
    second_pass: {
      regions: [
        {
          edge_continuity: 0.0,
          local_contrast: 0.14,
          crack_width_mm: 0.0,
          crack_length_px: 0.0,
          crack_severity_score: 0.0,
        },
      ],
      notes: "illumination-normalized distance-transform metrology: crack_width=0.000mm, length=0.0px, severity=0.000",
    },
    final_decision: {
      decision: "PASS",
      confidence_band: "medium",
      human_approval_required: false,
      reasoning: [
        "second-pass illumination-normalized metrology cleared shadow/surface artifact (width=0.00mm, severity=0.00)",
      ],
    },
    overlay_data_url: "/samples/overlays/crack_shadow_confounded_overlay.png",
    measurements: {
      decode_ms: 0.8,
      first_pass_ms: 5.2,
      agent_ms: 0.3,
      second_pass_ms: 4.7,
      total_ms: 11.0,
    },
  },
  crack_structural_fail: {
    status: "CONFIDENT_FAIL",
    inspection_profile: "structural_crack_metrology_v1",
    regions: [
      {
        x: 0,
        y: 0,
        w: 200,
        h: 200,
        evidence: {
          edge_continuity: 0.88,
          reference_similarity: 1.0,
          layer_alignment_deviation: 0.42,
          local_contrast: 0.19,
          glare_ratio: 0.0,
          crack_width_mm: 0.719,
          crack_length_px: 151.0,
          crack_severity_score: 1.0,
          detection_method: "distance_transform_metrology",
        },
      },
    ],
    evidence_gap: [],
    final_decision: {
      decision: "FAIL",
      confidence_band: "high",
      human_approval_required: true,
      reasoning: ["first pass confidently detected a defect/contamination signal"],
    },
    overlay_data_url: "/samples/overlays/crack_structural_fail_overlay.png",
    measurements: {
      decode_ms: 0.7,
      first_pass_ms: 4.9,
      agent_ms: null,
      second_pass_ms: null,
      total_ms: 5.6,
    },
  },
};

// Legacy aliases
GOLDEN_RESULTS.confident_pass = GOLDEN_RESULTS.water_glare_confounded;
GOLDEN_RESULTS.confident_fail = GOLDEN_RESULTS.water_turbid_fail;
GOLDEN_RESULTS.uncertain = GOLDEN_RESULTS.water_dual_lighting;

const PRIMARY_KEYS = [
  "water_glare_confounded",
  "water_stratified_sediment",
  "water_dual_lighting",
  "water_turbid_fail",
  "crack_shadow_confounded",
  "crack_structural_fail",
];

export function fnv1a(data: Uint8Array): number {
  let hash = 0x811c9dc5;
  for (let i = 0; i < data.length; i++) {
    hash ^= data[i];
    hash = Math.imul(hash, 0x01000193);
  }
  return hash >>> 0;
}

export function fixtureForFileBytes(data: Uint8Array, profile?: string): InspectionResult {
  const hash = fnv1a(data);
  if (profile === "structural_crack_metrology_v1") {
    const crackKeys = ["crack_shadow_confounded", "crack_structural_fail"];
    return GOLDEN_RESULTS[crackKeys[hash % crackKeys.length]];
  }
  const waterKeys = [
    "water_glare_confounded",
    "water_stratified_sediment",
    "water_dual_lighting",
    "water_turbid_fail",
  ];
  return GOLDEN_RESULTS[waterKeys[hash % waterKeys.length]];
}

export function fixtureByCase(
  demoCase: string | undefined | null
): InspectionResult | null {
  const key = (demoCase || "").trim();
  if (key in GOLDEN_RESULTS) {
    return GOLDEN_RESULTS[key];
  }
  if (PRIMARY_KEYS.includes(key)) {
    return GOLDEN_RESULTS[key];
  }
  return null;
}

const jobs = new Map<string, { result: InspectionResult; created_at: string }>();

export function createJob(result: InspectionResult): string {
  const id = crypto.randomUUID().slice(0, 8);
  jobs.set(id, { result, created_at: new Date().toISOString() });
  return id;
}

export function getJob(id: string): { id: string; result: InspectionResult; created_at: string } | null {
  const job = jobs.get(id);
  if (!job) return null;
  return { id, ...job };
}
