"use client"

interface AlumniDetectionPreview {
  summary_bullets?: string[]
  profile_updates?: Record<string, unknown>
  company_links?: Array<{
    company_name?: string
    company_slug?: string
    relationship?: string
    notes?: string
  }>
  facts?: Array<{
    slug?: string
    type?: string
    confidence?: number
    data?: Record<string, unknown>
  }>
}

interface AlumniDetectionModalProps {
  noteText: string
  preview: AlumniDetectionPreview
  onOpenAlumni: () => void
  onContinue: () => void
  onClose: () => void
  isLoading?: boolean
}

function hasBullets(preview: AlumniDetectionPreview): boolean {
  return Array.isArray(preview.summary_bullets) && preview.summary_bullets.length > 0
}

function hasCompanyLinks(preview: AlumniDetectionPreview): boolean {
  return Array.isArray(preview.company_links) && preview.company_links.length > 0
}

function hasFacts(preview: AlumniDetectionPreview): boolean {
  return Array.isArray(preview.facts) && preview.facts.length > 0
}

export default function AlumniDetectionModal({
  noteText,
  preview,
  onOpenAlumni,
  onContinue,
  onClose,
  isLoading,
}: AlumniDetectionModalProps) {
  const bullets = Array.isArray(preview.summary_bullets) ? preview.summary_bullets.filter((item): item is string => Boolean(item && item.trim())) : []
  const companies = Array.isArray(preview.company_links) ? preview.company_links : []
  const facts = Array.isArray(preview.facts) ? preview.facts : []

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Alumni note detected"
        className="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] shadow-[0_24px_80px_rgba(15,23,42,0.22)]"
      >
        <div className="border-b border-[var(--cl-line)] px-6 py-5">
          <p className="font-mono-display text-[11px] uppercase tracking-[0.26em] text-[var(--cl-secondary)]">Alumni detected</p>
          <h2 className="mt-2 font-display text-2xl text-[var(--cl-ink)]">This meeting note mentions alumni</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--cl-muted)]">
            We can move the note text into Alumni Records so it opens prefilled for extraction, or stay here and create the session anyway if this is a false positive.
          </p>
        </div>

        <div className="grid gap-6 overflow-y-auto p-6 lg:grid-cols-[1.1fr_0.9fr]">
          <section className="space-y-4">
            <div className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] p-5">
              <p className="text-xs uppercase tracking-[0.22em] text-[var(--cl-secondary)]">Detected note</p>
              <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-[var(--cl-ink)]">
                {noteText.length > 360 ? `${noteText.slice(0, 360)}…` : noteText}
              </p>
            </div>

            {bullets.length > 0 && (
              <div className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-5">
                <p className="text-xs uppercase tracking-[0.22em] text-[var(--cl-secondary)]">Why this matched</p>
                <ul className="mt-4 space-y-2">
                  {bullets.slice(0, 4).map((bullet, index) => (
                    <li key={`${bullet}-${index}`} className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-4 py-3 text-sm leading-6 text-[var(--cl-ink)]">
                      {bullet}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {!bullets.length && !hasCompanyLinks(preview) && !hasFacts(preview) && (
              <div className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-5 text-sm leading-6 text-[var(--cl-muted)]">
                The alumni preview found a signal in the note, but no extra summary was returned.
              </div>
            )}
          </section>

          <aside className="space-y-4">
            <div className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-5">
              <p className="font-mono-display text-[11px] uppercase tracking-[0.26em] text-[var(--cl-secondary)]">What will happen</p>
              <ol className="mt-4 space-y-3 text-sm leading-6 text-[var(--cl-muted)]">
                <li className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] p-4">
                  1. Save the note text in your browser session so it follows you to Alumni Records.
                </li>
                <li className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] p-4">
                  2. Open the Alumni page with the note already pasted into the extraction field.
                </li>
                <li className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] p-4">
                  3. Extract, review, and save the alumni profile from one place.
                </li>
              </ol>
            </div>

            {hasCompanyLinks(preview) && (
              <div className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-5">
                <p className="text-xs uppercase tracking-[0.22em] text-[var(--cl-secondary)]">Suggested companies</p>
                <ul className="mt-4 space-y-2">
                  {preview.company_links?.slice(0, 3).map((link, index) => (
                    <li key={`${link.company_slug ?? link.company_name ?? "company"}-${index}`} className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-4 py-3 text-sm text-[var(--cl-ink)]">
                      <p className="font-medium">{link.company_name || link.company_slug || "Linked company"}</p>
                      <p className="mt-1 text-[var(--cl-muted)]">
                        {link.relationship || "Company link"}
                        {link.notes ? ` · ${link.notes}` : ""}
                      </p>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {hasFacts(preview) && (
              <div className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-5">
                <p className="text-xs uppercase tracking-[0.22em] text-[var(--cl-secondary)]">Extracted facts</p>
                <ul className="mt-4 space-y-2">
                  {preview.facts?.slice(0, 3).map((fact, index) => (
                    <li key={`${fact.slug ?? fact.type ?? "fact"}-${index}`} className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-4 py-3 text-sm text-[var(--cl-ink)]">
                      <p className="font-medium">{fact.type || "fact"}</p>
                      <p className="mt-1 text-[var(--cl-muted)]">
                        {fact.slug || "untitled"}{fact.confidence !== undefined ? ` · confidence ${fact.confidence}%` : ""}
                      </p>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </aside>
        </div>

        <div className="border-t border-[var(--cl-line)] px-6 py-4">
          <p className="text-xs leading-5 text-[var(--cl-muted)]">
            If the alumni signal is wrong, choose <span className="font-medium text-[var(--cl-ink)]">Create Session Anyway</span> to keep moving in this flow.
          </p>
        </div>

        <div className="flex gap-3 border-t border-[var(--cl-line)] px-6 py-5">
          <button
            type="button"
            onClick={onContinue}
            disabled={isLoading}
            autoFocus
            className="flex-1 rounded-full border border-[var(--cl-accent)] bg-[var(--cl-accent)] px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[var(--cl-accent)]/90 disabled:opacity-60"
          >
            Create Session Anyway
          </button>
          <button
            type="button"
            onClick={onClose}
            disabled={isLoading}
            className="flex-1 rounded-full border border-[var(--cl-line)] bg-white/80 px-4 py-2.5 text-sm text-[var(--cl-ink)] transition-colors hover:border-[var(--cl-accent)]/60 hover:bg-white disabled:opacity-60"
          >
            Keep in Session Editor
          </button>
          <button
            type="button"
            onClick={onOpenAlumni}
            disabled={isLoading}
            className="flex-1 rounded-full border border-[var(--cl-accent)] bg-[var(--cl-accent)] px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[var(--cl-accent)]/90 disabled:opacity-60"
          >
            Open Alumni Records
          </button>
        </div>
      </div>
    </div>
  )
}
