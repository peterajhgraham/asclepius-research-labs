export function modelDisplayName(model: string): string {
  if (model.includes("haiku")) return "Rapid · Tier I";
  if (model.includes("sonnet")) return "Balanced · Tier II";
  if (model.includes("opus")) return "Deep · Tier III";
  return "Asclepius Engine";
}

export function genId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

export function pmidToUrl(pmid: string): string {
  return `https://pubmed.ncbi.nlm.nih.gov/${pmid}`;
}

export function sessionTitle(entries: { question: string }[]): string {
  if (!entries.length) return "New session";
  const first = entries[0].question;
  return first.length > 40 ? first.slice(0, 40) + "…" : first;
}

export const PROSE_CLS = [
  "prose prose-invert prose-sm max-w-none",
  "prose-headings:text-gray-100 prose-headings:font-semibold prose-headings:tracking-tight",
  "prose-p:text-gray-300 prose-p:leading-relaxed",
  "prose-strong:text-gray-100 prose-strong:font-semibold",
  "prose-code:text-accent-300 prose-code:bg-surface-2 prose-code:rounded prose-code:px-1 prose-code:text-xs prose-code:font-mono",
  "prose-ul:text-gray-300 prose-li:my-0.5",
  "prose-h2:text-base prose-h3:text-sm prose-h4:text-xs",
].join(" ");

export const LS_KEY = "asclepius_sessions_v2";
