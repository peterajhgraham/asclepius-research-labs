"use client";

import { useState, useRef, useEffect, useCallback, type FormEvent } from "react";
import {
  submitQuery,
  compareDiseases,
  generateHypotheses,
  type QueryResponse,
  type CompareResponse,
  type HypothesisResponse,
} from "@/lib/api";
import {
  generateDiseaseReport,
  generateTargetRiskReport,
  type DiseaseReportResponse,
  type TargetRiskResponse,
  type Vertical,
} from "@/lib/dmi-api";
import ResponseCard from "@/components/ResponseCard";
import CompareCard from "@/components/CompareCard";
import HypothesisCard from "@/components/HypothesisCard";
import DiseaseReportCard from "@/components/DiseaseReportCard";
import TargetRiskCard from "@/components/TargetRiskCard";

// ------------------------------------------------------------------
// Types
// ------------------------------------------------------------------
type Mode = "disease-report" | "target-risk" | "standard" | "compare" | "hypothesis";

interface ConversationEntry {
  id: string;
  question: string;
  mode: Mode;
  response: QueryResponse | null;
  compareResponse: CompareResponse | null;
  hypothesisResponse: HypothesisResponse | null;
  diseaseReportResponse: DiseaseReportResponse | null;
  targetRiskResponse: TargetRiskResponse | null;
  loading: boolean;
  error: string | null;
  timestamp: number;
  saved: boolean;
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
    "Rheumatoid arthritis",
    "Non-small cell lung cancer",
    "Systemic lupus erythematosus",
    "Triple-negative breast cancer",
    "Multiple sclerosis",
    "Colorectal cancer",
  ],
  "target-risk": [
    "TNF-alpha in Rheumatoid arthritis",
    "PD-1 in Non-small cell lung cancer",
    "BAFF in Systemic lupus",
    "KRAS in Colorectal cancer",
    "IL-17A in Psoriasis",
    "EGFR in Glioblastoma",
  ],
  standard: [
    "Rheumatoid arthritis cytokine pathways",
    "JAK-STAT dysregulation in lupus",
    "T cell exhaustion in autoimmunity",
    "IL-23/IL-17 axis in psoriasis",
    "TNF signaling and therapeutic targets",
    "Multiple sclerosis pathogenesis",
  ],
  compare: [
    "Rheumatoid arthritis vs Lupus",
    "Multiple sclerosis vs Type 1 diabetes",
    "Psoriasis vs Ankylosing spondylitis",
    "Crohn's disease vs Ulcerative colitis",
  ],
  hypothesis: [
    "JAK-STAT pathway in rheumatoid arthritis",
    "IL-17 signaling in psoriasis",
    "B cell hyperactivity in lupus",
    "Interferon signaling in multiple sclerosis",
  ],
};

const MODE_CONFIG: Record<Mode, { label: string; description: string; icon: string; group: "dmi" | "legacy" }> = {
  "disease-report": { label: "Disease Report", description: "Structured mechanism report", icon: "\uD83E\uDDE0", group: "dmi" },
  "target-risk":    { label: "Target Risk", description: "Risk scoring assessment", icon: "\uD83C\uDFAF", group: "dmi" },
  standard:         { label: "Analyze", description: "Structured immune reasoning", icon: "\u26A1", group: "legacy" },
  compare:          { label: "Compare", description: "Disease vs disease", icon: "\u2194\uFE0F", group: "legacy" },
  hypothesis:       { label: "Hypothesize", description: "Generate testable hypotheses", icon: "\uD83E\uDDEA", group: "legacy" },
};

const LS_KEY = "asclepius_sessions";

// ------------------------------------------------------------------
// Helpers
// ------------------------------------------------------------------
function genId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

function loadSessions(): SavedSession[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(LS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function persistSessions(sessions: SavedSession[]) {
  if (typeof window === "undefined") return;
  localStorage.setItem(LS_KEY, JSON.stringify(sessions));
}

function sessionTitle(entries: ConversationEntry[]): string {
  if (!entries.length) return "New session";
  const first = entries[0].question;
  return first.length > 40 ? first.slice(0, 40) + "..." : first;
}

// ------------------------------------------------------------------
// Rod of Asclepius SVG Logo
// ------------------------------------------------------------------
function AsclepiusLogo({ size = 24, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 512 512"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <circle cx="256" cy="256" r="240" fill="currentColor" fillOpacity="0.08" stroke="currentColor" strokeWidth="8" />
      <circle cx="256" cy="256" r="220" fill="none" stroke="currentColor" strokeWidth="1" opacity="0.12" />
      <line x1="256" y1="80" x2="256" y2="432" stroke="currentColor" strokeWidth="14" strokeLinecap="round" />
      <circle cx="256" cy="72" r="16" fill="currentColor" />
      <circle cx="256" cy="72" r="8" fill="currentColor" fillOpacity="0.15" />
      <path
        d="M256 400 C216 396, 196 380, 210 362 C224 344, 260 340, 280 328 C300 316, 308 300, 296 288 C284 276, 252 272, 232 260 C212 248, 204 232, 218 218 C232 204, 260 200, 280 190 C300 180, 308 164, 296 150 C284 136, 256 132, 240 124"
        stroke="currentColor"
        strokeWidth="12"
        strokeLinecap="round"
        fill="none"
      />
      <path
        d="M240 124 C232 116, 216 110, 200 114 C188 118, 184 130, 192 138 C198 144, 210 140, 218 134"
        stroke="currentColor"
        strokeWidth="10"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
      <circle cx="204" cy="122" r="5" fill="currentColor" />
      <path d="M194 114 L180 106" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
      <path d="M194 114 L182 118" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

// ------------------------------------------------------------------
// Sidebar
// ------------------------------------------------------------------
function Sidebar({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewSession,
  onDeleteSession,
  sidebarOpen,
  onToggleSidebar,
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

      <aside
        className={`fixed top-0 left-0 z-40 h-full w-64 border-r border-surface-3 bg-surface-1 transition-transform duration-200 lg:relative lg:translate-x-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex h-full flex-col">
          <div className="flex items-center justify-between border-b border-surface-3 px-4 py-3">
            <button onClick={onNewSession} className="flex items-center gap-2 group">
              <AsclepiusLogo size={22} className="text-accent-400" />
              <span className="text-sm font-semibold text-gray-100 group-hover:text-accent-400 transition">
                Asclepius
              </span>
            </button>
            <button
              onClick={onNewSession}
              className="flex h-7 w-7 items-center justify-center rounded-md text-muted hover:bg-surface-2 hover:text-gray-300 transition"
              title="New session"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
            </button>
          </div>

          <div className="flex-1 overflow-y-auto py-2">
            {sessions.length === 0 && (
              <p className="px-4 py-8 text-center text-xs text-muted">
                No saved sessions yet. Your research sessions will appear here.
              </p>
            )}
            {sessions.map((session) => (
              <div
                key={session.id}
                className={`group mx-2 mb-0.5 flex items-center rounded-lg px-3 py-2 cursor-pointer transition ${
                  activeSessionId === session.id
                    ? "bg-accent-600/15 text-accent-400"
                    : "text-gray-400 hover:bg-surface-2 hover:text-gray-200"
                }`}
                onClick={() => onSelectSession(session.id)}
              >
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium truncate">{session.title}</p>
                  <p className="text-[10px] text-muted mt-0.5">
                    {MODE_CONFIG[session.mode]?.icon || ""} {session.entries.length} {session.entries.length === 1 ? "query" : "queries"}
                  </p>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); onDeleteSession(session.id); }}
                  className="ml-1 flex h-5 w-5 shrink-0 items-center justify-center rounded opacity-0 group-hover:opacity-100 hover:bg-red-500/20 hover:text-red-400 transition"
                  title="Delete session"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              </div>
            ))}
          </div>

          <div className="border-t border-surface-3 px-4 py-3">
            <p className="text-[10px] text-muted text-center">
              Sessions stored locally
            </p>
          </div>
        </div>
      </aside>
    </>
  );
}

// ------------------------------------------------------------------
// Main Page
// ------------------------------------------------------------------
export default function HomePage() {
  const [question, setQuestion] = useState("");
  const [diseaseB, setDiseaseB] = useState("");
  const [targetName, setTargetName] = useState("");
  const [vertical, setVertical] = useState<Vertical>("immunology");
  const [entries, setEntries] = useState<ConversationEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<Mode>("disease-report");
  const [includePubmed, setIncludePubmed] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Session management
  const [sessions, setSessions] = useState<SavedSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);

  useEffect(() => {
    setSessions(loadSessions());
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries]);

  const saveCurrentSession = useCallback(() => {
    if (!entries.length) return;

    setSessions((prev) => {
      let updated: SavedSession[];
      if (activeSessionId) {
        updated = prev.map((s) =>
          s.id === activeSessionId
            ? { ...s, entries, title: sessionTitle(entries), mode, updatedAt: Date.now() }
            : s
        );
      } else {
        const newId = genId();
        const newSession: SavedSession = {
          id: newId,
          title: sessionTitle(entries),
          mode,
          entries,
          createdAt: Date.now(),
          updatedAt: Date.now(),
        };
        updated = [newSession, ...prev];
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
    setEntries([]);
    setActiveSessionId(null);
    setQuestion("");
    setDiseaseB("");
    setTargetName("");
    setMode("disease-report");
    setVertical("immunology");
    setSidebarOpen(false);
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
    if (activeSessionId === sessionId) {
      handleNewSession();
    }
  }

  function handleGoHome() {
    handleNewSession();
  }

  async function handleSubmit(e?: FormEvent<HTMLFormElement>) {
    if (e) e.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || loading) return;

    const idx = entries.length;
    let displayQ = trimmed;
    if (mode === "disease-report") {
      displayQ = `Disease Report: ${trimmed} [${vertical}]`;
    } else if (mode === "target-risk") {
      displayQ = `Target Risk: ${targetName.trim()} in ${trimmed} [${vertical}]`;
    } else if (mode === "compare" && diseaseB.trim()) {
      displayQ = `Compare: ${trimmed} vs ${diseaseB.trim()}`;
    } else if (mode === "hypothesis") {
      displayQ = `Hypotheses: ${trimmed}`;
    }

    const entry: ConversationEntry = {
      id: genId(),
      question: displayQ,
      mode,
      response: null,
      compareResponse: null,
      hypothesisResponse: null,
      diseaseReportResponse: null,
      targetRiskResponse: null,
      loading: true,
      error: null,
      timestamp: Date.now(),
      saved: false,
    };

    setEntries((prev) => [...prev, entry]);
    setQuestion("");
    setDiseaseB("");
    setTargetName("");
    setLoading(true);

    try {
      if (mode === "disease-report") {
        const result = await generateDiseaseReport({
          disease_name: trimmed,
          vertical,
        });
        setEntries((prev) =>
          prev.map((e, i) =>
            i === idx ? { ...e, diseaseReportResponse: result, loading: false } : e
          )
        );
      } else if (mode === "target-risk") {
        const result = await generateTargetRiskReport({
          disease_name: trimmed,
          target_name: targetName.trim(),
          vertical,
        });
        setEntries((prev) =>
          prev.map((e, i) =>
            i === idx ? { ...e, targetRiskResponse: result, loading: false } : e
          )
        );
      } else if (mode === "compare") {
        const result = await compareDiseases({
          disease_a: trimmed,
          disease_b: diseaseB.trim() || trimmed,
        });
        setEntries((prev) =>
          prev.map((e, i) =>
            i === idx ? { ...e, compareResponse: result, loading: false } : e
          )
        );
      } else if (mode === "hypothesis") {
        const result = await generateHypotheses({ topic: trimmed });
        setEntries((prev) =>
          prev.map((e, i) =>
            i === idx ? { ...e, hypothesisResponse: result, loading: false } : e
          )
        );
      } else {
        const result = await submitQuery({
          question: trimmed,
          include_pubmed: includePubmed,
        });
        setEntries((prev) =>
          prev.map((e, i) =>
            i === idx ? { ...e, response: result, loading: false } : e
          )
        );
      }
    } catch (err: unknown) {
      let detail = "Unable to reach the analysis service.";
      if (err && typeof err === "object" && "response" in err) {
        const res = (err as { response?: { data?: { detail?: string; error?: string } } }).response;
        if (res?.data?.detail) detail = res.data.detail;
        else if (res?.data?.error) detail = res.data.error;
      }
      setEntries((prev) =>
        prev.map((e, i) =>
          i === idx ? { ...e, error: detail, loading: false } : e
        )
      );
    } finally {
      setLoading(false);
    }
  }

  const isEmpty = entries.length === 0;
  const examples = EXAMPLE_PROMPTS[mode];
  const isDmiMode = mode === "disease-report" || mode === "target-risk";

  function handleExampleClick(example: string) {
    if (mode === "compare") {
      const parts = example.split(" vs ");
      setQuestion(parts[0] || example);
      setDiseaseB(parts[1] || "");
    } else if (mode === "target-risk") {
      const parts = example.split(" in ");
      setTargetName(parts[0] || "");
      setQuestion(parts[1] || example);
    } else {
      setQuestion(example);
    }
  }

  const dmiModes: Mode[] = ["disease-report", "target-risk"];
  const legacyModes: Mode[] = ["standard", "compare", "hypothesis"];

  return (
    <div className="flex h-screen bg-surface-0 overflow-hidden">
      {/* Sidebar */}
      <Sidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        onDeleteSession={handleDeleteSession}
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
      />

      {/* Main content */}
      <main className="flex flex-1 min-w-0 flex-col">
        {/* Top bar */}
        <header className="sticky top-0 z-20 border-b border-surface-3 bg-surface-0/80 backdrop-blur-md">
          <div className="flex items-center justify-between px-4 py-3 sm:px-6">
            <div className="flex items-center gap-3">
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-muted hover:bg-surface-2 hover:text-gray-300 transition lg:hidden"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                  <line x1="3" y1="6" x2="21" y2="6" />
                  <line x1="3" y1="12" x2="21" y2="12" />
                  <line x1="3" y1="18" x2="21" y2="18" />
                </svg>
              </button>
              <button
                onClick={handleGoHome}
                className="flex items-center gap-2.5 group"
                title="Back to home"
              >
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-600/20 text-accent-400 group-hover:bg-accent-600/30 transition">
                  <AsclepiusLogo size={20} />
                </div>
                <div className="hidden sm:block">
                  <h1 className="text-sm font-semibold text-gray-100 tracking-tight group-hover:text-accent-400 transition">
                    Asclepius Research Labs
                  </h1>
                  <p className="text-[10px] text-muted leading-none">
                    Disease Mechanism Intelligence
                  </p>
                </div>
              </button>
            </div>
            <div className="flex items-center gap-2 sm:gap-3">
              {/* DMI mode switcher */}
              <div className="flex rounded-lg border border-accent-500/30 bg-surface-1 p-0.5">
                {dmiModes.map((m) => (
                  <button
                    key={m}
                    onClick={() => setMode(m)}
                    className={`rounded-md px-2 py-1.5 text-xs font-medium transition sm:px-3 ${
                      mode === m
                        ? "bg-accent-600/20 text-accent-400"
                        : "text-muted hover:text-gray-300"
                    }`}
                  >
                    <span className="mr-0.5 sm:mr-1">{MODE_CONFIG[m].icon}</span>
                    <span className="hidden sm:inline">{MODE_CONFIG[m].label}</span>
                  </button>
                ))}
              </div>
              {/* Legacy mode switcher */}
              <div className="flex rounded-lg border border-surface-3 bg-surface-1 p-0.5">
                {legacyModes.map((m) => (
                  <button
                    key={m}
                    onClick={() => setMode(m)}
                    className={`rounded-md px-2 py-1.5 text-xs font-medium transition sm:px-3 ${
                      mode === m
                        ? "bg-accent-600/20 text-accent-400"
                        : "text-muted hover:text-gray-300"
                    }`}
                  >
                    <span className="mr-0.5 sm:mr-1">{MODE_CONFIG[m].icon}</span>
                    <span className="hidden sm:inline">{MODE_CONFIG[m].label}</span>
                  </button>
                ))}
              </div>
              <span className="hidden md:inline-block rounded-full border border-surface-4 px-3 py-1 text-xs text-muted">
                {entries.length} {entries.length === 1 ? "query" : "queries"}
              </span>
            </div>
          </div>
        </header>

        {/* Content area */}
        <div className="flex-1 overflow-y-auto">
          {/* Empty state */}
          {isEmpty && (
            <div className="mx-auto flex max-w-3xl flex-col items-center px-6 pt-16 pb-8 sm:pt-24">
              <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-accent-600/10 text-accent-400">
                <AsclepiusLogo size={36} />
              </div>
              <h2 className="text-2xl font-semibold tracking-tight text-gray-100 sm:text-3xl">
                Disease Mechanism Intelligence
              </h2>
              <p className="mt-2 text-center text-sm text-muted max-w-md">
                An AI system that maps causal disease biology and generates
                mechanistically grounded target risk assessments from primary literature.
              </p>

              {/* Mode description */}
              <div className="mt-6 rounded-lg border border-accent-500/20 bg-accent-600/5 px-4 py-3 text-center">
                <p className="text-xs text-accent-400 font-semibold">
                  {MODE_CONFIG[mode].icon} {MODE_CONFIG[mode].label} Mode
                </p>
                <p className="text-xs text-muted mt-1">
                  {mode === "disease-report" && "Enter a disease name to generate a structured, citation-backed mechanism report"}
                  {mode === "target-risk" && "Enter a disease and target to generate a risk-scored assessment"}
                  {mode === "standard" && "Ask about disease mechanisms, cytokine networks, pathways, or therapeutics"}
                  {mode === "compare" && "Enter two diseases to see a structured side-by-side comparison"}
                  {mode === "hypothesis" && "Enter a topic to generate testable research hypotheses with experimental designs"}
                </p>
              </div>

              {/* Vertical selector for DMI modes */}
              {isDmiMode && (
                <div className="mt-4 flex items-center gap-3">
                  <span className="text-xs text-muted-light">Vertical:</span>
                  <div className="flex rounded-lg border border-surface-3 bg-surface-1 p-0.5">
                    {(["immunology", "oncology"] as Vertical[]).map((v) => (
                      <button
                        key={v}
                        onClick={() => setVertical(v)}
                        className={`rounded-md px-3 py-1.5 text-xs font-medium capitalize transition ${
                          vertical === v
                            ? "bg-accent-600/20 text-accent-400"
                            : "text-muted hover:text-gray-300"
                        }`}
                      >
                        {v}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="mt-8 w-full max-w-lg">
                <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-dim">
                  Try a query
                </p>
                <div className="grid grid-cols-2 gap-2">
                  {examples.map((example) => (
                    <button
                      key={example}
                      onClick={() => handleExampleClick(example)}
                      className="rounded-lg border border-surface-3 bg-surface-1 px-3 py-2.5 text-left text-sm text-gray-300 transition hover:border-surface-4 hover:bg-surface-2 hover:text-gray-100"
                    >
                      {example}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Results */}
          {!isEmpty && (
            <div className="mx-auto max-w-5xl px-4 py-8 space-y-8 sm:px-6">
              {entries.map((entry) => (
                <div key={entry.id}>
                  {/* User query */}
                  <div className="mb-4 flex items-start gap-3">
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-accent-600/20 text-xs font-semibold text-accent-400">
                      {entry.mode === "disease-report"
                        ? "\uD83E\uDDE0"
                        : entry.mode === "target-risk"
                          ? "\uD83C\uDFAF"
                          : entry.mode === "compare"
                            ? "\u2194"
                            : entry.mode === "hypothesis"
                              ? "H"
                              : "Q"}
                    </div>
                    <p className="pt-0.5 text-sm font-medium text-gray-100">
                      {entry.question}
                    </p>
                  </div>

                  {/* Loading state */}
                  {entry.loading && (
                    <div className="ml-10 flex items-center gap-3 rounded-lg border border-surface-3 bg-surface-1 px-4 py-3">
                      <div className="h-4 w-4 animate-spin rounded-full border-2 border-accent-500 border-t-transparent" />
                      <span className="animate-pulse text-sm text-muted-light">
                        {entry.mode === "disease-report"
                          ? "Analyzing literature..."
                          : entry.mode === "target-risk"
                            ? "Assessing target risk..."
                            : entry.mode === "compare"
                              ? "Comparing diseases..."
                              : entry.mode === "hypothesis"
                                ? "Generating hypotheses..."
                                : "Reasoning across datasets..."}
                      </span>
                    </div>
                  )}

                  {/* Error state */}
                  {entry.error && (
                    <div className="ml-10 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
                      {entry.error}
                    </div>
                  )}

                  {/* Disease Report response */}
                  {entry.diseaseReportResponse && (
                    <div className="ml-10">
                      <DiseaseReportCard data={entry.diseaseReportResponse} />
                    </div>
                  )}

                  {/* Target Risk response */}
                  {entry.targetRiskResponse && (
                    <div className="ml-10">
                      <TargetRiskCard data={entry.targetRiskResponse} />
                    </div>
                  )}

                  {/* Standard response */}
                  {entry.response && (
                    <div className="ml-10">
                      <ResponseCard data={entry.response} />
                    </div>
                  )}

                  {/* Compare response */}
                  {entry.compareResponse && (
                    <div className="ml-10">
                      <CompareCard data={entry.compareResponse} />
                    </div>
                  )}

                  {/* Hypothesis response */}
                  {entry.hypothesisResponse && (
                    <div className="ml-10">
                      <HypothesisCard data={entry.hypothesisResponse} />
                    </div>
                  )}
                </div>
              ))}

              <div ref={bottomRef} />
            </div>
          )}
        </div>

        {/* Input area — sticky bottom */}
        <div className="border-t border-surface-3 bg-surface-0/90 backdrop-blur-md">
          <form onSubmit={handleSubmit} className="mx-auto max-w-5xl px-4 py-4 sm:px-6">
            {/* Controls row for DMI modes */}
            {isDmiMode && (
              <div className="flex items-center gap-4 mb-3">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-light">Vertical:</span>
                  <div className="flex rounded-md border border-surface-3 bg-surface-1 p-0.5">
                    {(["immunology", "oncology"] as Vertical[]).map((v) => (
                      <button
                        key={v}
                        type="button"
                        onClick={() => setVertical(v)}
                        className={`rounded px-2.5 py-1 text-[11px] font-medium capitalize transition ${
                          vertical === v
                            ? "bg-accent-600/20 text-accent-400"
                            : "text-muted hover:text-gray-300"
                        }`}
                      >
                        {v}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* PubMed toggle (standard mode only) */}
            {mode === "standard" && (
              <div className="flex items-center gap-4 mb-3">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={includePubmed}
                    onChange={(e) => setIncludePubmed(e.target.checked)}
                    className="h-3.5 w-3.5 rounded border-surface-4 bg-surface-2 text-accent-500 focus:ring-accent-500/30"
                  />
                  <span className="text-xs text-muted-light">Include live PubMed results</span>
                </label>
              </div>
            )}

            <div className="flex gap-2 sm:gap-3">
              {mode === "target-risk" ? (
                <>
                  <input
                    type="text"
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    placeholder="Disease name (e.g., Rheumatoid arthritis)"
                    disabled={loading}
                    className="flex-1 rounded-lg border border-surface-3 bg-surface-1 px-3 py-3 text-sm text-gray-100 placeholder-muted outline-none transition focus:border-accent-500/50 focus:ring-1 focus:ring-accent-500/30 disabled:opacity-50 sm:px-4"
                  />
                  <input
                    type="text"
                    value={targetName}
                    onChange={(e) => setTargetName(e.target.value)}
                    placeholder="Target (e.g., TNF-alpha)"
                    disabled={loading}
                    className="flex-1 rounded-lg border border-surface-3 bg-surface-1 px-3 py-3 text-sm text-gray-100 placeholder-muted outline-none transition focus:border-accent-500/50 focus:ring-1 focus:ring-accent-500/30 disabled:opacity-50 sm:px-4"
                  />
                </>
              ) : mode === "compare" ? (
                <>
                  <input
                    type="text"
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    placeholder="Disease A (e.g., Rheumatoid arthritis)"
                    disabled={loading}
                    className="flex-1 rounded-lg border border-surface-3 bg-surface-1 px-3 py-3 text-sm text-gray-100 placeholder-muted outline-none transition focus:border-accent-500/50 focus:ring-1 focus:ring-accent-500/30 disabled:opacity-50 sm:px-4"
                  />
                  <span className="flex items-center text-xs text-muted font-semibold">vs</span>
                  <input
                    type="text"
                    value={diseaseB}
                    onChange={(e) => setDiseaseB(e.target.value)}
                    placeholder="Disease B (e.g., Lupus)"
                    disabled={loading}
                    className="flex-1 rounded-lg border border-surface-3 bg-surface-1 px-3 py-3 text-sm text-gray-100 placeholder-muted outline-none transition focus:border-accent-500/50 focus:ring-1 focus:ring-accent-500/30 disabled:opacity-50 sm:px-4"
                  />
                </>
              ) : (
                <input
                  type="text"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder={
                    mode === "disease-report"
                      ? "Enter disease name (e.g., Rheumatoid arthritis, Non-small cell lung cancer)..."
                      : mode === "hypothesis"
                        ? "Enter a research topic (e.g., IL-17 in psoriasis)..."
                        : "Ask about a disease mechanism, pathway, or therapeutic target..."
                  }
                  disabled={loading}
                  className="flex-1 rounded-lg border border-surface-3 bg-surface-1 px-3 py-3 text-sm text-gray-100 placeholder-muted outline-none transition focus:border-accent-500/50 focus:ring-1 focus:ring-accent-500/30 disabled:opacity-50 sm:px-4"
                />
              )}
              <button
                type="submit"
                disabled={
                  loading ||
                  !question.trim() ||
                  (mode === "compare" && !diseaseB.trim()) ||
                  (mode === "target-risk" && !targetName.trim())
                }
                className="rounded-lg bg-accent-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-accent-700 focus:outline-none focus:ring-2 focus:ring-accent-500 focus:ring-offset-2 focus:ring-offset-surface-0 disabled:cursor-not-allowed disabled:opacity-40 sm:px-5"
              >
                {loading ? (
                  <span className="flex items-center gap-2">
                    <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                    <span className="hidden sm:inline">Working</span>
                  </span>
                ) : (
                  <>
                    {MODE_CONFIG[mode].icon}{" "}
                    <span className="hidden sm:inline">{MODE_CONFIG[mode].label}</span>
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      </main>
    </div>
  );
}
