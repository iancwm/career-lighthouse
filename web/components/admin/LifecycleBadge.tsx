"use client"

import { FactLifecycle, getFactLifecycleBadgeClass, getFactLifecycleLabel, normalizeFactLifecycle } from "@/types/facts"

interface LifecycleBadgeProps {
  lifecycle?: FactLifecycle | "deleted" | null
  deleted?: boolean
}

export default function LifecycleBadge({ lifecycle, deleted }: LifecycleBadgeProps) {
  const resolved = normalizeFactLifecycle({ lifecycle, deleted })
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium ${getFactLifecycleBadgeClass(resolved)}`}
    >
      {getFactLifecycleLabel(resolved)}
    </span>
  )
}
