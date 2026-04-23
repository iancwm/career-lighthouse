"use client"

interface SourceStateSummaryProps {
  activeCount?: number | null
  supersededCount?: number | null
  staleCount?: number | null
  activeHitCount?: number | null
  supersededHitCount?: number | null
  loading?: boolean
  lastRefreshedAt?: string | null
  onExplainStaleSources?: () => void
}

function formatCount(value: number | null | undefined): string {
  if (value === null || value === undefined) return "Unknown"
  return Intl.NumberFormat("en-US").format(value)
}

function formatDate(value: string | null | undefined): string | null {
  if (!value) return null
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return null
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(parsed)
}

function SummaryTile({
  label,
  value,
  helper,
  tone,
  loading,
  actionLabel,
  onAction,
}: {
  label: string
  value: number | null | undefined
  helper: string
  tone: "active" | "superseded" | "stale"
  loading?: boolean
  actionLabel?: string
  onAction?: () => void
}) {
  const toneClasses = {
    active: "border-[#0F766E]/20 bg-[#0F766E]/10 text-[#0F766E]",
    superseded: "border-[#5F6B76]/20 bg-[#F6F1E8] text-[#5F6B76]",
    stale: "border-[#B45309]/20 bg-[#B45309]/10 text-[#B45309]",
  }

  return (
    <article
      className={`rounded-3xl border p-4 shadow-[0_12px_30px_rgba(31,41,55,0.04)] ${toneClasses[tone]}`}
      aria-label={`${label}: ${loading ? "loading" : formatCount(value)}`}
    >
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs uppercase tracking-[0.18em] text-current/75">{label}</p>
        <span className="h-2.5 w-2.5 rounded-full bg-current/60" aria-hidden="true" />
      </div>
      <p className="mt-3 font-display text-3xl leading-none text-[var(--cl-ink)]">
        {loading ? <span className="inline-block h-8 w-20 rounded bg-current/10 align-middle" /> : formatCount(value)}
      </p>
      <p className="mt-2 text-sm leading-6 text-[var(--cl-muted)]">{helper}</p>
      {actionLabel && onAction && (
        <button
          type="button"
          onClick={onAction}
          className="mt-3 inline-flex rounded-full border border-current/20 bg-white/70 px-3 py-1.5 text-xs font-medium text-current transition-colors hover:bg-white"
        >
          {actionLabel}
        </button>
      )}
    </article>
  )
}

export default function SourceStateSummary({
  activeCount,
  supersededCount,
  staleCount,
  activeHitCount,
  supersededHitCount,
  loading,
  lastRefreshedAt,
  onExplainStaleSources,
}: SourceStateSummaryProps) {
  const refreshedLabel = formatDate(lastRefreshedAt)

  return (
    <section className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-5 shadow-[0_12px_30px_rgba(31,41,55,0.06)]">
      <div className="flex flex-col gap-2 border-b border-[var(--cl-line)] pb-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="font-mono-display text-[11px] uppercase tracking-[0.26em] text-[var(--cl-secondary)]">Source-state summary</p>
          <h3 className="mt-2 font-display text-2xl text-[var(--cl-ink)]">Current source truth</h3>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--cl-muted)]">
            Active sources should be the only current citations. Superseded material stays visible as evidence, not as truth.
          </p>
        </div>
        {refreshedLabel && (
          <p className="font-mono-display text-[11px] uppercase tracking-[0.18em] text-[var(--cl-muted)]">
            Updated {refreshedLabel}
          </p>
        )}
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-3">
        <SummaryTile
          label="Active sources"
          value={activeCount}
          helper="Eligible for current citations."
          tone="active"
          loading={loading}
        />
        <SummaryTile
          label="Superseded sources"
          value={supersededCount}
          helper="Kept for audit and stale-source detection."
          tone="superseded"
          loading={loading}
        />
        <SummaryTile
          label="Stale sources"
          value={staleCount}
          helper="Indexed chunks still point at old material."
          tone="stale"
          loading={loading}
          actionLabel={staleCount && staleCount > 0 ? "Explain stale sources" : undefined}
          onAction={onExplainStaleSources}
        />
      </div>

      <div className="mt-4 flex flex-wrap gap-x-4 gap-y-2 text-sm text-[var(--cl-muted)]">
        <span>
          Active hits: <span className="font-mono-display text-[var(--cl-ink)]">{loading ? "—" : formatCount(activeHitCount)}</span>
        </span>
        <span>
          Superseded hits: <span className="font-mono-display text-[var(--cl-ink)]">{loading ? "—" : formatCount(supersededHitCount)}</span>
        </span>
      </div>
    </section>
  )
}
