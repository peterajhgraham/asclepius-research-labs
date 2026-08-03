// ------------------------------------------------------------------
// Standard query types
// ------------------------------------------------------------------

export interface QueryRequest {
  question: string;
  mode?: "standard" | "hypothesis" | "compare";
  include_pubmed?: boolean;
}

export interface StructuredReasoning {
  summary: string;
  key_entities: string[];
  key_mechanisms: string[];
  pathways: string[];
  therapeutic_targets: string[];
  open_questions: string[];
  genes: string[];
  topic_context: string;
}

export interface PubMedArticle {
  pmid: string;
  title: string;
  abstract: string;
  authors: string[];
  journal: string;
  year: string;
  doi: string;
  citation: string;
}

export interface CausalDownstream {
  node: string;
  score: number;
}

export interface GraphContext {
  nodes: any[];
  edges: any[];
  node_count: number;
  edge_count: number;
  causal_downstream?: CausalDownstream[];
}

export interface RetrievedProposition {
  text: string;
  score: number;
  rerank_score: number;
  metadata: Record<string, unknown>;
}

export interface QueryResponse {
  answer: string;
  sources: string[];
  reasoning: StructuredReasoning;
  pubmed_articles?: PubMedArticle[];
  graph_context?: GraphContext | null;
  retrieved_propositions?: RetrievedProposition[];
  model_used?: string;
  cost_usd?: number;
  image_analysis?: string;
}

export interface ImageQueryRequest {
  question: string;
  image_base64: string;
  media_type: string;
  include_pubmed?: boolean;
}

// ------------------------------------------------------------------
// Comparative analysis types
// ------------------------------------------------------------------

export interface CompareRequest {
  disease_a: string;
  disease_b: string;
}

export interface DiseaseProfile {
  disease_name: string;
  disease_id: string;
  description: string;
  prevalence: string;
  pathogenic_mechanisms: string[];
  key_cell_types: string[];
  associated_genes: { gene: string; score: number }[];
  hla_associations: string[];
  autoantibodies: string[];
  cytokines: string[];
  pathways: any[];
  therapeutics: any[];
  approved_therapies: any[];
  cytokine_network?: Array<{ source: string; target: string; edge_type: string; description: string }>;
}

export interface Overlaps {
  shared_genes: string[];
  unique_genes_a: string[];
  unique_genes_b: string[];
  shared_cell_types: string[];
  unique_cell_types_a: string[];
  unique_cell_types_b: string[];
  shared_cytokines: string[];
  unique_cytokines_a: string[];
  unique_cytokines_b: string[];
  shared_pathways: string[];
  unique_pathways_a: string[];
  unique_pathways_b: string[];
  shared_therapeutics: string[];
  unique_therapeutics_a: string[];
  unique_therapeutics_b: string[];
  shared_mechanisms: string[];
  unique_mechanisms_a: string[];
  unique_mechanisms_b: string[];
}

export interface CompareResponse {
  disease_a: DiseaseProfile;
  disease_b: DiseaseProfile;
  overlaps: Overlaps;
  similarity_score: number;
  summary: string;
}

// ------------------------------------------------------------------
// Hypothesis generator types
// ------------------------------------------------------------------

export interface HypothesisRequest {
  topic: string;
  max_hypotheses?: number;
}

export interface ExperimentalDesign {
  model: string;
  intervention: string;
  readouts: string[];
  controls: string[];
  timeline: string;
}

export interface Hypothesis {
  hypothesis: string;
  category: string;
  rationale: string;
  experimental_design: ExperimentalDesign;
  biomarkers: string[];
  confounders: string[];
  confidence: string;
  supporting_evidence: string[];
}

export interface HypothesisResponse {
  topic: string;
  hypotheses: Hypothesis[];
  context: {
    diseases_matched: string[];
    pathways_matched: string[];
    therapeutics_matched: string[];
    cytokine_edges_found: number;
    kb_entries_matched: number;
  };
  total_generated: number;
}

// ------------------------------------------------------------------
// Dossier types
// ------------------------------------------------------------------

export interface DossierSummary {
  id: string;
  name: string;
  description: string;
  tags: string[];
  entry_count: number;
  created_at: string;
  updated_at: string;
}

export interface DossierEntry {
  id: string;
  query: string;
  response: any;
  notes: string;
  created_at: string;
}

export interface Dossier {
  id: string;
  name: string;
  description: string;
  tags: string[];
  entry_count: number;
  entries: DossierEntry[];
  created_at: string;
  updated_at: string;
}

export interface DossierInsights {
  total_queries: number;
  queries: string[];
  key_entities: string[];
  key_mechanisms: string[];
  pathways: string[];
  therapeutic_targets: string[];
  genes: string[];
  hypotheses: string[];
  sources: string[];
  notes: { entry_id: string; query: string; notes: string }[];
}

// ------------------------------------------------------------------
// Fetch wrapper
// ------------------------------------------------------------------

async function apiFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const { headers: initHeaders, ...restInit } = init ?? {};
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...initHeaders },
    ...restInit,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    let detail = text;
    try {
      const json = JSON.parse(text);
      detail = json.detail ?? json.error ?? text;
    } catch {
      // use raw text
    }
    throw Object.assign(new Error(detail || `HTTP ${res.status}`), {
      response: { data: { detail } },
    });
  }
  if (res.status === 204 || res.headers.get("content-length") === "0") {
    return undefined as unknown as T;
  }
  return res.json() as Promise<T>;
}

// ------------------------------------------------------------------
// API functions
// ------------------------------------------------------------------

export async function submitQuery(payload: QueryRequest): Promise<QueryResponse> {
  return apiFetch<QueryResponse>("/api/query", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function submitImageQuery(payload: ImageQueryRequest): Promise<QueryResponse> {
  return apiFetch<QueryResponse>("/api/query/images", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function compareDiseases(payload: CompareRequest): Promise<CompareResponse> {
  return apiFetch<CompareResponse>("/api/compare", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function generateHypotheses(payload: HypothesisRequest): Promise<HypothesisResponse> {
  return apiFetch<HypothesisResponse>("/api/hypotheses", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// Dossier operations
export async function createDossier(
  name: string,
  description?: string,
  tags?: string[],
): Promise<DossierSummary> {
  return apiFetch<DossierSummary>("/api/dossiers", {
    method: "POST",
    body: JSON.stringify({ name, description: description ?? "", tags: tags ?? [] }),
  });
}

export async function listDossiers(): Promise<{ dossiers: DossierSummary[] }> {
  return apiFetch<{ dossiers: DossierSummary[] }>("/api/dossiers");
}

export async function getDossier(dossierId: string): Promise<Dossier> {
  return apiFetch<Dossier>(`/api/dossiers/${dossierId}`);
}

export async function getDossierInsights(dossierId: string): Promise<DossierInsights> {
  return apiFetch<DossierInsights>(`/api/dossiers/${dossierId}/insights`);
}
