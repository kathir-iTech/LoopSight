export interface RegionEvidence {
  edge_continuity: number;
  reference_similarity: number;
  layer_alignment_deviation: number;
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
  [key: string]: number;
}

export interface SecondPass {
  regions: SecondPassRegion[];
}

export interface FinalDecision {
  decision: "PASS" | "REVIEW" | "FAIL";
  confidence_band: string;
  human_approval_required: boolean;
}

export interface InspectionResult {
  status: "CONFIDENT_PASS" | "CONFIDENT_FAIL" | "UNCERTAIN";
  regions: Region[];
  evidence_gap: string[];
  agent_call?: AgentCall;
  second_pass?: SecondPass;
  final_decision: FinalDecision;
}

export interface Job {
  id: string;
  created_at: string;
  result: InspectionResult;
}
