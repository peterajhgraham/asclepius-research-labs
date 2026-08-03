"use client";

import { Logo } from "@/components/Logo";

interface Props {
  analysis: string;
  previewUrl?: string;
}

export default function ImageAnalysisCard({ analysis, previewUrl }: Props) {
  return (
    <div className="mt-4 rounded-lg border border-surface-3 bg-surface-1 overflow-hidden animate-fade-in">
      <div className="flex items-center gap-2 border-b border-surface-3 px-4 py-2.5">
        <svg
          width="13" height="13" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth="2" strokeLinecap="round"
          className="text-accent-400 shrink-0"
        >
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <circle cx="8.5" cy="8.5" r="1.5" />
          <polyline points="21 15 16 10 5 21" />
        </svg>
        <span className="text-xs font-semibold text-gray-200 tracking-tight">Visual Analysis</span>
        <span className="ml-auto flex items-center gap-1.5 font-mono text-[10px] text-faint">
          <Logo size={11} />
          <span>sonnet · vision</span>
        </span>
      </div>
      <div className="p-4 flex gap-4">
        {previewUrl && (
          <img
            src={previewUrl}
            alt="Uploaded"
            className="h-24 w-24 shrink-0 rounded-md object-cover border border-surface-3"
          />
        )}
        <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">{analysis}</p>
      </div>
    </div>
  );
}
