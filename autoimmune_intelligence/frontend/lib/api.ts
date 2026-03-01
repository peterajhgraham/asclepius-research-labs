import axios from "axios";

export interface QueryRequest {
  question: string;
}

export interface QueryResponse {
  answer: string;
  sources: string[];
}

export async function submitQuery(payload: QueryRequest): Promise<QueryResponse> {
  const response = await axios.post<QueryResponse>("/api/query", payload);
  return response.data;
}
