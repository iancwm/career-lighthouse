"use client"

interface LowConfidenceQuery {
  ts: string
  query_text: string
  max_score: number
  doc_matched: string | null
}

interface Props {
  avgMatchScore: number | null
  queries: LowConfidenceQuery[]
}

export default function LowConfidenceLog({ avgMatchScore, queries }: Props) {
  return (
    <section className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-5 shadow-[0_12px_30px_rgba(31,41,55,0.06)]">
      <div className="border-b border-[var(--cl-line)] pb-4">
        <p className="font-mono-display text-[11px] uppercase tracking-[0.26em] text-[var(--cl-secondary)]">Weak queries</p>
        <h3 className="mt-2 font-display text-2xl text-[var(--cl-ink)]">
          Weak Queries (7d)
          <span className="ml-2 text-sm font-normal text-[var(--cl-muted)]">score &lt; 0.35</span>
        </h3>
      </div>

      {avgMatchScore === null ? (
        <p className="mt-4 text-sm text-[var(--cl-muted)]">No data yet — use the student chat to generate query history.</p>
      ) : queries.length === 0 ? (
        <p className="mt-4 text-sm text-[#2F6B4F]">No weak matches in the last 7 days.</p>
      ) : (
        <ul className="mt-4 space-y-3">
          {queries.map((q, index) => (
            <li key={`${q.ts}-${index}`} className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface)] px-4 py-4">
              <div className="flex items-start justify-between gap-3">
                <p className="min-w-0 flex-1 text-sm leading-6 text-[var(--cl-ink)]">{q.query_text}</p>
                <span className="rounded-full border border-red-200 bg-red-100 px-2.5 py-1 text-xs font-mono text-red-700">
                  {q.max_score.toFixed(3)}
                </span>
              </div>
              <div className="mt-3 h-1.5 rounded-full bg-[var(--cl-surface-2)]" aria-hidden="true">
                <div
                  className="h-1.5 rounded-full bg-red-400"
                  style={{ width: `${Math.min(q.max_score * 100, 100)}%` }}
                />
              </div>
              <p className="mt-2 text-xs text-[var(--cl-muted)]">
                {new Date(q.ts).toLocaleString()}
                {q.doc_matched && ` · ${q.doc_matched}`}
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
