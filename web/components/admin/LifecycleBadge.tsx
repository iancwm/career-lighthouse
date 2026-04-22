"use client"

import { FactLifecycle, getFactLifecycleBadgeClass, getFactLifecycleLabel, normalizeFactLifecycle } from "@/types/facts"

interface LifecycleBadgeProps {
  lifecycle?: FactLifecycle | "deleted" | null
  deleted?: boolean
  label?: string
  className?: string
}

function getUnknownBadgeClass(): string {
  return "border-[var(--cl-line)] bg-[var(--cl-surface)] text-[var(--cl-muted)]"
}

export default function LifecycleBadge({ lifecycle, deleted, label, className }: LifecycleBadgeProps) {
  const hasKnownLifecycle = lifecycle === "active" || lifecycle === "superseded" || lifecycle === "archived" || deleted === true || deleted === false
  const resolved = hasKnownLifecycle ? normalizeFactLifecycle({ lifecycle, deleted }) : null
  const badgeLabel = resolved ? getFactLifecycleLabel(resolved) : label || "Unknown"
  const badgeClass = resolved ? getFactLifecycleBadgeClass(resolved) : getUnknownBadgeClass()
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium ${badgeClass} ${className || ""}`.trim()}
      aria-label={`Lifecycle state: ${badgeLabel.replace(/^●\s*/, "").replace(/^○\s*/, "").replace(/^◦\s*/, "")}`}
    >
      {resolved ? badgeLabel : badgeLabel}
    </span>
  )
}
