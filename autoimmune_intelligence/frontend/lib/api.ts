import axios from "axios";

export interface QueryRequest {
  question: string;
}

export interface StructuredReasoning {
  summary: string;
  key_cells: string[];
  key_cytokines: string[];
  pathways: string[];
  therapeutic_targets: string[];
  open_questions: string[];
  genes: string[];
  disease_context: string;
}

export interface QueryResponse {
  answer: string;
  sources: string[];
  reasoning: StructuredReasoning;
}

export async function submitQuery(payload: QueryRequest): Promise<QueryResponse> {
  const response = await axios.post<QueryResponse>("/api/query", payload);
  return response.data;
}
