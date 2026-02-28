import type { QueryResponse } from "@/lib/api";

interface ResponseCardProps {
  data: QueryResponse;
}

export default function ResponseCard({ data }: ResponseCardProps) {
  return (
    <div className="mt-8 w-full max-w-2xl rounded-2xl border border-brand-200 bg-brand-50 p-6 shadow-sm">
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-brand-600">
        Analysis
      </h2>
      <p className="text-base leading-relaxed text-gray-800">{data.answer}</p>

      {data.sources.length > 0 && (
        <div className="mt-6">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-widest text-brand-600">
            Sources
          </h3>
          <ul className="space-y-1">
            {data.sources.map((source, index) => (
              <li
                key={index}
                className="text-sm text-gray-500"
              >
                {source}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
