import axios from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface QueryRequest {
  question: string;
}

export interface QueryResponse {
  answer: string;
  sources: string[];
}

export async function submitQuery(payload: QueryRequest): Promise<QueryResponse> {
  const response = await axios.post<QueryResponse>(`${API_BASE}/query`, payload);
  return response.data;
}
