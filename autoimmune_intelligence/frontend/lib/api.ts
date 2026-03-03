import axios from "axios";

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
  key_cells: string[];
  key_cytokines: string[];
  pathways: string[];
  therapeutic_targets: string[];
  open_questions: string[];
  genes: string[];
  disease_context: string;
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

export interface QueryResponse {
  answer: string;
  sources: string[];
  reasoning: StructuredReasoning;
  pubmed_articles?: PubMedArticle[];
  graph_context?: GraphContext | null;
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
// PubMed search types
// ------------------------------------------------------------------

export interface PubMedSearchRequest {
  query: string;
  max_results?: number;
  autoimmune_enriched?: boolean;
}

export interface PubMedSearchResponse {
  query: string;
  articles: PubMedArticle[];
  interactions: any[];
  total_found: number;
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
  key_cells: string[];
  key_cytokines: string[];
  pathways: string[];
  therapeutic_targets: string[];
  genes: string[];
  hypotheses: string[];
  sources: string[];
  notes: { entry_id: string; query: string; notes: string }[];
}

// ------------------------------------------------------------------
// API functions
// ------------------------------------------------------------------

export async function submitQuery(payload: QueryRequest): Promise<QueryResponse> {
  const response = await axios.post<QueryResponse>("/api/query", payload);
  return response.data;
}

export async function compareDiseases(payload: CompareRequest): Promise<CompareResponse> {
  const response = await axios.post<CompareResponse>("/api/compare", payload);
  return response.data;
}

export async function generateHypotheses(payload: HypothesisRequest): Promise<HypothesisResponse> {
  const response = await axios.post<HypothesisResponse>("/api/hypotheses", payload);
  return response.data;
}

export async function searchPubMed(payload: PubMedSearchRequest): Promise<PubMedSearchResponse> {
  const response = await axios.post<PubMedSearchResponse>("/api/pubmed/search", payload);
  return response.data;
}

export async function listDiseases(): Promise<{ diseases: string[]; count: number }> {
  const response = await axios.get("/api/diseases");
  return response.data;
}

// Dossier operations
export async function createDossier(name: string, description?: string, tags?: string[]): Promise<DossierSummary> {
  const response = await axios.post("/api/dossiers", { name, description: description || "", tags: tags || [] });
  return response.data;
}

export async function listDossiers(): Promise<{ dossiers: DossierSummary[] }> {
  const response = await axios.get("/api/dossiers");
  return response.data;
}

export async function getDossier(dossierId: string): Promise<Dossier> {
  const response = await axios.get(`/api/dossiers/${dossierId}`);
  return response.data;
}

export async function addToDossier(dossierId: string, query: string, responseData: any, notes?: string): Promise<DossierEntry> {
  const response = await axios.post(`/api/dossiers/${dossierId}/entries`, {
    query,
    response: responseData,
    notes: notes || "",
  });
  return response.data;
}

export async function getDossierInsights(dossierId: string): Promise<DossierInsights> {
  const response = await axios.get(`/api/dossiers/${dossierId}/insights`);
  return response.data;
}

export async function deleteDossier(dossierId: string): Promise<void> {
  await axios.delete(`/api/dossiers/${dossierId}`);
}
