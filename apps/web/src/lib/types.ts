export interface RegionEvidence {
  edge_continuity: number;
  reference_similarity: number;
  layer_alignment_deviation: number;
  // water-turbidity fields (present when inspection_profile == water_turbidity_v1)
  pattern_visibility?: number;
  pattern_sharpness?: number;
  pattern_found?: boolean;
  local_contrast?: number;
}

export interface Region {
  x: number;
  y: number;
  w: number;
  h: number;
  evidence: RegionEvidence;
}

export interface AgentCall {
  tool: string;
  reason_code: string;
}

export interface SecondPassRegion {
  edge_continuity: number;
  pattern_visibility?: number;
  pattern_sharpness?: number;
  pattern_found?: boolean | number;
  [key: string]: number | boolean | undefined;
}

export interface SecondPass {
  regions: SecondPassRegion[];
}

export interface FinalDecision {
  decision: "PASS" | "REVIEW" | "FAIL";
  confidence_band: string;
  human_approval_required: boolean;
}

export interface Measurements {
  decode_ms: number;
  first_pass_ms: number;
  agent_ms: number | null;
  second_pass_ms: number | null;
  total_ms: number;
}

export interface InspectionResult {
  status: "CONFIDENT_PASS" | "CONFIDENT_FAIL" | "UNCERTAIN";
  regions: Region[];
  evidence_gap: string[];
  agent_call?: AgentCall;
  second_pass?: SecondPass;
  final_decision: FinalDecision;
  measurements?: Measurements;
}

export interface Job {
  id: string;
  created_at: string;
  result: InspectionResult;
}
