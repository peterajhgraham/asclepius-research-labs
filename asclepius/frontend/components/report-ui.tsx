"use client";

import { useState } from "react";

// Shared building blocks for result documents (Mechanism Report, Target Risk):
// hairline-separated sections, quiet citation chips, neutral tags.

export function PmidLink({ pmid }: { pmid: string }) {
  const clean = pmid.replace(/^PMID:?\s*/i, "").trim();
  return (
    <a
      href={`https://pubmed.ncbi.nlm.nih.gov/${clean}/`}
      target="_blank"
      rel="noopener noreferrer"
      className="rounded bg-bg-3 px-1.5 py-0.5 font-mono text-[11px] text-muted transition hover:bg-bg-4 hover:text-ink"
    >
      {clean}
    </a>
  );
}

export function PmidList({ pmids }: { pmids: string[] }) {
  if (!pmids.length) return null;
  return (
    <div className="mt-2.5 flex flex-wrap gap-1">
      {pmids.map((p, i) => (
        <PmidLink key={i} pmid={p} />
      ))}
    </div>
  );
}

// A neutral content chip (genes, biomarkers).
export function Tag({ children }: { children: React.ReactNode }) {
  return <span className="rounded-md bg-bg-3 px-2 py-0.5 font-mono text-xs text-ink-2">{children}</span>;
}

export function Section({
  label,
  count,
  children,
  defaultOpen = true,
}: {
  label: string;
  count?: number;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="border-t border-line">
      <button
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="group flex w-full items-center gap-2 py-3.5 text-left"
      >
        <span className="text-[13px] font-medium text-ink">{label}</span>
        {count !== undefined && <span className="text-xs tabular-nums text-faint">{count}</span>}
        <svg
          className={`ml-auto h-3.5 w-3.5 shrink-0 text-faint transition group-hover:text-muted ${open ? "" : "-rotate-90"}`}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>
      {open && <div className="pb-5">{children}</div>}
    </section>
  );
}
