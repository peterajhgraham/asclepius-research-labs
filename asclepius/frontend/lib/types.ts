import type { CompareResponse, HypothesisResponse, QueryResponse } from "@/lib/api";
import type { DiseaseReportResponse, TargetRiskResponse } from "@/lib/dmi-api";

export type Mode = "disease-report" | "target-risk" | "standard" | "research" | "compare" | "hypothesis";

export interface Citation {
  text: string;
  score: number;
  rerank_score: number;
  type: string;
  pmid: string;
  source: string;
  content_type?: "text" | "image" | "table";
  image_hash?: string | null;
  image_url?: string | null;
  page?: number | null;
  table_markdown?: string | null;
}

export interface AgentPlannerStep {
  iteration: number;
  thinking?: string;
  tool_calls?: string[];
}

export interface AgentToolCall {
  iteration: number;
  tool: string;
  args: Record<string, unknown>;
}

export interface AgentToolResult {
  iteration: number;
  tool: string;
  result_preview: string;
}

export interface AgentVerification {
  verdict: string;
  confidence: number;
  notes: string;
  revised_answer?: string;
  images_inspected: number;
  cost_usd?: number;
  model_used?: string;
}

export interface AgentDone {
  iterations: number;
  model: string;
  cost_usd: number;
}

export interface AgentState {
  steps: AgentPlannerStep[];
  toolCalls: AgentToolCall[];
  toolResults: AgentToolResult[];
  finalAnswer: string;
  imageHashes: string[];
  verification: AgentVerification | null;
  done: AgentDone | null;
  isStreaming: boolean;
  error: string | null;
}

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
