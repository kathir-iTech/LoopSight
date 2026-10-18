export interface RegionEvidence {
  edge_continuity: number;
  reference_similarity: number;
  layer_alignment_deviation: number;
  local_contrast?: number;
  // water-turbidity & optical nephelometry fields
  pattern_visibility?: number;
  pattern_sharpness?: number;
  pattern_found?: boolean;
  glare_ratio?: number;
  skew_deg?: number;
  stratification_delta?: number;
  // structural crack metrology fields
  crack_width_mm?: number;
  crack_length_px?: number;
  crack_severity_score?: number;
  detection_method?: string;
  // physical nephelometry & standards
  estimated_ntu?: number;
  who_tier?: "PRISTINE" | "ACCEPTABLE" | "ELEVATED_TURBIDITY" | string;
}

export interface Region {
  x: number;
  y: number;
  w: number;
  h: number;
  evidence: RegionEvidence;
}

export interface AgentCall {
  selector?: "gemini" | "deterministic_policy" | "deterministic_fallback";
  tool: string;
  reason_code: string;
  tool_chain?: string[];
}

export interface SecondPassRegion {
  edge_continuity: number;
  pattern_visibility?: number;
  pattern_sharpness?: number;
  pattern_found?: boolean | number;
  glare_ratio?: number;
  stratification_delta?: number;
  crack_width_mm?: number;
  crack_length_px?: number;
  crack_severity_score?: number;
  estimated_ntu?: number;
  who_tier?: "PRISTINE" | "ACCEPTABLE" | "ELEVATED_TURBIDITY" | string;
  [key: string]: number | boolean | string | undefined;
}

export interface SecondPass {
  regions: SecondPassRegion[];
  notes?: string;
}

export interface FinalDecision {
  decision: "PASS" | "REVIEW" | "FAIL" | "NO_PATTERN_DETECTED";
  confidence_band: string;
  human_approval_required: boolean;
  reasoning?: string[];
}

export interface Measurements {
  decode_ms: number | null;
  first_pass_ms: number | null;
  agent_ms: number | null;
  second_pass_ms: number | null;
  total_ms: number;
}

export interface InspectionResult {
  provenance?: {
    execution_mode: "live_opencv" | "synthetic_benchmark" | "demo_fixture";
    opencv_version?: string;
    measurement_basis?: string;
  };
  status: "CONFIDENT_PASS" | "CONFIDENT_FAIL" | "UNCERTAIN";
  inspection_profile?: string;
  regions: Region[];
  evidence_gap: string[];
  agent_call?: AgentCall;
  second_pass?: SecondPass;
  final_decision: FinalDecision;
  measurements?: Measurements;
  overlay_data_url?: string | null;
  frames?: Array<{ seq: number | string; timestamp: string; lighting: string }>;
  frame_info?: string;
}

export interface Job {
  id: string;
  created_at: string;
  result: InspectionResult;
}
