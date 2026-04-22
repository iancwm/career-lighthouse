"use client"

interface StatCardsProps {
  totalDocs: number
  totalChunks: number
  lowConfidenceCount: number
  avgMatchScore: number | null
  diversityScore: number | null
}

function scoreColor(value: number | null, greenThresh: number, amberThresh: number): string {
  if (value === null) return "text-[var(--cl-muted)]"
  if (value >= greenThresh) return "text-[#2F6B4F]"
  if (value >= amberThresh) return "text-amber-600"
  return "text-red-600"
}

function StatTile({
  label,
  value,
  valueClassName,
  helper,
}: {
  label: string
  value: string
  valueClassName?: string
  helper?: string
}) {
  return (
    <article className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface)] px-4 py-4 shadow-[0_8px_18px_rgba(31,41,55,0.04)]">
      <p className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">{label}</p>
      <p className={`mt-2 font-display text-2xl leading-none ${valueClassName || "text-[var(--cl-ink)]"}`}>{value}</p>
      {helper && <p className="mt-2 text-sm leading-6 text-[var(--cl-muted)]">{helper}</p>}
    </article>
  )
}

export default function StatCards({
  totalDocs,
  totalChunks,
  lowConfidenceCount,
  avgMatchScore,
  diversityScore,
}: StatCardsProps) {
  const cards = [
    {
      label: "Documents",
      value: totalDocs.toString(),
      helper: "Ledgered source records.",
    },
    {
      label: "Chunks",
      value: totalChunks.toString(),
      helper: "Indexed retrieval payloads.",
    },
    {
      label: "Weak Queries (7d)",
      value: lowConfidenceCount.toString(),
      helper: "Matches that need attention.",
      valueClassName: lowConfidenceCount > 5 ? "text-red-600" : "text-[var(--cl-ink)]",
    },
    {
      label: "Avg Match Score",
      value: avgMatchScore !== null ? avgMatchScore.toFixed(2) : "Unknown",
      helper: "Average retrieval confidence.",
      valueClassName: scoreColor(avgMatchScore, 0.5, 0.35),
    },
    {
      label: "Retrieval Diversity",
      value: diversityScore !== null ? diversityScore.toFixed(1) : "Unknown",
      helper: "Spread across sources.",
      valueClassName: scoreColor(diversityScore, 3.0, 1.5),
    },
  ]

  return (
    <section className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-5 shadow-[0_12px_30px_rgba(31,41,55,0.06)]">
      <div className="border-b border-[var(--cl-line)] pb-4">
        <p className="font-mono-display text-[11px] uppercase tracking-[0.26em] text-[var(--cl-secondary)]">KB health</p>
        <h3 className="mt-2 font-display text-2xl text-[var(--cl-ink)]">Key numbers</h3>
        <p className="mt-2 text-sm leading-6 text-[var(--cl-muted)]">
          These are the quick-read metrics. Source-state truth still lives above this block.
        </p>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {cards.map((card) => (
          <StatTile
            key={card.label}
            label={card.label}
            value={card.value}
            helper={card.helper}
            valueClassName={card.valueClassName}
          />
        ))}
      </div>
    </section>
  )
}
