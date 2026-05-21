import type { Citation } from "@/hooks/useStreamingQuery";
import type { AgentState } from "@/hooks/useAgentStream";
import type { CompareResponse, HypothesisResponse, QueryResponse } from "@/lib/api";
import type { DiseaseReportResponse, TargetRiskResponse } from "@/lib/dmi-api";

export type Mode = "disease-report" | "target-risk" | "standard" | "research" | "compare" | "hypothesis";

export interface UploadedImage {
  base64: string;
  previewUrl: string;
  mediaType: string;
  fileName: string;
}

export interface UploadedPdf {
  file: File;
  fileName: string;
  status: "pending" | "indexing" | "done" | "error";
  message?: string;
}

export interface ConversationEntry {
  id: string;
  question: string;
  mode: Mode;
  response: QueryResponse | null;
  compareResponse: CompareResponse | null;
  hypothesisResponse: HypothesisResponse | null;
  diseaseReportResponse: DiseaseReportResponse | null;
  targetRiskResponse: TargetRiskResponse | null;
  streamedText?: string;
  streamedCitations?: Citation[];
  streamedSources?: string[];
  streamedModel?: string;
  streamedCost?: number;
  agentState?: AgentState;
  imageAnalysis?: string;
  imagePreviewUrl?: string;
  loading: boolean;
  error: string | null;
  timestamp: number;
}

export interface SavedSession {
  id: string;
  title: string;
  mode: Mode;
  entries: Omit<ConversationEntry, "imagePreviewUrl">[];
  createdAt: number;
  updatedAt: number;
}
