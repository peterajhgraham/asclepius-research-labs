"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type DragEvent,
} from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  compareDiseases,
  generateHypotheses,
  submitImageQuery,
  submitQuery,
  type CompareResponse,
  type HypothesisResponse,
  type QueryResponse,
} from "@/lib/api";
import {
  generateDiseaseReport,
  generateTargetRiskReport,
  type DiseaseReportResponse,
  type TargetRiskResponse,
} from "@/lib/dmi-api";
import { useStreamingQuery, type Citation } from "@/hooks/useStreamingQuery";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import AuthHeader from "@/components/AuthHeader";
import CitationPanel from "@/components/CitationPanel";
import CompareCard from "@/components/CompareCard";
import DiseaseReportCard from "@/components/DiseaseReportCard";
import HypothesisCard from "@/components/HypothesisCard";
import ResponseCard from "@/components/ResponseCard";
import StreamingResponse from "@/components/StreamingResponse";
import TargetRiskCard from "@/components/TargetRiskCard";

// ------------------------------------------------------------------
// Types
// ------------------------------------------------------------------
type Mode = "disease-report" | "target-risk" | "standard" | "compare" | "hypothesis";

interface UploadedImage {
  base64: string;
  previewUrl: string;
  mediaType: string;
  fileName: string;
}

interface UploadedPdf {
  file: File;
  fileName: string;
  status: "pending" | "indexing" | "done" | "error";
  message?: string;
}

interface ConversationEntry {
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
  imageAnalysis?: string;
  imagePreviewUrl?: string;
  loading: boolean;
  error: string | null;
  timestamp: number;
}

interface SavedSession {
  id: string;
  title: string;
  mode: Mode;
  entries: ConversationEntry[];
  createdAt: number;
  updatedAt: number;
}

// ------------------------------------------------------------------
// Constants
// ------------------------------------------------------------------
const EXAMPLE_PROMPTS: Record<Mode, string[]> = {
  "disease-report": [
    "Alzheimer's disease",
    "Non-small cell lung cancer",
    "Rheumatoid arthritis",
    "Parkinson's disease",
    "Type 2 diabetes",
    "Glioblastoma",
  ],
  "target-risk": [
    "BACE1 in Alzheimer's disease",
    "PD-1 in Non-small cell lung cancer",
    "TNF-alpha in Rheumatoid arthritis",
    "KRAS in Colorectal cancer",
    "LRRK2 in Parkinson's disease",
    "EGFR in Glioblastoma",
  ],
  standard: [
    "mRNA vaccine immune response mechanisms",
    "Tau aggregation in Alzheimer's disease",
    "CRISPR off-target effects in gene therapy",
    "Gut microbiome and metabolic syndrome",
    "Neuroinflammation in Parkinson's disease",
    "Climate change effects on vector-borne diseases",
  ],
  compare: [
    "Alzheimer's disease vs Parkinson's disease",
    "Rheumatoid arthritis vs Lupus",
    "Type 1 vs Type 2 diabetes",
    "Crohn's disease vs Ulcerative colitis",
  ],
  hypothesis: [
    "Tau propagation in Alzheimer's disease",
    "JAK-STAT pathway in rheumatoid arthritis",
    "Ferroptosis in cancer therapy resistance",
    "Gut-brain axis in Parkinson's disease",
  ],
};

const MODE_CONFIG: Record<Mode, { label: string; description: string; group: "dmi" | "legacy" }> = {
  "disease-report": { label: "Mechanism Report", description: "Map disease biology from literature",        group: "dmi" },
  "target-risk":    { label: "Target Risk",       description: "Score therapeutic target tractability",     group: "dmi" },
  standard:         { label: "Analyze",           description: "Real-time scientific reasoning",            group: "legacy" },
  compare:          { label: "Compare",           description: "Side-by-side biological comparison",        group: "legacy" },
  hypothesis:       { label: "Hypothesize",       description: "Generate testable experimental hypotheses", group: "legacy" },
};

const ALL_MODES: Mode[] = ["disease-report", "target-risk", "standard", "compare", "hypothesis"];
const LS_KEY = "asclepius_sessions_v2";

// ------------------------------------------------------------------
// Helpers
// ------------------------------------------------------------------
function genId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}
function loadSessions(): SavedSession[] {
  if (typeof window === "undefined") return [];
  try { return JSON.parse(localStorage.getItem(LS_KEY) || "[]"); } catch { return []; }
}
function persistSessions(sessions: SavedSession[]) {
  if (typeof window === "undefined") return;
  localStorage.setItem(LS_KEY, JSON.stringify(sessions));
}
function sessionTitle(entries: ConversationEntry[]): string {
  if (!entries.length) return "New session";
  const first = entries[0].question;
  return first.length > 40 ? first.slice(0, 40) + "…" : first;
}
function pmidToUrl(pmid: string): string {
  return `https://pubmed.ncbi.nlm.nih.gov/${pmid}`;
}
function modelDisplayName(model: string): string {
  if (model.includes("haiku")) return "Claude Haiku";
  if (model.includes("sonnet")) return "Claude Sonnet";
  if (model.includes("opus")) return "Claude Opus";
  return "Claude";
}

// ------------------------------------------------------------------
// Claude attribution badge
// ------------------------------------------------------------------
function ClaudeBadge({
  model,
  cost,
  isStreaming = false,
  sourceCount = 0,
}: {
  model?: string;
  cost?: number;
  isStreaming?: boolean;
  sourceCount?: number;
}) {
  const name = model ? modelDisplayName(model) : "Claude";
  return (
    <div className="flex items-center gap-2 text-[11px] text-muted-light">
      {/* Anthropic-style mark */}
      <div className="flex items-center gap-1.5 rounded-md border border-surface-3 bg-surface-1 px-2 py-1 font-medium">
        <span className="h-1.5 w-1.5 rounded-full bg-accent-400" />
        <span className="font-mono tracking-tight">{isStreaming ? "Claude" : name}</span>
        {!isStreaming && cost != null && cost > 0 && (
          <span className="text-muted font-mono opacity-70 ml-0.5">${cost.toFixed(5)}</span>
        )}
      </div>
      {isStreaming ? (
        <span className="flex items-center gap-1 text-muted">
          <span className="flex gap-0.5">
            {[0, 1, 2].map((i) => (
              <span key={i} className="h-1 w-1 rounded-full bg-accent-500 animate-pulse-dot"
                style={{ animationDelay: `${i * 0.16}s` }} />
            ))}
          </span>
          Generating…
        </span>
      ) : sourceCount > 0 ? (
        <span className="text-muted">{sourceCount} source{sourceCount !== 1 ? "s" : ""} retrieved</span>
      ) : null}
    </div>
  );
}

// ------------------------------------------------------------------
// Mode Switcher — clean flat tabs
// ------------------------------------------------------------------
function ModeSwitcher({
  mode,
  onModeChange,
}: {
  mode: Mode;
  onModeChange: (m: Mode) => void;
}) {
  return (
    <div className="flex items-center gap-0.5 rounded-lg border border-surface-3 bg-surface-1 p-0.5">
      {ALL_MODES.map((m) => {
        const active = mode === m;
        return (
          <div key={m} className="relative group">
            <button
              onClick={() => onModeChange(m)}
              className={`
                relative rounded-md px-3 py-1.5 text-xs font-medium whitespace-nowrap transition-all
                ${active
                  ? "bg-surface-3 text-gray-100 shadow-sm"
                  : "text-muted hover:text-gray-300"
                }
              `}
            >
              {MODE_CONFIG[m].label}
            </button>
            <div className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 opacity-0 group-hover:opacity-100 transition-opacity duration-150">
              <div className="rounded-md border border-surface-3 bg-surface-0 px-2.5 py-1.5 text-[11px] text-gray-400 whitespace-nowrap shadow-xl">
                {MODE_CONFIG[m].description}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ------------------------------------------------------------------
// Sidebar
// ------------------------------------------------------------------
function Sidebar({
  sessions, activeSessionId, onSelectSession, onNewSession, onDeleteSession,
  sidebarOpen, onToggleSidebar,
}: {
  sessions: SavedSession[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
  onDeleteSession: (id: string) => void;
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
}) {
  return (
    <>
      {sidebarOpen && (
        <div className="fixed inset-0 z-30 bg-black/40 lg:hidden" onClick={onToggleSidebar} />
      )}
      <aside className={`fixed top-0 left-0 z-40 h-full w-60 border-r border-surface-3 bg-surface-1 flex flex-col transition-transform duration-200 lg:relative lg:translate-x-0 ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}`}>
        {/* Sidebar header */}
        <div className="flex items-center justify-between border-b border-surface-3 px-4 py-3.5">
          <button onClick={onNewSession} className="flex items-center gap-2 group">
            <span className="text-sm font-semibold tracking-tight text-gray-100 group-hover:text-accent-400 transition">
              Asclepius
            </span>
            <span className="rounded-md bg-accent-600/15 px-1.5 py-0.5 text-[10px] font-medium text-accent-400 tracking-wide">
              Research
            </span>
          </button>
          <button
            onClick={onNewSession}
            className="flex h-7 w-7 items-center justify-center rounded-md text-muted hover:bg-surface-2 hover:text-gray-300 transition"
            title="New session"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
            </svg>
          </button>
        </div>

        {/* Session list */}
        <div className="flex-1 overflow-y-auto py-1.5">
          {sessions.length === 0 && (
            <p className="px-4 py-8 text-center text-xs text-muted leading-relaxed">
              No sessions yet.<br />Start a query to begin.
            </p>
          )}
          {sessions.map((session) => (
            <div
              key={session.id}
              className={`group mx-2 mb-0.5 flex items-center gap-2 rounded-md px-3 py-2 cursor-pointer transition ${
                activeSessionId === session.id
                  ? "bg-surface-2 text-gray-200"
                  : "text-muted hover:bg-surface-2/60 hover:text-gray-300"
              }`}
              onClick={() => onSelectSession(session.id)}
            >
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium truncate leading-snug">{session.title}</p>
                <p className="text-[10px] text-muted mt-0.5 font-mono">
                  {MODE_CONFIG[session.mode]?.label} · {session.entries.length}q
                </p>
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); onDeleteSession(session.id); }}
                className="shrink-0 flex h-5 w-5 items-center justify-center rounded opacity-0 group-hover:opacity-100 hover:bg-red-500/15 hover:text-red-400 transition"
                title="Delete"
              >
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
          ))}
        </div>

        <div className="border-t border-surface-3 px-4 py-2.5">
          <p className="text-[10px] text-muted font-mono">sessions · local storage</p>
        </div>
      </aside>
    </>
  );
}

// ------------------------------------------------------------------
// Image Analysis Card
// ------------------------------------------------------------------
function ImageAnalysisCard({ analysis, previewUrl }: { analysis: string; previewUrl?: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="mt-4 rounded-lg border border-surface-3 bg-surface-1 overflow-hidden"
    >
      <div className="flex items-center gap-2 border-b border-surface-3 px-4 py-2.5">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="text-accent-400 shrink-0">
          <rect x="3" y="3" width="18" height="18" rx="2" /><circle cx="8.5" cy="8.5" r="1.5" /><polyline points="21 15 16 10 5 21" />
        </svg>
        <span className="text-xs font-semibold text-gray-200 tracking-tight">Visual Analysis</span>
        <span className="ml-auto">
          <ClaudeBadge model="sonnet" />
        </span>
      </div>
      <div className="p-4 flex gap-4">
        {previewUrl && (
          <img src={previewUrl} alt="Uploaded" className="h-24 w-24 shrink-0 rounded-md object-cover border border-surface-3" />
        )}
        <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">{analysis}</p>
      </div>
    </motion.div>
  );
}

// ------------------------------------------------------------------
// FrozenStreamEntry — completed streamed response
// ------------------------------------------------------------------
function FrozenStreamEntry({ entry, onShowCitations }: {
  entry: ConversationEntry;
  onShowCitations: (citations: Citation[]) => void;
}) {
  const [sourcesExpanded, setSourcesExpanded] = useState(false);
  const sources = entry.streamedSources ?? [];
  const displayed = sourcesExpanded ? sources : sources.slice(0, 5);

  return (
    <div className="rounded-lg border border-surface-3 bg-surface-1 overflow-hidden">
      {/* Response header — Claude attribution */}
      <div className="flex items-center gap-3 border-b border-surface-3 px-4 py-2.5">
        <ClaudeBadge
          model={entry.streamedModel}
          cost={entry.streamedCost}
          sourceCount={entry.streamedCitations?.length ?? 0}
        />
        {(entry.streamedCitations?.length ?? 0) > 0 && (
          <button
            onClick={() => onShowCitations(entry.streamedCitations!)}
            className="ml-auto flex items-center gap-1.5 rounded-md border border-surface-3 px-2 py-1 text-[11px] text-muted hover:text-gray-300 hover:border-accent-500/30 transition"
          >
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
            {entry.streamedCitations!.length} retrieved
          </button>
        )}
      </div>

      {/* Answer body */}
      <div className="px-5 py-4">
        <div className="prose prose-invert prose-sm max-w-none
          prose-headings:text-gray-100 prose-headings:font-semibold prose-headings:tracking-tight
          prose-p:text-gray-300 prose-p:leading-relaxed
          prose-strong:text-gray-100
          prose-code:text-accent-300 prose-code:bg-surface-2 prose-code:rounded prose-code:px-1 prose-code:text-xs prose-code:font-mono
          prose-ul:text-gray-300 prose-li:my-0.5
          prose-h2:text-base prose-h3:text-sm">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{entry.streamedText || ""}</ReactMarkdown>
        </div>
      </div>

      {/* Sources footer */}
      {sources.length > 0 && (
        <div className="border-t border-surface-3 bg-surface-0/40 px-4 py-2.5 flex flex-wrap items-center gap-1.5">
          {displayed.map((s, i) => {
            const pmidMatch = s.match(/PMID:\s*(\d+)/i);
            return pmidMatch ? (
              <a key={i} href={pmidToUrl(pmidMatch[1])} target="_blank" rel="noopener noreferrer"
                className="rounded px-1.5 py-0.5 text-[10px] font-mono border border-accent-700/40 bg-accent-900/20 text-accent-400 hover:text-accent-300 transition">
                {s}
              </a>
            ) : (
              <span key={i} className="rounded px-1.5 py-0.5 text-[10px] font-mono border border-surface-3 bg-surface-2 text-muted-light">{s}</span>
            );
          })}
          {sources.length > 5 && (
            <button onClick={() => setSourcesExpanded(!sourcesExpanded)} className="text-[10px] text-muted hover:text-gray-300 transition">
              {sourcesExpanded ? "show less" : `+${sources.length - 5} more`}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------------
// AI Response Wrapper — wraps non-streaming cards with Claude badge
// ------------------------------------------------------------------
function AiResponseWrapper({ children, label }: { children: React.ReactNode; label: string }) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <ClaudeBadge />
        <span className="text-[11px] text-muted">{label}</span>
      </div>
      {children}
    </div>
  );
}

// ------------------------------------------------------------------
// Landing Page
// ------------------------------------------------------------------
const HOW_IT_WORKS = [
  {
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" />
      </svg>
    ),
    title: "Retrieve",
    desc: "BM25 + semantic search across curated knowledge bases and live PubMed",
  },
  {
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <path d="M12 2a10 10 0 1 0 10 10" /><path d="M12 6v6l4 2" />
      </svg>
    ),
    title: "Synthesize",
    desc: "Claude grounds answers in retrieved propositions from primary literature",
  },
  {
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
      </svg>
    ),
    title: "Multimodal",
    desc: "Upload images or PDFs — figures are captioned and indexed for retrieval",
  },
];

// ------------------------------------------------------------------
// PDF ingest helper
// ------------------------------------------------------------------
async function ingestDocument(file: File): Promise<{ propositions_indexed: number; images_captioned: number }> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch("/api/ingest", { method: "POST", body: formData });
  if (!res.ok) throw new Error(`Ingest failed: ${res.status}`);
  return res.json();
}

// ------------------------------------------------------------------
// Main Page
// ------------------------------------------------------------------
export default function HomePage() {
  const [question, setQuestion] = useState("");
  const [diseaseB, setDiseaseB] = useState("");
  const [targetName, setTargetName] = useState("");
  const [vertical, setVertical] = useState<string>("general");
  const [entries, setEntries] = useState<ConversationEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<Mode>("disease-report");
  const [includePubmed, setIncludePubmed] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [showCitationPanel, setShowCitationPanel] = useState(false);
  const [panelCitations, setPanelCitations] = useState<Citation[]>([]);
  const [uploadedImage, setUploadedImage] = useState<UploadedImage | null>(null);
  const [uploadedPdf, setUploadedPdf] = useState<UploadedPdf | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const pdfInputRef = useRef<HTMLInputElement>(null);

  const streaming = useStreamingQuery();
  const [streamingEntryId, setStreamingEntryId] = useState<string | null>(null);

  const [sessions, setSessions] = useState<SavedSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);

  useEffect(() => { setSessions(loadSessions()); }, []);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [entries, streaming.text]);

  useEffect(() => {
    if (streamingEntryId && streaming.done) {
      setEntries((prev) =>
        prev.map((e) =>
          e.id === streamingEntryId
            ? {
                ...e,
                loading: false,
                streamedText: streaming.text,
                streamedCitations: streaming.citations,
                streamedSources: streaming.done?.sources ?? [],
                streamedModel: streaming.done?.model ?? "",
                streamedCost: streaming.done?.cost ?? 0,
              }
            : e,
        ),
      );
      setStreamingEntryId(null);
    }
  }, [streaming.done, streamingEntryId, streaming.text, streaming.citations]);

  useEffect(() => {
    if (streamingEntryId && streaming.error) {
      setEntries((prev) =>
        prev.map((e) =>
          e.id === streamingEntryId
            ? { ...e, loading: false, error: streaming.error }
            : e,
        ),
      );
      setStreamingEntryId(null);
      setLoading(false);
    }
  }, [streaming.error, streamingEntryId]);

  const saveCurrentSession = useCallback(() => {
    if (!entries.length) return;
    setSessions((prev) => {
      let updated: SavedSession[];
      if (activeSessionId) {
        updated = prev.map((s) =>
          s.id === activeSessionId
            ? { ...s, entries, title: sessionTitle(entries), mode, updatedAt: Date.now() }
            : s,
        );
      } else {
        const newId = genId();
        updated = [{ id: newId, title: sessionTitle(entries), mode, entries, createdAt: Date.now(), updatedAt: Date.now() }, ...prev];
        setActiveSessionId(newId);
      }
      persistSessions(updated);
      return updated;
    });
  }, [entries, activeSessionId, mode]);

  useEffect(() => {
    if (entries.length > 0 && entries.some((e) => !e.loading)) {
      saveCurrentSession();
    }
  }, [entries, saveCurrentSession]);

  function handleNewSession() {
    streaming.reset();
    setStreamingEntryId(null);
    setEntries([]);
    setActiveSessionId(null);
    setQuestion("");
    setDiseaseB("");
    setTargetName("");
    setMode("disease-report");
    setVertical("general");
    setSidebarOpen(false);
    setShowCitationPanel(false);
    setLoading(false);
    setUploadedImage(null);
    setUploadedPdf(null);
  }

  function handleSelectSession(sessionId: string) {
    const session = sessions.find((s) => s.id === sessionId);
    if (!session) return;
    setEntries(session.entries);
    setActiveSessionId(sessionId);
    setMode(session.mode);
    setSidebarOpen(false);
  }

  function handleDeleteSession(sessionId: string) {
    setSessions((prev) => {
      const updated = prev.filter((s) => s.id !== sessionId);
      persistSessions(updated);
      return updated;
    });
    if (activeSessionId === sessionId) handleNewSession();
  }

  function handleShowCitations(citations: Citation[]) {
    setPanelCitations(citations);
    setShowCitationPanel(true);
  }

  // ------------------------------------------------------------------
  // Image upload
  // ------------------------------------------------------------------
  function processImageFile(file: File) {
    if (!file.type.startsWith("image/")) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      const dataUrl = e.target?.result as string;
      const base64 = dataUrl.split(",")[1];
      setUploadedImage({ base64, previewUrl: dataUrl, mediaType: file.type, fileName: file.name });
    };
    reader.readAsDataURL(file);
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (!file) return;
    if (file.type.startsWith("image/")) processImageFile(file);
    else if (file.type === "application/pdf") handlePdfSelected(file);
  }

  function handleDragOver(e: DragEvent<HTMLDivElement>) { e.preventDefault(); setIsDragging(true); }
  function handleDragLeave() { setIsDragging(false); }

  // ------------------------------------------------------------------
  // PDF upload / ingest
  // ------------------------------------------------------------------
  async function handlePdfSelected(file: File) {
    setUploadedPdf({ file, fileName: file.name, status: "indexing" });
    try {
      const result = await ingestDocument(file);
      setUploadedPdf((prev) => prev ? {
        ...prev,
        status: "done",
        message: `${result.propositions_indexed} propositions indexed · ${result.images_captioned} figures captioned`,
      } : null);
    } catch {
      setUploadedPdf((prev) => prev ? { ...prev, status: "error", message: "Failed to index document" } : null);
    }
  }

  // ------------------------------------------------------------------
  // Submit
  // ------------------------------------------------------------------
  async function handleSubmit(e?: FormEvent<HTMLFormElement>) {
    if (e) e.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || loading) return;

    const idx = entries.length;
    let displayQ = trimmed;
    if (mode === "disease-report") displayQ = `${trimmed} [${vertical}]`;
    else if (mode === "target-risk") displayQ = `${targetName.trim()} in ${trimmed}`;
    else if (mode === "compare" && diseaseB.trim()) displayQ = `${trimmed} vs ${diseaseB.trim()}`;

    const capturedImage = uploadedImage;

    const entry: ConversationEntry = {
      id: genId(),
      question: displayQ,
      mode,
      response: null,
      compareResponse: null,
      hypothesisResponse: null,
      diseaseReportResponse: null,
      targetRiskResponse: null,
      imagePreviewUrl: capturedImage?.previewUrl,
      loading: true,
      error: null,
      timestamp: Date.now(),
    };

    setEntries((prev) => [...prev, entry]);
    setQuestion("");
    setDiseaseB("");
    setTargetName("");
    setUploadedImage(null);
    setLoading(true);

    try {
      if (capturedImage) {
        const result = await submitImageQuery({
          question: trimmed,
          image_base64: capturedImage.base64,
          media_type: capturedImage.mediaType,
          include_pubmed: includePubmed,
        });
        setEntries((prev) =>
          prev.map((e, i) =>
            i === idx ? { ...e, response: result, imageAnalysis: result.image_analysis ?? undefined, loading: false } : e,
          ),
        );
        setLoading(false);
        return;
      }

      if (mode === "standard") {
        streaming.reset();
        setStreamingEntryId(entry.id);
        streaming.stream(trimmed);
        setLoading(false);
        return;
      }

      if (mode === "disease-report") {
        const result = await generateDiseaseReport({ disease_name: trimmed, vertical });
        setEntries((prev) => prev.map((e, i) => i === idx ? { ...e, diseaseReportResponse: result, loading: false } : e));
      } else if (mode === "target-risk") {
        const result = await generateTargetRiskReport({ disease_name: trimmed, target_name: targetName.trim(), vertical });
        setEntries((prev) => prev.map((e, i) => i === idx ? { ...e, targetRiskResponse: result, loading: false } : e));
      } else if (mode === "compare") {
        const result = await compareDiseases({ disease_a: trimmed, disease_b: diseaseB.trim() || trimmed });
        setEntries((prev) => prev.map((e, i) => i === idx ? { ...e, compareResponse: result, loading: false } : e));
      } else if (mode === "hypothesis") {
        const result = await generateHypotheses({ topic: trimmed });
        setEntries((prev) => prev.map((e, i) => i === idx ? { ...e, hypothesisResponse: result, loading: false } : e));
      }
    } catch (err: unknown) {
      let detail = "Unable to reach the analysis service.";
      if (err && typeof err === "object" && "response" in err) {
        const res = (err as { response?: { data?: { detail?: string; error?: string } } }).response;
        if (res?.data?.detail) detail = res.data.detail;
        else if (res?.data?.error) detail = res.data.error;
      }
      setEntries((prev) => prev.map((e, i) => i === idx ? { ...e, error: detail, loading: false } : e));
    } finally {
      setLoading(false);
    }
  }

  const isEmpty = entries.length === 0;
  const examples = EXAMPLE_PROMPTS[mode];
  const isDmiMode = mode === "disease-report" || mode === "target-risk";
  const isLoading = loading || streaming.isStreaming;

  function handleExampleClick(example: string) {
    if (mode === "compare") { const p = example.split(" vs "); setQuestion(p[0] || example); setDiseaseB(p[1] || ""); }
    else if (mode === "target-risk") { const p = example.split(" in "); setTargetName(p[0] || ""); setQuestion(p[1] || example); }
    else setQuestion(example);
  }

  // Input class shared by all text inputs in the bar
  const inputCls = "h-11 flex-1 min-w-0 rounded-lg border border-surface-3 bg-surface-1/80 px-3.5 text-sm text-gray-100 placeholder-muted outline-none transition focus:border-accent-500/50 focus:ring-1 focus:ring-accent-500/20 disabled:opacity-40 font-sans";

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------
  return (
    <div
      className="flex h-screen bg-surface-0 overflow-hidden"
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
    >
      {/* Drag overlay */}
      <AnimatePresence>
        {isDragging && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-surface-0/80 backdrop-blur-sm border-2 border-dashed border-accent-500/40"
          >
            <div className="text-center">
              <p className="text-lg font-semibold text-gray-200">Drop to attach</p>
              <p className="text-sm text-muted mt-1">Images · PDF documents</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <Sidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        onDeleteSession={handleDeleteSession}
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
      />

      <main className="flex flex-1 min-w-0 flex-col">
        {/* Top bar */}
        <header className="sticky top-0 z-20 border-b border-surface-3 bg-surface-0/80 backdrop-blur-md">
          <div className="flex items-center justify-between px-4 py-2.5 sm:px-5">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="flex h-8 w-8 items-center justify-center rounded-md text-muted hover:bg-surface-2 hover:text-gray-300 transition lg:hidden"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            </button>
            <div className="hidden lg:block" />
            <AuthHeader />
          </div>
        </header>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">

          {/* Landing */}
          {isEmpty && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
              className="mx-auto flex max-w-2xl flex-col items-center px-6 pt-16 pb-10 sm:pt-20"
            >
              <h1 className="text-2xl font-semibold tracking-tight text-gray-100 sm:text-3xl text-center">
                Asclepius Research Labs
              </h1>
              <p className="mt-2.5 text-center text-sm text-muted max-w-md leading-relaxed">
                Scientific research intelligence powered by Claude. Query any domain: mechanism mapping, target risk assessment, hypothesis generation.
              </p>

              {/* Powered by Claude badge */}
              <div className="mt-5 flex items-center gap-2">
                <ClaudeBadge />
                <span className="text-xs text-muted">· Hybrid RAG · Live PubMed · Multimodal</span>
              </div>

              {/* Mode switcher */}
              <div className="mt-8">
                <ModeSwitcher mode={mode} onModeChange={setMode} />
              </div>

              {/* Example chips */}
              <div className="mt-5 flex flex-wrap gap-2 justify-center">
                {examples.map((example) => (
                  <motion.button
                    key={example}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => handleExampleClick(example)}
                    className="rounded-md border border-surface-3 bg-surface-1 px-3.5 py-1.5 text-xs text-muted hover:border-surface-4 hover:bg-surface-2 hover:text-gray-300 transition"
                  >
                    {example}
                  </motion.button>
                ))}
              </div>

              {/* How it works */}
              <div className="mt-12 w-full">
                <div className="flex items-center gap-3 mb-4">
                  <div className="h-px flex-1 bg-surface-3" />
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-muted font-mono">How it works</p>
                  <div className="h-px flex-1 bg-surface-3" />
                </div>
                <div className="grid grid-cols-3 gap-3">
                  {HOW_IT_WORKS.map((step, i) => (
                    <motion.div
                      key={step.title}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.1 + i * 0.07 }}
                      className="rounded-lg border border-surface-3 bg-surface-1 p-4"
                    >
                      <div className="mb-2 text-accent-400">{step.icon}</div>
                      <p className="text-xs font-semibold text-gray-200 mb-1">{step.title}</p>
                      <p className="text-[11px] text-muted leading-relaxed">{step.desc}</p>
                    </motion.div>
                  ))}
                </div>
              </div>
            </motion.div>
          )}

          {/* Results */}
          {!isEmpty && (
            <div className="mx-auto max-w-3xl px-4 py-8 space-y-8 sm:px-6">
              {entries.map((entry) => {
                const isCurrentlyStreaming = entry.id === streamingEntryId;
                return (
                  <motion.div
                    key={entry.id}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    {/* User message */}
                    <div className="mb-4 flex items-start gap-3">
                      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-surface-2 text-xs font-semibold text-muted-light">
                        {MODE_CONFIG[entry.mode]?.label.slice(0, 1)}
                      </div>
                      <div className="flex-1 min-w-0 pt-0.5">
                        {entry.imagePreviewUrl && (
                          <img
                            src={entry.imagePreviewUrl}
                            alt="Uploaded"
                            className="mb-2 h-16 w-16 rounded-md object-cover border border-surface-3"
                          />
                        )}
                        <p className="text-sm font-medium text-gray-100 leading-relaxed">{entry.question}</p>
                        <p className="text-[10px] text-muted mt-0.5 font-mono">
                          {MODE_CONFIG[entry.mode]?.label} · {new Date(entry.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                        </p>
                      </div>
                    </div>

                    {/* Response */}
                    <div className="ml-10">
                      {entry.error && (
                        <div className="rounded-lg border border-red-500/25 bg-red-500/8 px-4 py-3 text-sm text-red-400">
                          {entry.error}
                        </div>
                      )}

                      {isCurrentlyStreaming && (
                        <StreamingResponse
                          state={streaming}
                          onShowCitations={() => handleShowCitations(streaming.citations)}
                        />
                      )}

                      {!isCurrentlyStreaming && entry.mode === "standard" && entry.streamedText && (
                        <FrozenStreamEntry entry={entry} onShowCitations={handleShowCitations} />
                      )}

                      {entry.loading && !isCurrentlyStreaming && (
                        <div className="flex items-center gap-3 rounded-lg border border-surface-3 bg-surface-1 px-4 py-3">
                          <ClaudeBadge isStreaming />
                          <span className="text-xs text-muted">
                            {entry.mode === "disease-report" ? "Mapping disease mechanisms…"
                              : entry.mode === "target-risk" ? "Assessing target tractability…"
                              : entry.mode === "compare" ? "Running comparative analysis…"
                              : entry.mode === "hypothesis" ? "Generating hypotheses…"
                              : entry.imagePreviewUrl ? "Analyzing image…"
                              : "Reasoning across literature…"}
                          </span>
                        </div>
                      )}

                      {entry.imageAnalysis && (
                        <ImageAnalysisCard analysis={entry.imageAnalysis} previewUrl={entry.imagePreviewUrl} />
                      )}

                      {entry.response && entry.imagePreviewUrl && (
                        <div className="mt-3 rounded-lg border border-surface-3 bg-surface-1 overflow-hidden">
                          <div className="flex items-center gap-2 border-b border-surface-3 px-4 py-2.5">
                            <ClaudeBadge model={entry.response.model_used} sourceCount={entry.response.sources?.length ?? 0} />
                          </div>
                          <div className="px-5 py-4">
                            <div className="prose prose-invert prose-sm max-w-none
                              prose-headings:text-gray-100 prose-headings:font-semibold
                              prose-p:text-gray-300 prose-p:leading-relaxed
                              prose-strong:text-gray-100
                              prose-code:text-accent-300 prose-code:bg-surface-2 prose-code:rounded prose-code:px-1 prose-code:text-xs prose-code:font-mono
                              prose-ul:text-gray-300 prose-li:my-0.5">
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>{entry.response.answer}</ReactMarkdown>
                            </div>
                          </div>
                          {entry.response.sources?.length > 0 && (
                            <div className="border-t border-surface-3 bg-surface-0/40 px-4 py-2.5 flex flex-wrap gap-1.5">
                              {entry.response.sources.slice(0, 8).map((s, i) => {
                                const m = s.match(/PMID:\s*(\d+)/i);
                                return m ? (
                                  <a key={i} href={pmidToUrl(m[1])} target="_blank" rel="noopener noreferrer"
                                    className="rounded px-1.5 py-0.5 text-[10px] font-mono border border-accent-700/40 bg-accent-900/20 text-accent-400 hover:text-accent-300 transition">
                                    {s}
                                  </a>
                                ) : (
                                  <span key={i} className="rounded px-1.5 py-0.5 text-[10px] font-mono border border-surface-3 bg-surface-2 text-muted-light">{s}</span>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      )}

                      {entry.response && entry.mode === "standard" && !entry.streamedText && !entry.imagePreviewUrl && (
                        <AiResponseWrapper label="Standard retrieval">
                          <ResponseCard data={entry.response} />
                        </AiResponseWrapper>
                      )}

                      {entry.diseaseReportResponse && (
                        <AiResponseWrapper label="Mechanism report via Claude">
                          <DiseaseReportCard data={entry.diseaseReportResponse} />
                        </AiResponseWrapper>
                      )}
                      {entry.targetRiskResponse && (
                        <AiResponseWrapper label="Target risk via Claude">
                          <TargetRiskCard data={entry.targetRiskResponse} />
                        </AiResponseWrapper>
                      )}
                      {entry.compareResponse && (
                        <AiResponseWrapper label="Comparative analysis via Claude">
                          <CompareCard data={entry.compareResponse} />
                        </AiResponseWrapper>
                      )}
                      {entry.hypothesisResponse && (
                        <AiResponseWrapper label="Hypothesis generation via Claude">
                          <HypothesisCard data={entry.hypothesisResponse} />
                        </AiResponseWrapper>
                      )}
                    </div>
                  </motion.div>
                );
              })}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        {/* Input bar */}
        <div className="border-t border-surface-3 bg-surface-0/95 backdrop-blur-md">
          <form onSubmit={handleSubmit} className="mx-auto max-w-3xl px-4 py-3 sm:px-5">

            {/* Top row: mode + options */}
            <div className="flex items-center justify-between mb-2.5 gap-3 flex-wrap">
              <ModeSwitcher mode={mode} onModeChange={setMode} />

              <div className="flex items-center gap-3 shrink-0">
                {isDmiMode && (
                  <div className="flex items-center gap-1.5">
                    <span className="text-[11px] text-muted font-mono">domain:</span>
                    <input
                      type="text"
                      value={vertical}
                      onChange={(e) => setVertical(e.target.value)}
                      placeholder="general"
                      className="w-28 h-7 rounded-md border border-surface-3 bg-surface-1 px-2 text-[11px] text-gray-200 placeholder-muted outline-none transition focus:border-accent-500/50 font-mono"
                    />
                  </div>
                )}

                {mode === "standard" && (
                  <label className="flex items-center gap-2 cursor-pointer">
                    <div
                      className={`relative inline-flex h-4 w-7 items-center rounded-full transition-colors ${includePubmed ? "bg-accent-600" : "bg-surface-3"}`}
                      onClick={() => setIncludePubmed(!includePubmed)}
                    >
                      <span className={`inline-block h-3 w-3 rounded-full bg-white shadow transition-transform ${includePubmed ? "translate-x-3.5" : "translate-x-0.5"}`} />
                    </div>
                    <span className="text-[11px] text-muted select-none font-mono">pubmed</span>
                  </label>
                )}

                {streaming.citations.length > 0 && (
                  <button
                    type="button"
                    onClick={() => handleShowCitations(streaming.citations)}
                    className="flex items-center gap-1.5 rounded-md border border-surface-3 px-2 py-1 text-[11px] text-muted hover:text-gray-300 hover:border-accent-500/30 transition"
                  >
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                      <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                      <polyline points="14 2 14 8 20 8" />
                    </svg>
                    {streaming.citations.length} sources
                  </button>
                )}
              </div>
            </div>

            {/* PDF status banner */}
            <AnimatePresence>
              {uploadedPdf && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="mb-2"
                >
                  <div className={`flex items-center gap-2.5 rounded-md border px-3 py-2 text-xs ${
                    uploadedPdf.status === "done"
                      ? "border-accent-700/40 bg-accent-900/15 text-accent-400"
                      : uploadedPdf.status === "error"
                      ? "border-red-500/30 bg-red-500/8 text-red-400"
                      : "border-surface-3 bg-surface-1 text-muted-light"
                  }`}>
                    {uploadedPdf.status === "indexing" && (
                      <span className="h-3 w-3 animate-spin rounded-full border-2 border-accent-500 border-t-transparent shrink-0" />
                    )}
                    {uploadedPdf.status === "done" && (
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="shrink-0">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    )}
                    {uploadedPdf.status === "error" && (
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="shrink-0">
                        <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
                      </svg>
                    )}
                    <span className="font-mono truncate max-w-[200px]">{uploadedPdf.fileName}</span>
                    {uploadedPdf.status === "indexing" && <span className="text-muted">Indexing with Claude…</span>}
                    {uploadedPdf.message && <span className="text-muted">{uploadedPdf.message}</span>}
                    <button
                      type="button"
                      onClick={() => setUploadedPdf(null)}
                      className="ml-auto shrink-0 text-muted hover:text-gray-300 transition"
                    >
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                        <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                      </svg>
                    </button>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Image preview */}
            <AnimatePresence>
              {uploadedImage && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="mb-2 flex items-center gap-2.5"
                >
                  <div className="relative">
                    <img
                      src={uploadedImage.previewUrl}
                      alt={uploadedImage.fileName}
                      className="h-12 w-12 rounded-md object-cover border border-surface-3"
                    />
                    <button
                      type="button"
                      onClick={() => setUploadedImage(null)}
                      className="absolute -top-1.5 -right-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-surface-0 border border-surface-3 text-muted hover:text-red-400 transition"
                    >
                      <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                        <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                      </svg>
                    </button>
                  </div>
                  <div>
                    <p className="text-[11px] text-gray-300 font-medium font-mono truncate max-w-[180px]">{uploadedImage.fileName}</p>
                    <p className="text-[10px] text-muted">Claude Vision · multimodal RAG</p>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Input row */}
            <div className="flex items-center gap-2">
              {/* Hidden file inputs */}
              <input ref={imageInputRef} type="file" accept="image/*" className="hidden"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) processImageFile(f); e.target.value = ""; }} />
              <input ref={pdfInputRef} type="file" accept="application/pdf" className="hidden"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) handlePdfSelected(f); e.target.value = ""; }} />

              {/* Attach buttons */}
              <div className="flex items-center gap-1 shrink-0">
                <button
                  type="button"
                  onClick={() => imageInputRef.current?.click()}
                  title="Attach image for Claude Vision analysis"
                  className={`flex h-11 w-11 items-center justify-center rounded-lg border transition ${
                    uploadedImage
                      ? "border-accent-500/50 bg-accent-600/15 text-accent-400"
                      : "border-surface-3 bg-surface-1 text-muted hover:border-surface-4 hover:text-gray-300"
                  }`}
                >
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                    <rect x="3" y="3" width="18" height="18" rx="2" /><circle cx="8.5" cy="8.5" r="1.5" /><polyline points="21 15 16 10 5 21" />
                  </svg>
                </button>
                <button
                  type="button"
                  onClick={() => pdfInputRef.current?.click()}
                  title="Upload PDF — Claude captions figures and indexes propositions for RAG"
                  className={`flex h-11 w-11 items-center justify-center rounded-lg border transition ${
                    uploadedPdf
                      ? "border-accent-500/50 bg-accent-600/15 text-accent-400"
                      : "border-surface-3 bg-surface-1 text-muted hover:border-surface-4 hover:text-gray-300"
                  }`}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                    <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                    <polyline points="14 2 14 8 20 8" />
                    <line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /><line x1="10" y1="9" x2="8" y2="9" />
                  </svg>
                </button>
              </div>

              {/* Text inputs — consistent height */}
              {mode === "target-risk" ? (
                <>
                  <input type="text" value={question} onChange={(e) => setQuestion(e.target.value)}
                    placeholder="Condition (e.g., Rheumatoid arthritis)" disabled={isLoading}
                    className={inputCls} />
                  <span className="text-[11px] font-semibold text-muted shrink-0 font-mono">·</span>
                  <input type="text" value={targetName} onChange={(e) => setTargetName(e.target.value)}
                    placeholder="Target (e.g., TNF-alpha)" disabled={isLoading}
                    className={inputCls} />
                </>
              ) : mode === "compare" ? (
                <>
                  <input type="text" value={question} onChange={(e) => setQuestion(e.target.value)}
                    placeholder="Topic A" disabled={loading} className={inputCls} />
                  <span className="text-[11px] font-semibold text-muted shrink-0 font-mono">vs</span>
                  <input type="text" value={diseaseB} onChange={(e) => setDiseaseB(e.target.value)}
                    placeholder="Topic B" disabled={loading} className={inputCls} />
                </>
              ) : (
                <input
                  type="text"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder={
                    uploadedImage ? "Ask about this image…"
                    : mode === "disease-report" ? "Disease or condition name…"
                    : mode === "hypothesis" ? "Research topic…"
                    : "Ask about any mechanism, pathway, or target…"
                  }
                  disabled={isLoading}
                  className={inputCls}
                />
              )}

              {/* Submit */}
              <button
                type="submit"
                disabled={
                  isLoading ||
                  !question.trim() ||
                  (mode === "compare" && !diseaseB.trim() && !uploadedImage) ||
                  (mode === "target-risk" && !targetName.trim() && !uploadedImage)
                }
                className="h-11 shrink-0 rounded-lg bg-accent-600 px-4 text-sm font-semibold text-white transition hover:bg-accent-700 focus:outline-none focus:ring-2 focus:ring-accent-500 focus:ring-offset-2 focus:ring-offset-surface-0 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {isLoading ? (
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white block" />
                ) : (
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                    <line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" />
                  </svg>
                )}
              </button>
            </div>

            <p className="mt-2 text-[10px] text-muted text-center font-mono">
              Claude · BM25 + semantic RAG · {mode === "standard" ? "streaming" : "structured"} · {isDmiMode ? "mechanism intelligence" : "literature synthesis"}
            </p>
          </form>
        </div>
      </main>

      <CitationPanel
        citations={panelCitations}
        isOpen={showCitationPanel}
        onClose={() => setShowCitationPanel(false)}
      />
    </div>
  );
}
