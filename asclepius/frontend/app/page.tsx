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
import { useSessionManager } from "@/hooks/useSessionManager";
import type { ConversationEntry, Mode, UploadedImage, UploadedPdf } from "@/lib/types";
import { genId, PROSE_CLS, pmidToUrl } from "@/lib/utils";
import { MODE_CONFIG } from "@/components/ModeSwitcher";

import AuthHeader from "@/components/AuthHeader";
import CitationPanel from "@/components/CitationPanel";
import ClaudeBadge from "@/components/ClaudeBadge";
import CompareCard from "@/components/CompareCard";
import DiseaseReportCard from "@/components/DiseaseReportCard";
import FrozenStreamEntry from "@/components/FrozenStreamEntry";
import HypothesisCard from "@/components/HypothesisCard";
import ImageAnalysisCard from "@/components/ImageAnalysisCard";
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
    desc: "Answers are grounded in retrieved propositions, with citations traced back to primary literature",
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
      <div className="flex items-center gap-2 mb-2">
        <ClaudeBadge />
        <span className="text-[11px] text-muted">{label}</span>
      </div>
      {children}
    </div>
  );
}

// ------------------------------------------------------------------
// Inline image response card (non-streaming image query result)
// ------------------------------------------------------------------
function ImageResponseCard({ response }: { response: QueryResponse }) {
  return (
    <div className="mt-3 rounded-lg border border-surface-3 bg-surface-1 overflow-hidden">
      <div className="flex items-center gap-2 border-b border-surface-3 px-4 py-2.5">
        <ClaudeBadge
          model={response.model_used}
          sourceCount={response.sources?.length ?? 0}
        />
      </div>
      <div className="px-5 py-4">
        <div className={PROSE_CLS}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{response.answer}</ReactMarkdown>
        </div>
      </div>
      {(response.sources?.length ?? 0) > 0 && (
        <div className="border-t border-surface-3 bg-surface-0/40 px-4 py-2.5 flex flex-wrap gap-1.5">
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

  const { sessions, activeSessionId, selectSession, deleteSession, newSession } =
    useSessionManager(entries, mode);

  // Scroll to bottom on new content
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries, streaming.text]);

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

  // ------------------------------------------------------------------
  // Session management
  // ------------------------------------------------------------------
  function handleNewSession() {
    streaming.reset();
    setStreamingEntryId(null);
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
    setEntries(session.entries as ConversationEntry[]);
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
    [question, loading, mode, vertical, targetName, diseaseB, uploadedImage, includePubmed, streaming],
  );

  const isEmpty = entries.length === 0;
  const examples = EXAMPLE_PROMPTS[mode];
  const isLoading = loading || streaming.isStreaming;

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
        {/* Mobile header */}
        <header className="sticky top-0 z-20 lg:hidden border-b border-surface-3 bg-surface-0/80 backdrop-blur-md">
          <div className="flex items-center justify-between px-4 py-2.5 sm:px-5">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              aria-label="Toggle sidebar"
              className="flex h-8 w-8 items-center justify-center rounded-md text-muted hover:bg-surface-2 hover:text-gray-300 transition"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            </button>
            <AuthHeader />
          </div>
        </header>

        {/* Scrollable content */}
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
                Proposition-level hybrid retrieval with causal graph reasoning. Query any domain:
                mechanism mapping, target risk assessment, hypothesis generation.
              </p>

              <div className="mt-5 flex items-center gap-2">
                <div className="flex items-center gap-1.5 rounded-md border border-surface-3 bg-surface-1 px-2 py-1 text-[11px] font-medium text-muted-light">
                  <span className="h-1.5 w-1.5 rounded-full bg-accent-400" />
                  <span className="font-mono tracking-tight">Asclepius Engine</span>
                </div>
                <span className="text-xs text-muted">· Hybrid RAG · Causal Graph · Live PubMed</span>
              </div>

              {/* Example chips */}
              <div className="mt-8 flex flex-wrap gap-2 justify-center">
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
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-muted font-mono">
                    How it works
                  </p>
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
                        <p className="text-sm font-medium text-gray-100 leading-relaxed">
                          {entry.question}
                        </p>
                        <p className="text-[10px] text-muted mt-0.5 font-mono">
                          {MODE_CONFIG[entry.mode]?.label} ·{" "}
                          {new Date(entry.timestamp).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
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

                      {entry.loading && !isCurrentlyStreaming && (
                        <div className="flex items-center gap-3 rounded-lg border border-surface-3 bg-surface-1 px-4 py-3">
                          <ClaudeBadge isStreaming />
                          <span className="text-xs text-muted">
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

  function handleShowCitations(citations: Citation[]) {
    setPanelCitations(citations);
    setShowCitationPanel(true);
  }
}
