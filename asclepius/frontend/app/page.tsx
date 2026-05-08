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

const MODE_CONFIG: Record<Mode, { label: string; description: string; icon: string; group: "dmi" | "legacy" }> = {
  "disease-report": { label: "Mechanism Report", description: "Map disease biology from literature",       icon: "🧠", group: "dmi" },
  "target-risk":    { label: "Target Risk",       description: "Score therapeutic target tractability",    icon: "🎯", group: "dmi" },
  standard:         { label: "Analyze",           description: "Real-time scientific reasoning",           icon: "⚡", group: "legacy" },
  compare:          { label: "Compare",           description: "Side-by-side biological comparison",       icon: "↔",  group: "legacy" },
  hypothesis:       { label: "Hypothesize",       description: "Generate testable experimental hypotheses",icon: "🧪", group: "legacy" },
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

// ------------------------------------------------------------------
// Asclepius Logo
// ------------------------------------------------------------------
function AsclepiusLogo({ size = 24, className = "" }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 512 512" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
      <circle cx="256" cy="256" r="240" fill="currentColor" fillOpacity="0.08" stroke="currentColor" strokeWidth="8" />
      <circle cx="256" cy="256" r="220" fill="none" stroke="currentColor" strokeWidth="1" opacity="0.12" />
      <line x1="256" y1="80" x2="256" y2="432" stroke="currentColor" strokeWidth="14" strokeLinecap="round" />
      <circle cx="256" cy="72" r="16" fill="currentColor" />
      <path d="M256 400 C216 396, 196 380, 210 362 C224 344, 260 340, 280 328 C300 316, 308 300, 296 288 C284 276, 252 272, 232 260 C212 248, 204 232, 218 218 C232 204, 260 200, 280 190 C300 180, 308 164, 296 150 C284 136, 256 132, 240 124" stroke="currentColor" strokeWidth="12" strokeLinecap="round" fill="none" />
      <path d="M240 124 C232 116, 216 110, 200 114 C188 118, 184 130, 192 138 C198 144, 210 140, 218 134" stroke="currentColor" strokeWidth="10" strokeLinecap="round" strokeLinejoin="round" fill="none" />
      <circle cx="204" cy="122" r="5" fill="currentColor" />
    </svg>
  );
}

// ------------------------------------------------------------------
// Mode Switcher — segmented pill control
// ------------------------------------------------------------------
function ModeSwitcher({
  mode,
  onModeChange,
}: {
  mode: Mode;
  onModeChange: (m: Mode) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {ALL_MODES.map((m) => {
        const active = mode === m;
        return (
          <div key={m} className="relative group">
            <button
              onClick={() => onModeChange(m)}
              className={`
                flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-medium whitespace-nowrap transition-all
                ${active
                  ? "bg-accent-600 text-white shadow-md shadow-accent-600/20"
                  : "border border-surface-3 text-muted-light hover:border-accent-500/40 hover:text-gray-200 hover:bg-surface-2"
                }
              `}
            >
              <span className="text-sm">{MODE_CONFIG[m].icon}</span>
              <span>{MODE_CONFIG[m].label}</span>
            </button>
            {/* Hover tooltip */}
            <div className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 opacity-0 group-hover:opacity-100 transition-opacity duration-150">
              <div className="rounded-lg border border-surface-3 bg-surface-1 px-2.5 py-1.5 text-[11px] text-gray-300 whitespace-nowrap shadow-lg">
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
        <div className="fixed inset-0 z-30 bg-black/50 lg:hidden" onClick={onToggleSidebar} />
      )}
      <aside className={`fixed top-0 left-0 z-40 h-full w-64 border-r border-surface-3 bg-surface-1 transition-transform duration-200 lg:relative lg:translate-x-0 ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="flex h-full flex-col">
          <div className="flex items-center justify-between border-b border-surface-3 px-4 py-3">
            <button onClick={onNewSession} className="flex items-center gap-2 group">
              <AsclepiusLogo size={22} className="text-accent-400" />
              <span className="text-sm font-semibold text-gray-100 group-hover:text-accent-400 transition">Asclepius</span>
            </button>
            <button onClick={onNewSession} className="flex h-7 w-7 items-center justify-center rounded-md text-muted hover:bg-surface-2 hover:text-gray-300 transition" title="New session">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
              </svg>
            </button>
          </div>
          <div className="flex-1 overflow-y-auto py-2">
            {sessions.length === 0 && (
              <p className="px-4 py-8 text-center text-xs text-muted">No sessions yet. Your research appears here.</p>
            )}
            {sessions.map((session) => (
              <div key={session.id}
                className={`group mx-2 mb-0.5 flex items-center rounded-lg px-3 py-2 cursor-pointer transition ${activeSessionId === session.id ? "bg-accent-600/15 text-accent-400" : "text-gray-400 hover:bg-surface-2 hover:text-gray-200"}`}
                onClick={() => onSelectSession(session.id)}
              >
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium truncate">{session.title}</p>
                  <p className="text-[10px] text-muted mt-0.5">
                    {MODE_CONFIG[session.mode]?.icon || ""} {session.entries.length} {session.entries.length === 1 ? "query" : "queries"}
                  </p>
                </div>
                <button onClick={(e) => { e.stopPropagation(); onDeleteSession(session.id); }}
                  className="ml-1 flex h-5 w-5 shrink-0 items-center justify-center rounded opacity-0 group-hover:opacity-100 hover:bg-red-500/20 hover:text-red-400 transition"
                  title="Delete session">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
          <div className="border-t border-surface-3 px-4 py-3">
            <p className="text-[10px] text-muted text-center">Sessions stored locally</p>
          </div>
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
      className="mt-4 rounded-xl border border-blue-500/25 bg-blue-500/5 overflow-hidden"
    >
      <div className="flex items-center gap-2 border-b border-blue-500/15 px-4 py-2.5 bg-blue-500/8">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="text-blue-400">
          <rect x="3" y="3" width="18" height="18" rx="2" /><circle cx="8.5" cy="8.5" r="1.5" /><polyline points="21 15 16 10 5 21" />
        </svg>
        <p className="text-xs font-bold uppercase tracking-widest text-blue-400">Image Analysis</p>
      </div>
      <div className="p-4 flex gap-4">
        {previewUrl && (
          <img src={previewUrl} alt="Uploaded research image" className="h-28 w-28 shrink-0 rounded-lg object-cover border border-surface-3" />
        )}
        <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">{analysis}</p>
      </div>
    </motion.div>
  );
}

// ------------------------------------------------------------------
// FrozenStreamEntry — renders a completed streamed response
// ------------------------------------------------------------------
function FrozenStreamEntry({ entry, onShowCitations }: {
  entry: ConversationEntry;
  onShowCitations: (citations: Citation[]) => void;
}) {
  const [sourcesExpanded, setSourcesExpanded] = useState(false);

  const sources = entry.streamedSources ?? [];
  const displayed = sourcesExpanded ? sources : sources.slice(0, 6);

  return (
    <div className="rounded-xl border border-surface-3 bg-surface-1 overflow-hidden">
      <div className="px-5 py-4">
        <div className="prose prose-invert prose-sm max-w-none
          prose-headings:text-gray-100 prose-headings:font-semibold
          prose-p:text-gray-300 prose-p:leading-relaxed
          prose-strong:text-gray-100
          prose-code:text-accent-300 prose-code:bg-surface-2 prose-code:rounded prose-code:px-1 prose-code:text-xs
          prose-ul:text-gray-300 prose-li:my-0.5
          prose-h2:text-base prose-h3:text-sm">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{entry.streamedText || ""}</ReactMarkdown>
        </div>
      </div>
      <div className="border-t border-surface-3 bg-surface-0/50 px-5 py-2.5 flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3 flex-wrap">
          {(entry.streamedCitations?.length ?? 0) > 0 && (
            <button
              onClick={() => onShowCitations(entry.streamedCitations!)}
              className="flex items-center gap-1.5 rounded-md border border-surface-3 bg-surface-2 px-2.5 py-1 text-[11px] font-medium text-muted-light hover:text-gray-200 hover:border-accent-600/50 transition"
            >
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
              {entry.streamedCitations!.length} retrieved
            </button>
          )}
          <div className="flex flex-wrap gap-1">
            {displayed.map((s, i) => {
              const pmidMatch = s.match(/PMID:\s*(\d+)/i);
              return pmidMatch ? (
                <a key={i} href={pmidToUrl(pmidMatch[1])} target="_blank" rel="noopener noreferrer"
                  className="rounded px-1.5 py-0.5 text-[10px] font-mono border border-accent-700/40 bg-accent-900/20 text-accent-400 hover:text-accent-300 transition">
                  {s}
                </a>
              ) : (
                <span key={i} className="rounded px-1.5 py-0.5 text-[10px] font-mono border border-surface-4 bg-surface-2 text-muted-light">{s}</span>
              );
            })}
            {sources.length > 6 && (
              <button onClick={() => setSourcesExpanded(!sourcesExpanded)} className="text-[10px] text-muted hover:text-gray-300 transition">
                {sourcesExpanded ? "less" : `+${sources.length - 6} more`}
              </button>
            )}
          </div>
        </div>
        {entry.streamedModel && (
          <div className="flex items-center gap-1.5 text-[10px] text-muted shrink-0">
            <span className="h-1.5 w-1.5 rounded-full bg-accent-500" />
            <span className="font-mono">
              {entry.streamedModel.includes("haiku") ? "Haiku"
                : entry.streamedModel.includes("sonnet") ? "Sonnet"
                : entry.streamedModel.includes("opus") ? "Opus"
                : entry.streamedModel}
            </span>
            {(entry.streamedCost ?? 0) > 0 && (
              <><span className="text-surface-4">·</span><span className="font-mono">${entry.streamedCost!.toFixed(5)}</span></>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------
// Landing Page Sections
// ------------------------------------------------------------------
const HOW_IT_WORKS = [
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" />
      </svg>
    ),
    title: "Search",
    desc: "Ask about any mechanism, pathway, target, or disease",
  },
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M3 5v14a9 3 0 0 0 18 0V5" /><path d="M3 12a9 3 0 0 0 18 0" />
      </svg>
    ),
    title: "Retrieve",
    desc: "BM25 and semantic search across knowledge bases and live PubMed",
  },
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <path d="M12 2a10 10 0 1 0 10 10" /><path d="M12 6v6l4 2" /><path d="M22 2L12 12" /><path d="M17 2h5v5" />
      </svg>
    ),
    title: "Synthesize",
    desc: "Answers are grounded in retrieved propositions from primary literature",
  },
];

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
  const [isDragging, setIsDragging] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

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
  // Image upload handlers
  // ------------------------------------------------------------------
  function processImageFile(file: File) {
    if (!file.type.startsWith("image/")) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      const dataUrl = e.target?.result as string;
      const base64 = dataUrl.split(",")[1];
      setUploadedImage({
        base64,
        previewUrl: dataUrl,
        mediaType: file.type,
        fileName: file.name,
      });
    };
    reader.readAsDataURL(file);
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) processImageFile(file);
  }

  function handleDragOver(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setIsDragging(true);
  }

  function handleDragLeave() {
    setIsDragging(false);
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
    if (mode === "disease-report") displayQ = `Disease Report: ${trimmed} [${vertical}]`;
    else if (mode === "target-risk") displayQ = `Target Risk: ${targetName.trim()} in ${trimmed} [${vertical}]`;
    else if (mode === "compare" && diseaseB.trim()) displayQ = `Compare: ${trimmed} vs ${diseaseB.trim()}`;
    else if (mode === "hypothesis") displayQ = `Hypotheses: ${trimmed}`;

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
      // Image query — always routes through vision endpoint
      if (capturedImage) {
        const result = await submitImageQuery({
          question: trimmed,
          image_base64: capturedImage.base64,
          media_type: capturedImage.mediaType,
          include_pubmed: includePubmed,
        });
        setEntries((prev) =>
          prev.map((e, i) =>
            i === idx
              ? { ...e, response: result, imageAnalysis: result.image_analysis ?? undefined, loading: false }
              : e,
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
            className="fixed inset-0 z-50 flex items-center justify-center bg-accent-900/60 backdrop-blur-sm border-4 border-dashed border-accent-400/60"
          >
            <div className="text-center">
              <div className="text-5xl mb-3">🖼️</div>
              <p className="text-xl font-bold text-accent-300">Drop image to upload</p>
              <p className="text-sm text-accent-400/70 mt-1">Supports JPEG, PNG, GIF, WebP</p>
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
        {/* Top bar — logo + auth only (mode switcher moved to input area) */}
        <header className="sticky top-0 z-20 border-b border-surface-3 bg-surface-0/80 backdrop-blur-md">
          <div className="flex items-center justify-between px-4 py-3 sm:px-6">
            <div className="flex items-center gap-3">
              <button onClick={() => setSidebarOpen(!sidebarOpen)} className="flex h-8 w-8 items-center justify-center rounded-lg text-muted hover:bg-surface-2 hover:text-gray-300 transition lg:hidden">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                  <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
                </svg>
              </button>
              <button onClick={handleNewSession} className="flex items-center justify-center group" title="New session">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-600/20 text-accent-400 group-hover:bg-accent-600/30 transition">
                  <AsclepiusLogo size={20} />
                </div>
              </button>
            </div>
            <AuthHeader />
          </div>
        </header>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {/* Landing state */}
          {isEmpty && (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35 }}
              className="mx-auto flex max-w-2xl flex-col items-center px-6 pt-12 pb-10 sm:pt-16"
            >
              {/* Hero */}
              <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-accent-600/10 text-accent-400 ring-1 ring-accent-500/20">
                <AsclepiusLogo size={36} />
              </div>
              <h2 className="text-2xl font-bold tracking-tight text-gray-100 sm:text-3xl text-center">
                Scientific Research Intelligence
              </h2>
              <p className="mt-2 text-center text-sm text-muted max-w-sm leading-relaxed">
                Query any scientific domain. Mechanism mapping, hypothesis generation, and literature synthesis from primary research.
              </p>

              {/* Mode switcher — centered, prominent on landing */}
              <div className="mt-8 flex justify-center w-full">
                <ModeSwitcher mode={mode} onModeChange={setMode} />
              </div>

              {/* Example chips */}
              <div className="mt-4 w-full">
                <div className="flex flex-wrap gap-2 justify-center">
                  {examples.map((example) => (
                    <motion.button
                      key={example}
                      whileHover={{ scale: 1.03 }}
                      whileTap={{ scale: 0.97 }}
                      onClick={() => handleExampleClick(example)}
                      className="rounded-full border border-surface-3 bg-surface-1 px-4 py-2 text-xs text-gray-400 transition hover:border-accent-500/40 hover:bg-surface-2 hover:text-gray-200 hover:shadow-[0_0_12px_rgba(13,148,136,0.15)]"
                    >
                      <span className="mr-1.5 opacity-60">{MODE_CONFIG[mode].icon}</span>{example}
                    </motion.button>
                  ))}
                </div>
              </div>

              {/* How it works */}
              <div className="mt-10 w-full">
                <div className="flex items-center gap-2 mb-4">
                  <div className="h-px flex-1 bg-surface-3" />
                  <p className="text-[10px] font-bold uppercase tracking-widest text-muted-dim px-2">How it works</p>
                  <div className="h-px flex-1 bg-surface-3" />
                </div>
                <div className="grid grid-cols-3 gap-3">
                  {HOW_IT_WORKS.map((step, i) => (
                    <motion.div
                      key={step.title}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.1 + i * 0.08 }}
                      className="rounded-xl border border-surface-3 bg-surface-1 p-4 text-center"
                    >
                      <div className="flex justify-center mb-2 text-accent-400">{step.icon}</div>
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
            <div className="mx-auto max-w-5xl px-4 py-8 space-y-10 sm:px-6">
              {entries.map((entry) => {
                const isCurrentlyStreaming = entry.id === streamingEntryId;
                return (
                  <motion.div
                    key={entry.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.25 }}
                  >
                    {/* User query bubble */}
                    <div className="mb-5 flex items-start gap-3">
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent-600/20 text-sm">
                        {MODE_CONFIG[entry.mode]?.icon || "Q"}
                      </div>
                      <div className="flex-1 min-w-0 pt-0.5">
                        {/* Show uploaded image thumbnail if present */}
                        {entry.imagePreviewUrl && (
                          <img
                            src={entry.imagePreviewUrl}
                            alt="Uploaded"
                            className="mb-2 h-20 w-20 rounded-lg object-cover border border-surface-3"
                          />
                        )}
                        <p className="text-sm font-semibold text-gray-100 leading-relaxed">{entry.question}</p>
                        <p className="text-[10px] text-muted mt-0.5">
                          {MODE_CONFIG[entry.mode]?.label} · {new Date(entry.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                        </p>
                      </div>
                    </div>

                    {/* Response area */}
                    <div className="ml-10">
                      {entry.error && (
                        <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">{entry.error}</div>
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
                          <div className="h-4 w-4 animate-spin rounded-full border-2 border-accent-500 border-t-transparent" />
                          <span className="animate-pulse text-sm text-muted-light">
                            {entry.mode === "disease-report" ? "Analyzing literature…"
                              : entry.mode === "target-risk" ? "Assessing target risk…"
                              : entry.mode === "compare" ? "Comparing topics…"
                              : entry.mode === "hypothesis" ? "Generating hypotheses…"
                              : entry.imagePreviewUrl ? "Analyzing image with Claude vision…"
                              : "Reasoning across datasets…"}
                          </span>
                        </div>
                      )}

                      {/* Image analysis card (shown for image queries) */}
                      {entry.imageAnalysis && (
                        <ImageAnalysisCard
                          analysis={entry.imageAnalysis}
                          previewUrl={entry.imagePreviewUrl}
                        />
                      )}

                      {/* Image query main response */}
                      {entry.response && entry.imagePreviewUrl && (
                        <div className="mt-4 rounded-xl border border-surface-3 bg-surface-1 overflow-hidden">
                          <div className="px-5 py-4">
                            <div className="prose prose-invert prose-sm max-w-none
                              prose-headings:text-gray-100 prose-headings:font-semibold
                              prose-p:text-gray-300 prose-p:leading-relaxed
                              prose-strong:text-gray-100
                              prose-code:text-accent-300 prose-code:bg-surface-2 prose-code:rounded prose-code:px-1 prose-code:text-xs
                              prose-ul:text-gray-300 prose-li:my-0.5">
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>{entry.response.answer}</ReactMarkdown>
                            </div>
                          </div>
                          {entry.response.sources?.length > 0 && (
                            <div className="border-t border-surface-3 bg-surface-0/50 px-5 py-2.5 flex flex-wrap gap-1">
                              {entry.response.sources.slice(0, 8).map((s, i) => {
                                const m = s.match(/PMID:\s*(\d+)/i);
                                return m ? (
                                  <a key={i} href={pmidToUrl(m[1])} target="_blank" rel="noopener noreferrer"
                                    className="rounded px-1.5 py-0.5 text-[10px] font-mono border border-accent-700/40 bg-accent-900/20 text-accent-400 hover:text-accent-300 transition">
                                    {s}
                                  </a>
                                ) : (
                                  <span key={i} className="rounded px-1.5 py-0.5 text-[10px] font-mono border border-surface-4 bg-surface-2 text-muted-light">{s}</span>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      )}

                      {/* Standard mode — restored session */}
                      {entry.response && entry.mode === "standard" && !entry.streamedText && !entry.imagePreviewUrl && (
                        <ResponseCard data={entry.response} />
                      )}

                      {entry.diseaseReportResponse && <DiseaseReportCard data={entry.diseaseReportResponse} />}
                      {entry.targetRiskResponse && <TargetRiskCard data={entry.targetRiskResponse} />}
                      {entry.compareResponse && <CompareCard data={entry.compareResponse} />}
                      {entry.hypothesisResponse && <HypothesisCard data={entry.hypothesisResponse} />}
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
          <form onSubmit={handleSubmit} className="mx-auto max-w-5xl px-4 py-3 sm:px-6">
            {/* Mode switcher row */}
            <div className="flex items-center justify-between mb-2.5 gap-3 flex-wrap">
              <div className="flex-1 min-w-0">
                <ModeSwitcher mode={mode} onModeChange={setMode} />
              </div>

              <div className="flex items-center gap-3 shrink-0">
                {isDmiMode && (
                  <div className="flex items-center gap-1.5">
                    <span className="text-[11px] text-muted-light">Domain:</span>
                    <input
                      type="text"
                      value={vertical}
                      onChange={(e) => setVertical(e.target.value)}
                      placeholder="e.g., immunology"
                      className="w-32 rounded-md border border-surface-3 bg-surface-1 px-2 py-1 text-[11px] text-gray-200 placeholder-muted outline-none transition focus:border-accent-500/60"
                    />
                  </div>
                )}

                {mode === "standard" && (
                  <>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <div
                        className={`relative inline-flex h-4 w-7 items-center rounded-full transition-colors ${includePubmed ? "bg-accent-600" : "bg-surface-3"}`}
                        onClick={() => setIncludePubmed(!includePubmed)}
                      >
                        <span className={`inline-block h-3 w-3 rounded-full bg-white shadow transition-transform ${includePubmed ? "translate-x-3.5" : "translate-x-0.5"}`} />
                      </div>
                      <span className="text-[11px] text-muted-light select-none">Live PubMed</span>
                    </label>

                    {streaming.citations.length > 0 && (
                      <button type="button" onClick={() => handleShowCitations(streaming.citations)}
                        className="flex items-center gap-1.5 rounded-md border border-surface-3 bg-surface-2 px-2.5 py-1 text-[11px] font-medium text-muted-light hover:text-accent-400 hover:border-accent-500/40 transition">
                        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                          <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                          <polyline points="14 2 14 8 20 8" />
                        </svg>
                        {streaming.citations.length} sources
                      </button>
                    )}
                  </>
                )}
              </div>
            </div>

            {/* Image preview */}
            <AnimatePresence>
              {uploadedImage && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="mb-2 flex items-center gap-2"
                >
                  <div className="relative">
                    <img
                      src={uploadedImage.previewUrl}
                      alt={uploadedImage.fileName}
                      className="h-14 w-14 rounded-lg object-cover border border-accent-500/30"
                    />
                    <button
                      type="button"
                      onClick={() => setUploadedImage(null)}
                      className="absolute -top-1.5 -right-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-surface-0 border border-surface-3 text-muted hover:text-red-400 hover:border-red-400/40 transition"
                    >
                      <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                        <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                      </svg>
                    </button>
                  </div>
                  <div>
                    <p className="text-[11px] text-gray-300 font-medium truncate max-w-[200px]">{uploadedImage.fileName}</p>
                    <p className="text-[10px] text-muted">Image ready, will be analyzed with Claude Vision</p>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Input row */}
            <div className="flex gap-2 sm:gap-3">
              {/* Image upload button */}
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) processImageFile(file);
                  e.target.value = "";
                }}
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                title="Upload image for visual analysis"
                className={`flex h-[46px] w-[46px] shrink-0 items-center justify-center rounded-xl border transition ${
                  uploadedImage
                    ? "border-accent-500/50 bg-accent-600/15 text-accent-400"
                    : "border-surface-3 bg-surface-1 text-muted hover:border-accent-500/30 hover:text-gray-300"
                }`}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                  <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
                </svg>
              </button>

              {mode === "target-risk" ? (
                <>
                  <input type="text" value={question} onChange={(e) => setQuestion(e.target.value)}
                    placeholder="Topic or condition (e.g., Rheumatoid arthritis)" disabled={isLoading}
                    className="flex-1 rounded-xl border border-surface-3 bg-surface-1 px-4 py-3 text-sm text-gray-100 placeholder-muted outline-none transition focus:border-accent-500/60 focus:ring-1 focus:ring-accent-500/25 disabled:opacity-50" />
                  <input type="text" value={targetName} onChange={(e) => setTargetName(e.target.value)}
                    placeholder="Target (e.g., TNF-alpha, BACE1)" disabled={isLoading}
                    className="flex-1 rounded-xl border border-surface-3 bg-surface-1 px-4 py-3 text-sm text-gray-100 placeholder-muted outline-none transition focus:border-accent-500/60 focus:ring-1 focus:ring-accent-500/25 disabled:opacity-50" />
                </>
              ) : mode === "compare" ? (
                <>
                  <input type="text" value={question} onChange={(e) => setQuestion(e.target.value)}
                    placeholder="Topic A (e.g., Alzheimer's disease)" disabled={loading}
                    className="flex-1 rounded-xl border border-surface-3 bg-surface-1 px-4 py-3 text-sm text-gray-100 placeholder-muted outline-none transition focus:border-accent-500/60 focus:ring-1 focus:ring-accent-500/25 disabled:opacity-50" />
                  <div className="flex items-center px-1"><span className="text-xs font-bold text-muted">vs</span></div>
                  <input type="text" value={diseaseB} onChange={(e) => setDiseaseB(e.target.value)}
                    placeholder="Topic B (e.g., Parkinson's disease)" disabled={loading}
                    className="flex-1 rounded-xl border border-surface-3 bg-surface-1 px-4 py-3 text-sm text-gray-100 placeholder-muted outline-none transition focus:border-accent-500/60 focus:ring-1 focus:ring-accent-500/25 disabled:opacity-50" />
                </>
              ) : (
                <input
                  type="text"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder={
                    uploadedImage
                      ? "Ask a question about this image…"
                      : mode === "disease-report" ? "Enter topic or condition name…"
                      : mode === "hypothesis" ? "Research topic (e.g., tau aggregation in Alzheimer's)…"
                      : "Ask about any mechanism, pathway, or research question…"
                  }
                  disabled={isLoading}
                  className="flex-1 rounded-xl border border-surface-3 bg-surface-1 px-4 py-3 text-sm text-gray-100 placeholder-muted outline-none transition focus:border-accent-500/60 focus:ring-1 focus:ring-accent-500/25 disabled:opacity-50"
                />
              )}

              <button
                type="submit"
                disabled={
                  isLoading ||
                  !question.trim() ||
                  (mode === "compare" && !diseaseB.trim() && !uploadedImage) ||
                  (mode === "target-risk" && !targetName.trim() && !uploadedImage)
                }
                className="rounded-xl bg-accent-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-accent-700 focus:outline-none focus:ring-2 focus:ring-accent-500 focus:ring-offset-2 focus:ring-offset-surface-0 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {isLoading ? (
                  <span className="flex items-center gap-2">
                    <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                    <span className="hidden sm:inline">Working…</span>
                  </span>
                ) : (
                  <span className="flex items-center gap-1.5">
                    <span>{uploadedImage ? "🔬" : MODE_CONFIG[mode].icon}</span>
                    <span className="hidden sm:inline">{uploadedImage ? "Analyze" : MODE_CONFIG[mode].label}</span>
                  </span>
                )}
              </button>
            </div>
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
