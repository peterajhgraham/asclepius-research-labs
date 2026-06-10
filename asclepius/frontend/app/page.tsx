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
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

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
import { useAgentStream } from "@/hooks/useAgentStream";
import { useSessionManager } from "@/hooks/useSessionManager";
import type { ConversationEntry, Mode, UploadedImage, UploadedPdf } from "@/lib/types";
import { genId, PROSE_CLS, pmidToUrl, modelDisplayName } from "@/lib/utils";
import { MODE_CONFIG } from "@/components/ModeSwitcher";

import AgentTrace from "@/components/AgentTrace";
import AuthHeader from "@/components/AuthHeader";
import CitationPanel from "@/components/CitationPanel";
import CompareCard from "@/components/CompareCard";
import DiseaseReportCard from "@/components/DiseaseReportCard";
import FrozenStreamEntry from "@/components/FrozenStreamEntry";
import HypothesisCard from "@/components/HypothesisCard";
import ImageAnalysisCard from "@/components/ImageAnalysisCard";
import { Logo } from "@/components/Logo";
import QueryInputBar from "@/components/QueryInputBar";
import ResponseCard from "@/components/ResponseCard";
import Sidebar from "@/components/Sidebar";
import StreamingResponse from "@/components/StreamingResponse";
import TargetRiskCard from "@/components/TargetRiskCard";

// ------------------------------------------------------------------
// Example prompts per mode
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
  research: [
    "Compare TNF blockade vs IL-17 blockade in psoriatic arthritis across efficacy, safety, and biomarkers",
    "What downstream targets of JAK1 have published 2024-2025 trial data?",
    "Map upstream interventions to suppress STAT3 in tumor microenvironments, then cross-reference with approved drugs",
    "How does anti-amyloid therapy compare to anti-tau across mechanism, trial endpoints, and adverse events?",
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

// ------------------------------------------------------------------
// PDF ingest helper
// ------------------------------------------------------------------
async function ingestDocument(
  file: File,
): Promise<{ propositions_indexed: number; images_captioned: number }> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch("/api/ingest", { method: "POST", body: formData });
  if (!res.ok) throw new Error(`Ingest failed: ${res.status}`);
  return res.json();
}

// ------------------------------------------------------------------
// Wrapper that attributes non-streaming response cards to the engine
// ------------------------------------------------------------------
function AiResponseWrapper({ children, label }: { children: React.ReactNode; label: string }) {
  return (
    <div>
      <div className="mb-2 flex items-center gap-2 text-[11px]">
        <span className="cc-dot is-done" aria-hidden="true" />
        <Logo size={13} />
        <span className="font-mono text-faint">{label}</span>
      </div>
      <div className="pl-[18px]">{children}</div>
    </div>
  );
}

// ------------------------------------------------------------------
// Inline image response card (non-streaming image query result)
// ------------------------------------------------------------------
function ImageResponseCard({ response }: { response: QueryResponse }) {
  return (
    <div className="mt-3">
      <div className="mb-2 flex items-center gap-2 text-[11px]">
        <span className="cc-dot is-done" aria-hidden="true" />
        <Logo size={13} />
        <span className="font-mono text-faint">
          {modelDisplayName(response.model_used ?? "")} · multimodal vision
        </span>
      </div>
      <div className="pl-[18px]">
        <div className={PROSE_CLS}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{response.answer}</ReactMarkdown>
        </div>
      {(response.sources?.length ?? 0) > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5 border-t border-line pt-2.5">
          {response.sources.slice(0, 8).map((s) => {
            const m = s.match(/PMID:\s*(\d+)/i);
            return m ? (
              <a
                key={s}
                href={pmidToUrl(m[1])}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded px-1.5 py-0.5 text-[10px] font-mono border border-accent-700/40 bg-accent-900/20 text-accent-400 hover:text-accent-300 transition"
              >
                {s}
              </a>
            ) : (
              <span
                key={s}
                className="rounded px-1.5 py-0.5 text-[10px] font-mono border border-surface-3 bg-surface-2 text-muted-light"
              >
                {s}
              </span>
            );
          })}
        </div>
      )}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------
// Main Page
// ------------------------------------------------------------------
export default function HomePage() {
  const [question, setQuestion] = useState("");
  const [diseaseB, setDiseaseB] = useState("");
  const [targetName, setTargetName] = useState("");
  const [vertical, setVertical] = useState("general");
  const [entries, setEntries] = useState<ConversationEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<Mode>("disease-report");
  const [includePubmed, setIncludePubmed] = useState(false);
  const [verify, setVerify] = useState(false);
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
  const agent = useAgentStream();
  const [streamingEntryId, setStreamingEntryId] = useState<string | null>(null);
  const [agentEntryId, setAgentEntryId] = useState<string | null>(null);

  const { sessions, activeSessionId, selectSession, deleteSession, newSession } =
    useSessionManager(entries, mode);

  // Scroll to bottom on new content
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries, streaming.text, agent.steps.length, agent.toolCalls.length, agent.finalAnswer]);

  // Freeze streaming entry when stream completes
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

  // Propagate streaming error to entry
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

  // Freeze agent entry when its stream completes
  useEffect(() => {
    if (agentEntryId && agent.done) {
      const snapshot = { ...agent };
      setEntries((prev) =>
        prev.map((e) =>
          e.id === agentEntryId ? { ...e, loading: false, agentState: snapshot } : e,
        ),
      );
      setAgentEntryId(null);
      setLoading(false);
    }
  }, [agent.done, agentEntryId]);

  // Propagate agent error to entry
  useEffect(() => {
    if (agentEntryId && agent.error) {
      setEntries((prev) =>
        prev.map((e) =>
          e.id === agentEntryId ? { ...e, loading: false, error: agent.error } : e,
        ),
      );
      setAgentEntryId(null);
      setLoading(false);
    }
  }, [agent.error, agentEntryId]);

  // ------------------------------------------------------------------
  // Session management
  // ------------------------------------------------------------------
  function handleNewSession() {
    streaming.reset();
    agent.reset();
    setStreamingEntryId(null);
    setAgentEntryId(null);
    setEntries([]);
    newSession();
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
    const session = selectSession(sessionId);
    if (!session) return;
    streaming.reset();
    agent.reset();
    setStreamingEntryId(null);
    setAgentEntryId(null);
    setLoading(false);
    setQuestion("");
    setDiseaseB("");
    setTargetName("");
    setUploadedImage(null);
    setUploadedPdf(null);
    setShowCitationPanel(false);
    // Sanitise any entries that were saved mid-request, they'd show a
    // permanent loading spinner otherwise.
    const sanitised = (session.entries as ConversationEntry[]).map((e) =>
      e.loading ? { ...e, loading: false, error: "Query did not complete." } : e,
    );
    setEntries(sanitised);
    setMode(session.mode);
    setSidebarOpen(false);
  }

  function handleDeleteSession(sessionId: string) {
    deleteSession(sessionId);
    if (activeSessionId === sessionId) handleNewSession();
  }

  // ------------------------------------------------------------------
  // Image upload
  // ------------------------------------------------------------------
  function processImageFile(file: File) {
    if (!file.type.startsWith("image/")) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      const dataUrl = e.target?.result as string;
      setUploadedImage({
        base64: dataUrl.split(",")[1],
        previewUrl: dataUrl,
        mediaType: file.type,
        fileName: file.name,
      });
    };
    reader.readAsDataURL(file);
  }

  // ------------------------------------------------------------------
  // PDF upload / ingest
  // ------------------------------------------------------------------
  async function handlePdfSelected(file: File) {
    setUploadedPdf({ file, fileName: file.name, status: "indexing" });
    try {
      const result = await ingestDocument(file);
      setUploadedPdf((prev) =>
        prev
          ? {
              ...prev,
              status: "done",
              message: `${result.propositions_indexed} propositions indexed · ${result.images_captioned} figures captioned`,
            }
          : null,
      );
    } catch {
      setUploadedPdf((prev) =>
        prev ? { ...prev, status: "error", message: "Failed to index document" } : null,
      );
    }
  }

  // ------------------------------------------------------------------
  // Drag-and-drop
  // ------------------------------------------------------------------
  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (!file) return;
    if (file.type.startsWith("image/")) processImageFile(file);
    else if (file.type === "application/pdf") handlePdfSelected(file);
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
  const handleSubmit = useCallback(
    async (e?: FormEvent<HTMLFormElement>) => {
      if (e) e.preventDefault();
      const trimmed = question.trim();
      if (!trimmed || loading) return;

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
            prev.map((e) =>
              e.id === entry.id
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

        if (mode === "research") {
          agent.reset();
          setAgentEntryId(entry.id);
          agent.stream(trimmed, verify);
          // keep loading flag true; the agent freezing effect clears it on done/error
          return;
        }

        if (mode === "disease-report") {
          const result = await generateDiseaseReport({ disease_name: trimmed, vertical });
          setEntries((prev) =>
            prev.map((e) =>
              e.id === entry.id ? { ...e, diseaseReportResponse: result, loading: false } : e,
            ),
          );
        } else if (mode === "target-risk") {
          const result = await generateTargetRiskReport({
            disease_name: trimmed,
            target_name: targetName.trim(),
            vertical,
          });
          setEntries((prev) =>
            prev.map((e) =>
              e.id === entry.id ? { ...e, targetRiskResponse: result, loading: false } : e,
            ),
          );
        } else if (mode === "compare") {
          const result = await compareDiseases({
            disease_a: trimmed,
            disease_b: diseaseB.trim() || trimmed,
          });
          setEntries((prev) =>
            prev.map((e) =>
              e.id === entry.id ? { ...e, compareResponse: result, loading: false } : e,
            ),
          );
        } else if (mode === "hypothesis") {
          const result = await generateHypotheses({ topic: trimmed });
          setEntries((prev) =>
            prev.map((e) =>
              e.id === entry.id ? { ...e, hypothesisResponse: result, loading: false } : e,
            ),
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
          prev.map((e) =>
            e.id === entry.id ? { ...e, error: detail, loading: false } : e,
          ),
        );
      } finally {
        setLoading(false);
      }
    },
    // streaming.stream / streaming.reset are stable useCallback refs; including
    // the entire streaming object would recreate handleSubmit on every SSE token.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [question, loading, mode, vertical, targetName, diseaseB, uploadedImage, includePubmed, verify, streaming.stream, streaming.reset, agent.stream, agent.reset],
  );

  function handleShowCitations(citations: Citation[]) {
    setPanelCitations(citations);
    setShowCitationPanel(true);
  }

  const isEmpty = entries.length === 0;
  const examples = EXAMPLE_PROMPTS[mode];
  const isLoading = loading || streaming.isStreaming || agent.isStreaming;

  function handleExampleClick(example: string) {
    if (mode === "compare") {
      const p = example.split(" vs ");
      setQuestion(p[0] || example);
      setDiseaseB(p[1] || "");
    } else if (mode === "target-risk") {
      const p = example.split(" in ");
      setTargetName(p[0] || "");
      setQuestion(p[1] || example);
    } else {
      setQuestion(example);
    }
  }

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------
  return (
    <div
      className="flex h-screen bg-bg overflow-hidden"
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
            className="fixed inset-0 z-50 flex items-center justify-center bg-bg/80 backdrop-blur-sm border-2 border-dashed border-green/40"
          >
            <div className="text-center">
              <p className="font-display text-2xl text-ink">Drop to attach</p>
              <p className="text-sm text-muted mt-1 font-mono">Images · PDF documents</p>
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
        {/* Mobile header */}
        <header className="sticky top-0 z-20 lg:hidden border-b border-line bg-bg/80 backdrop-blur-md">
          <div className="flex items-center justify-between px-4 py-2.5 sm:px-5">
            <div className="flex items-center gap-2.5">
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                aria-label="Toggle sidebar"
                className="flex h-8 w-8 items-center justify-center rounded-md text-muted hover:bg-bg-3 hover:text-ink transition"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                  <line x1="3" y1="6" x2="21" y2="6" />
                  <line x1="3" y1="12" x2="21" y2="12" />
                  <line x1="3" y1="18" x2="21" y2="18" />
                </svg>
              </button>
              <Logo size={20} />
              <span className="font-sans font-semibold text-ink text-sm tracking-tight">Asclepius</span>
            </div>
            <AuthHeader />
          </div>
        </header>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto">

          {/* Landing */}
          {isEmpty && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
              className="mx-auto flex min-h-full w-full max-w-2xl flex-col items-center justify-center px-6 py-16 text-center"
            >
              {/* Brand mark */}
              <Logo size={32} />

              {/* Headline */}
              <h1 className="mt-6 font-display leading-[1.1] text-ink text-[2rem] sm:text-[2.5rem]">
                The literature, <em className="italic text-green">read carefully.</em>
              </h1>

              {/* Subtitle */}
              <p className="mt-4 max-w-md text-sm leading-relaxed text-muted">
                Multimodal Agentic RAG System over PubMed. Every claim traced to a primary source.
              </p>

              {/* Example prompts — terminal-style suggestions */}
              <div className="mt-10 w-full text-left">
                <p className="mb-2.5 px-1 font-mono uppercase text-faint" style={{ fontSize: 10, letterSpacing: "0.16em" }}>
                  Try a prompt
                </p>
                <div className="overflow-hidden rounded-xl border border-line-2 bg-bg-2">
                  {examples.map((example, i) => (
                    <button
                      key={example}
                      onClick={() => handleExampleClick(example)}
                      className={`group flex w-full items-start gap-2.5 px-4 py-2.5 text-left font-mono text-[12.5px] leading-relaxed text-ink-2 transition hover:bg-bg-3 ${
                        i > 0 ? "border-t border-line" : ""
                      }`}
                    >
                      <span className="select-none text-faint transition group-hover:text-green">&gt;</span>
                      <span className="flex-1">{example}</span>
                    </button>
                  ))}
                </div>
              </div>
            </motion.div>
          )}

          {/* Results */}
          {!isEmpty && (
            <div className="mx-auto max-w-4xl px-4 py-8 space-y-8 sm:px-6">
              {entries.map((entry) => {
                const isCurrentlyStreaming = entry.id === streamingEntryId;
                return (
                  <motion.div
                    key={entry.id}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    {/* User prompt — Claude Code `>` style */}
                    <div className="mb-4">
                      {entry.imagePreviewUrl && (
                        <img
                          src={entry.imagePreviewUrl}
                          alt="Uploaded"
                          className="mb-2 ml-[22px] h-16 w-16 rounded-md object-cover border border-line"
                        />
                      )}
                      <div className="flex items-baseline gap-2.5">
                        <span className="select-none font-mono text-[15px] leading-snug text-green">&gt;</span>
                        <p className="min-w-0 flex-1 text-[15px] leading-snug text-ink">
                          {entry.question}
                        </p>
                      </div>
                      <p className="mt-1 pl-[22px] font-mono uppercase text-faint" style={{ fontSize: 10, letterSpacing: "0.12em" }}>
                        {MODE_CONFIG[entry.mode]?.label} ·{" "}
                        {new Date(entry.timestamp).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </p>
                    </div>

                    {/* Response — assistant markers align with the user `>` */}
                    <div className="space-y-2">
                      {entry.error && (
                        <div className="rounded-lg border border-risk/25 bg-risk/8 px-4 py-3 text-sm text-risk">
                          {entry.error}
                        </div>
                      )}

                      {isCurrentlyStreaming && (
                        <StreamingResponse
                          state={streaming}
                          onShowCitations={() =>
                            handleShowCitations(streaming.citations)
                          }
                        />
                      )}

                      {!isCurrentlyStreaming &&
                        entry.mode === "standard" &&
                        entry.streamedText && (
                          <FrozenStreamEntry
                            entry={entry}
                            onShowCitations={handleShowCitations}
                          />
                        )}

                      {/* Research agent: live stream or frozen replay */}
                      {entry.id === agentEntryId && (
                        <AgentTrace state={agent} question={entry.question} />
                      )}
                      {entry.id !== agentEntryId && entry.agentState && (
                        <AgentTrace state={entry.agentState} question={entry.question} />
                      )}

                      {entry.loading && !isCurrentlyStreaming && entry.id !== agentEntryId && (
                        <div className="flex items-center gap-2 text-[11px]">
                          <span className="cc-dot is-active" aria-hidden="true" />
                          <Logo size={13} />
                          <span className="hx-spin" />
                          <span className="font-mono text-muted">
                            {entry.mode === "disease-report"
                              ? "Mapping disease mechanisms…"
                              : entry.mode === "target-risk"
                              ? "Assessing target tractability…"
                              : entry.mode === "compare"
                              ? "Running comparative analysis…"
                              : entry.mode === "hypothesis"
                              ? "Generating hypotheses…"
                              : entry.imagePreviewUrl
                              ? "Analyzing image…"
                              : "Reasoning across literature…"}
                          </span>
                        </div>
                      )}

                      {entry.imageAnalysis && (
                        <ImageAnalysisCard
                          analysis={entry.imageAnalysis}
                          previewUrl={entry.imagePreviewUrl}
                        />
                      )}

                      {entry.response && entry.imagePreviewUrl && (
                        <ImageResponseCard response={entry.response} />
                      )}

                      {entry.response &&
                        entry.mode === "standard" &&
                        !entry.streamedText &&
                        !entry.imagePreviewUrl && (
                          <AiResponseWrapper label="Standard retrieval">
                            <ResponseCard data={entry.response} />
                          </AiResponseWrapper>
                        )}

                      {entry.diseaseReportResponse && (
                        <AiResponseWrapper label="Mechanism Report · DMI Engine">
                          <DiseaseReportCard data={entry.diseaseReportResponse} />
                        </AiResponseWrapper>
                      )}
                      {entry.targetRiskResponse && (
                        <AiResponseWrapper label="Target Risk Assessment · DMI Engine">
                          <TargetRiskCard data={entry.targetRiskResponse} />
                        </AiResponseWrapper>
                      )}
                      {entry.compareResponse && (
                        <AiResponseWrapper label="Comparative Analysis · RAG Pipeline">
                          <CompareCard data={entry.compareResponse} />
                        </AiResponseWrapper>
                      )}
                      {entry.hypothesisResponse && (
                        <AiResponseWrapper label="Hypothesis Generation · RAG Pipeline">
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

        <QueryInputBar
          mode={mode}
          onModeChange={setMode}
          question={question}
          onQuestionChange={setQuestion}
          diseaseB={diseaseB}
          onDiseaseBChange={setDiseaseB}
          targetName={targetName}
          onTargetNameChange={setTargetName}
          vertical={vertical}
          onVerticalChange={setVertical}
          includePubmed={includePubmed}
          onIncludePubmedChange={setIncludePubmed}
          verify={verify}
          onVerifyChange={setVerify}
          uploadedImage={uploadedImage}
          onClearImage={() => setUploadedImage(null)}
          uploadedPdf={uploadedPdf}
          onClearPdf={() => setUploadedPdf(null)}
          imageInputRef={imageInputRef}
          pdfInputRef={pdfInputRef}
          onImageFileSelected={processImageFile}
          onPdfFileSelected={handlePdfSelected}
          isLoading={isLoading}
          onSubmit={handleSubmit}
        />
      </main>

      <CitationPanel
        citations={panelCitations}
        isOpen={showCitationPanel}
        onClose={() => setShowCitationPanel(false)}
      />
    </div>
  );
}
