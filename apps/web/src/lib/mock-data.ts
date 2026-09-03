import type { InspectionResult } from "./types";

// ============================================================================
// DEMO MODE fixtures.
//
// IMPORTANT: these are NOT real computation. They are the pre-computed "golden"
// demo results (ported from services/inference/demo_golden.py) served only as a
// fallback when the real inference backend is unreachable from Vercel. They are
// shaped to exercise every UI branch (confident pass / confident fail /
// genuinely uncertain) and are NOT a substitute for the real OpenCV pipeline.
// The final architecture uses the real backend (currently the AWS Lambda path
// — a mandatory competition requirement) and does NOT depend on these.
//
// The selection between them is a pure function of the uploaded file's bytes
// via a deterministic hash, so the same file always yields the same result and
// different files usually differ. This exists only to stop the previous bug
// where EVERY fallback response was byte-for-byte identical regardless of the
// upload — which made two genuinely different images look identical in the UI.
// ============================================================================

const GOLDEN_RESULTS: Record<string, InspectionResult> = {
  confident_pass: {
    status: "CONFIDENT_PASS",
    regions: [
      {
        x: 0,
        y: 0,
        w: 200,
        h: 200,
        evidence: {
          edge_continuity: 0.97,
          reference_similarity: 1.0,
          layer_alignment_deviation: 0.02,
        },
      },
    ],
    evidence_gap: [],
    final_decision: {
      decision: "PASS",
      confidence_band: "high",
      human_approval_required: false,
    },
  },
  confident_fail: {
    status: "CONFIDENT_FAIL",
    regions: [
      {
        x: 0,
        y: 0,
        w: 200,
        h: 200,
        evidence: {
          edge_continuity: 0.08,
          reference_similarity: 0.47,
          layer_alignment_deviation: 0.61,
        },
      },
    ],
    evidence_gap: [],
    final_decision: {
      decision: "FAIL",
      confidence_band: "high",
      human_approval_required: true,
    },
  },
  uncertain: {
    status: "UNCERTAIN",
    regions: [
      {
        x: 0,
        y: 0,
        w: 200,
        h: 200,
        evidence: {
          edge_continuity: 0.52,
          reference_similarity: 0.73,
          layer_alignment_deviation: 0.31,
        },
      },
    ],
    evidence_gap: [
      "edge continuity 0.52 in ambiguous middle band (0.35-0.85)",
    ],
    agent_call: {
      tool: "measure_edge_continuity",
      reason_code: "AMBIGUOUS_EDGE_BAND",
    },
    second_pass: {
      regions: [
        {
          edge_continuity: 0.58,
          reference_similarity: 0.74,
          layer_alignment_deviation: 0.29,
          local_contrast: 0.42,
        },
      ],
    },
    final_decision: {
      decision: "REVIEW",
      confidence_band: "low",
      human_approval_required: true,
    },
  },
};

const DEMO_FIXTURE_KEYS = Object.keys(GOLDEN_RESULTS) as Array<
  keyof typeof GOLDEN_RESULTS
>;

// Deterministic non-cryptographic hash (FNV-1a) over the uploaded bytes.
export function fnv1a(data: Uint8Array): number {
  let hash = 0x811c9dc5;
  for (let i = 0; i < data.length; i++) {
    hash ^= data[i];
    hash = Math.imul(hash, 0x01000193);
  }
  return hash >>> 0;
}

// Pick a demo fixture purely from the file bytes: same bytes -> same fixture,
// different bytes -> (usually) a different fixture. Never random.
export function fixtureForFileBytes(data: Uint8Array): InspectionResult {
  const hash = fnv1a(data);
  const key = DEMO_FIXTURE_KEYS[hash % DEMO_FIXTURE_KEYS.length];
  return GOLDEN_RESULTS[key];
}

export function fixtureByCase(
  demoCase: string | undefined | null
): InspectionResult | null {
  const key = (demoCase || "").trim();
  if (key in GOLDEN_RESULTS) {
    return GOLDEN_RESULTS[key as keyof typeof GOLDEN_RESULTS];
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
