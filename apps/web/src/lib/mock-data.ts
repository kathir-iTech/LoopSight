import type { InspectionResult } from "./types";

export const MOCK_RESULT: InspectionResult = {
  status: "UNCERTAIN",
  regions: [
    {
      x: 120,
      y: 90,
      w: 220,
      h: 180,
      evidence: {
        edge_continuity: 0.81,
        reference_similarity: 0.64,
        layer_alignment_deviation: 0.48,
      },
    },
  ],
  evidence_gap: [
    "low local contrast — cannot confirm edge deviation",
  ],
  agent_call: {
    tool: "reinspect_roi",
    reason_code: "INSUFFICIENT_LOCAL_CONTRAST",
  },
  second_pass: {
    regions: [{ edge_continuity: 0.91 }],
  },
  final_decision: {
    decision: "REVIEW",
    confidence_band: "medium",
    human_approval_required: true,
  },
};

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
