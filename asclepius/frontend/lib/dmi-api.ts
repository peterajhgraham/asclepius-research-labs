import axios from "axios";

// ------------------------------------------------------------------
// Domain type: any scientific domain (e.g., immunology, oncology, neuroscience)
// ------------------------------------------------------------------
export type Vertical = string;

// ------------------------------------------------------------------
// Disease Mechanism Report types
// ------------------------------------------------------------------

export interface CorePathway {
  name: string;
  description: string;
  evidence_pmids: string[];
}

export interface ValidatedTarget {
  target: string;
  mechanism: string;
  evidence_pmids: string[];
}

export interface FailedTarget {
  target: string;
  stage_failed: string;
  mechanistic_reason: string;
  evidence_pmids: string[];
}

export interface MechanisticContradiction {
  description: string;
  evidence_pmids: string[];
}

export interface DiseaseReportRequest {
  disease_name: string;
  vertical: Vertical;
}

export interface DiseaseReportResponse {
  disease_summary: string;
  core_pathways: CorePathway[];
  causal_genes: string[];
  key_cell_types: string[];
  validated_targets: ValidatedTarget[];
  failed_targets: FailedTarget[];
  mechanistic_contradictions: MechanisticContradiction[];
  biomarkers: string[];
  unresolved_questions: string[];
  all_citations: string[];
}

// ------------------------------------------------------------------
// Target Risk Report types
// ------------------------------------------------------------------

export interface HistoricalFailure {
  program: string;
  failure_stage: string;
  reason: string;
  evidence_pmids: string[];
}

export interface TargetRiskRequest {
  disease_name: string;
  target_name: string;
  vertical: Vertical;
}

export interface TargetRiskResponse {
  target: string;
  disease: string;
  pathway_position: string;
  redundancy_level: string;
  historical_failures: HistoricalFailure[];
  biomarker_alignment: string;
  mechanistic_risk_score: number;
  translational_risk_score: number;
  overall_risk_score: number;
  risk_explanation: string;
  citations: string[];
}

// ------------------------------------------------------------------
// API functions
// ------------------------------------------------------------------

export async function generateDiseaseReport(
  payload: DiseaseReportRequest
): Promise<DiseaseReportResponse> {
  const response = await axios.post<DiseaseReportResponse>(
    "/api/dmi/disease-report",
    payload
  );
  return response.data;
}

export async function generateTargetRiskReport(
  payload: TargetRiskRequest
): Promise<TargetRiskResponse> {
  const response = await axios.post<TargetRiskResponse>(
    "/api/dmi/target-risk",
    payload
  );
  return response.data;
}
