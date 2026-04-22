"use client"

interface DocCoverageItem {
  filename: string
  chunk_count: number
  coverage_status: "good" | "thin"
  has_overlap_warning: boolean
}

interface Props {
  docs: DocCoverageItem[]
}

export default function DocCoverageList({ docs }: Props) {
  return (
    <section className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-5 shadow-[0_12px_30px_rgba(31,41,55,0.06)]">
      <div className="border-b border-[var(--cl-line)] pb-4">
        <p className="font-mono-display text-[11px] uppercase tracking-[0.26em] text-[var(--cl-secondary)]">Coverage</p>
        <h3 className="mt-2 font-display text-2xl text-[var(--cl-ink)]">Document coverage</h3>
        <p className="mt-2 text-sm leading-6 text-[var(--cl-muted)]">
          Thin coverage and overlap warnings point to documents that may need another pass.
        </p>
      </div>

      {!docs.length ? (
        <p className="mt-4 text-sm text-[var(--cl-muted)]">No documents uploaded yet.</p>
      ) : (
        <ul className="mt-4 space-y-2">
          {docs.map((doc) => (
            <li
              key={doc.filename}
              className="flex flex-col gap-3 rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface)] px-4 py-3 md:flex-row md:items-center md:justify-between"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium text-[var(--cl-ink)]">{doc.filename}</p>
                <p className="mt-1 text-sm text-[var(--cl-muted)]">
                  <span className="font-mono-display text-[var(--cl-ink)]">{doc.chunk_count}</span> chunks
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2 md:justify-end">
                {doc.has_overlap_warning && (
                  <span
                    title="This document overlaps with another source. See the redundancy panel."
                    className="rounded-full border border-amber-200 bg-amber-100 px-2.5 py-1 text-xs font-medium text-amber-700"
                  >
                    overlap
                  </span>
                )}
                <span
                  className={`rounded-full border px-2.5 py-1 text-xs font-medium ${
                    doc.coverage_status === "good"
                      ? "border-green-200 bg-green-100 text-green-700"
                      : "border-amber-200 bg-amber-100 text-amber-700"
                  }`}
                >
                  {doc.coverage_status}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
