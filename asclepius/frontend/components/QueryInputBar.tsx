"use client";

import { type FormEvent, type RefObject } from "react";
import { AnimatePresence, motion } from "framer-motion";
import ModeSwitcher from "@/components/ModeSwitcher";
import type { Mode, UploadedImage, UploadedPdf } from "@/lib/types";

const INPUT_CLS =
  "h-11 flex-1 min-w-0 rounded-xl border border-line-2 bg-bg-3 px-3.5 text-sm text-ink placeholder-muted outline-none transition focus:border-green/70 focus:ring-2 focus:ring-green-faint disabled:opacity-40 font-sans";

interface Props {
  mode: Mode;
  onModeChange: (m: Mode) => void;
  question: string;
  onQuestionChange: (v: string) => void;
  diseaseB: string;
  onDiseaseBChange: (v: string) => void;
  targetName: string;
  onTargetNameChange: (v: string) => void;
  vertical: string;
  onVerticalChange: (v: string) => void;
  includePubmed: boolean;
  onIncludePubmedChange: (v: boolean) => void;
  verify: boolean;
  onVerifyChange: (v: boolean) => void;
  uploadedImage: UploadedImage | null;
  onClearImage: () => void;
  uploadedPdf: UploadedPdf | null;
  onClearPdf: () => void;
  imageInputRef: RefObject<HTMLInputElement>;
  pdfInputRef: RefObject<HTMLInputElement>;
  onImageFileSelected: (file: File) => void;
  onPdfFileSelected: (file: File) => void;
  isLoading: boolean;
  onSubmit: (e?: FormEvent<HTMLFormElement>) => void;
}

export default function QueryInputBar({
  mode, onModeChange,
  question, onQuestionChange,
  diseaseB, onDiseaseBChange,
  targetName, onTargetNameChange,
  vertical, onVerticalChange,
  includePubmed, onIncludePubmedChange,
  verify, onVerifyChange,
  uploadedImage, onClearImage,
  uploadedPdf, onClearPdf,
  imageInputRef, pdfInputRef,
  onImageFileSelected, onPdfFileSelected,
  isLoading,
  onSubmit,
}: Props) {
  const isDmiMode = mode === "disease-report" || mode === "target-risk";

  const submitDisabled =
    isLoading ||
    !question.trim() ||
    (mode === "compare" && !diseaseB.trim()) ||
    (mode === "target-risk" && !targetName.trim());

  return (
    <div className="border-t border-line bg-bg/95 backdrop-blur-md">
      <form onSubmit={onSubmit} className="mx-auto max-w-3xl px-4 py-3 sm:px-5">

        {/* Top row: mode switcher + options */}
        <div className="flex items-center justify-between mb-2.5 gap-3 flex-wrap">
          <ModeSwitcher mode={mode} onModeChange={onModeChange} />

          <div className="flex items-center gap-3 shrink-0">
            {isDmiMode && (
              <div className="flex items-center gap-1.5">
                <span className="text-[11px] text-faint font-mono">domain:</span>
                <input
                  type="text"
                  value={vertical}
                  onChange={(e) => onVerticalChange(e.target.value)}
                  placeholder="general"
                  className="w-28 h-7 rounded-md border border-line-2 bg-bg-3 px-2 text-[11px] text-ink-2 placeholder-muted outline-none transition focus:border-green/70 font-mono"
                />
              </div>
            )}

            {mode === "standard" && (
              <label className="flex items-center gap-2 cursor-pointer">
                <div
                  role="switch"
                  aria-checked={includePubmed}
                  aria-label="Include PubMed results"
                  className={`relative inline-flex h-4 w-7 items-center rounded-full transition-colors cursor-pointer ${
                    includePubmed ? "bg-green" : "bg-bg-4"
                  }`}
                  onClick={() => onIncludePubmedChange(!includePubmed)}
                >
                  <span
                    className={`inline-block h-3 w-3 rounded-full shadow transition-transform ${
                      includePubmed ? "translate-x-3.5 bg-bg" : "translate-x-0.5 bg-muted"
                    }`}
                  />
                </div>
                <span className={`text-[11px] select-none font-mono ${includePubmed ? "text-green" : "text-muted"}`}>PubMed live</span>
              </label>
            )}

            {(mode === "standard" || mode === "research") && (
              <label
                className="flex items-center gap-2 cursor-pointer"
                title="Re-check the generated answer against retrieved figures with Claude vision. Adds a verification pass after generation."
              >
                <div
                  role="switch"
                  aria-checked={verify}
                  aria-label="Verify answer against retrieved figures"
                  className={`relative inline-flex h-4 w-7 items-center rounded-full transition-colors cursor-pointer ${
                    verify ? "bg-green" : "bg-bg-4"
                  }`}
                  onClick={() => onVerifyChange(!verify)}
                >
                  <span
                    className={`inline-block h-3 w-3 rounded-full shadow transition-transform ${
                      verify ? "translate-x-3.5 bg-bg" : "translate-x-0.5 bg-muted"
                    }`}
                  />
                </div>
                <span className={`text-[11px] select-none font-mono ${verify ? "text-green" : "text-muted"}`}>Verify figures</span>
              </label>
            )}

            <span className="hidden sm:inline font-mono tabular-nums text-faint" style={{ fontSize: 10 }}>
              sonnet-4.6 · tier I
            </span>
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
              <div
                className={`flex items-center gap-2.5 rounded-md border px-3 py-2 text-xs ${
                  uploadedPdf.status === "done"
                    ? "border-accent-700/40 bg-accent-900/15 text-accent-400"
                    : uploadedPdf.status === "error"
                    ? "border-red-500/30 bg-red-500/8 text-red-400"
                    : "border-surface-3 bg-surface-1 text-muted-light"
                }`}
              >
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
                    <circle cx="12" cy="12" r="10" />
                    <line x1="12" y1="8" x2="12" y2="12" />
                    <line x1="12" y1="16" x2="12.01" y2="16" />
                  </svg>
                )}
                <span className="font-mono truncate max-w-[200px]">{uploadedPdf.fileName}</span>
                {uploadedPdf.status === "indexing" && (
                  <span className="text-muted">Extracting &amp; indexing propositions…</span>
                )}
                {uploadedPdf.message && <span className="text-muted">{uploadedPdf.message}</span>}
                <button
                  type="button"
                  aria-label="Remove PDF"
                  onClick={onClearPdf}
                  className="ml-auto shrink-0 text-muted hover:text-gray-300 transition"
                >
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
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
                  aria-label="Remove image"
                  onClick={onClearImage}
                  className="absolute -top-1.5 -right-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-surface-0 border border-surface-3 text-muted hover:text-red-400 transition"
                >
                  <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              </div>
              <div>
                <p className="text-[11px] text-gray-300 font-medium font-mono truncate max-w-[180px]">
                  {uploadedImage.fileName}
                </p>
                <p className="text-[10px] text-muted">Multimodal Vision · RAG Pipeline</p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Input row */}
        <div className="flex items-center gap-2">
          {/* Hidden file inputs */}
          <input
            ref={imageInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) onImageFileSelected(f);
              e.target.value = "";
            }}
          />
          <input
            ref={pdfInputRef}
            type="file"
            accept="application/pdf"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) onPdfFileSelected(f);
              e.target.value = "";
            }}
          />

          {/* Attach buttons */}
          <div className="flex items-center gap-1 shrink-0">
            <button
              type="button"
              aria-label="Attach scientific image for multimodal analysis"
              onClick={() => imageInputRef.current?.click()}
              className={`flex h-11 w-11 items-center justify-center rounded-xl border transition ${
                uploadedImage
                  ? "border-green/50 bg-green-faint text-green"
                  : "border-line-2 bg-bg-3 text-muted hover:bg-bg-4 hover:text-ink-2"
              }`}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <circle cx="8.5" cy="8.5" r="1.5" />
                <polyline points="21 15 16 10 5 21" />
              </svg>
            </button>
            <button
              type="button"
              aria-label="Upload PDF: figures are captioned and propositions indexed into the RAG pipeline"
              onClick={() => pdfInputRef.current?.click()}
              className={`flex h-11 w-11 items-center justify-center rounded-xl border transition ${
                uploadedPdf
                  ? "border-green/50 bg-green-faint text-green"
                  : "border-line-2 bg-bg-3 text-muted hover:bg-bg-4 hover:text-ink-2"
              }`}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
                <line x1="10" y1="9" x2="8" y2="9" />
              </svg>
            </button>
          </div>

          {/* Text inputs */}
          {mode === "target-risk" ? (
            <>
              <input
                type="text"
                value={question}
                onChange={(e) => onQuestionChange(e.target.value)}
                placeholder="Condition (e.g., Rheumatoid arthritis)"
                disabled={isLoading}
                className={INPUT_CLS}
              />
              <span className="text-[11px] font-semibold text-muted shrink-0 font-mono">·</span>
              <input
                type="text"
                value={targetName}
                onChange={(e) => onTargetNameChange(e.target.value)}
                placeholder="Target (e.g., TNF-alpha)"
                disabled={isLoading}
                className={INPUT_CLS}
              />
            </>
          ) : mode === "compare" ? (
            <>
              <input
                type="text"
                value={question}
                onChange={(e) => onQuestionChange(e.target.value)}
                placeholder="Topic A"
                disabled={isLoading}
                className={INPUT_CLS}
              />
              <span className="text-[11px] font-semibold text-muted shrink-0 font-mono">vs</span>
              <input
                type="text"
                value={diseaseB}
                onChange={(e) => onDiseaseBChange(e.target.value)}
                placeholder="Topic B"
                disabled={isLoading}
                className={INPUT_CLS}
              />
            </>
          ) : (
            <input
              type="text"
              value={question}
              onChange={(e) => onQuestionChange(e.target.value)}
              placeholder={
                uploadedImage
                  ? "Ask about this image…"
                  : mode === "disease-report"
                  ? "Disease or condition name…"
                  : mode === "hypothesis"
                  ? "Research topic…"
                  : mode === "research"
                  ? "Multi-part question; the agent will decompose & dispatch…"
                  : "Ask about any mechanism, pathway, or target…"
              }
              disabled={isLoading}
              className={INPUT_CLS}
            />
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={submitDisabled}
            aria-label="Submit query"
            className="flex h-11 shrink-0 items-center gap-1.5 rounded-xl px-4 text-sm font-semibold text-bg transition hover:brightness-110 focus:outline-none focus:ring-4 focus:ring-green-faint disabled:cursor-not-allowed disabled:opacity-40"
            style={{ background: "linear-gradient(180deg, var(--green), var(--green-2))" }}
          >
            {isLoading ? (
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-bg/40 border-t-bg block" />
            ) : (
              <>
                <span>Run</span>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="9 10 4 15 9 20" />
                  <path d="M20 4v7a4 4 0 0 1-4 4H4" />
                </svg>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
