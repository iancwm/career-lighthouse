export type FactLifecycle = "active" | "superseded" | "archived"

export type FactType =
  | "timeline_phase"
  | "alumni"
  | "interview_stage"
  | "compensation"
  | "skill_requirement"

export type FactSource = "counselor" | "inferred" | "direct_from_alumni" | string

export interface Fact {
  slug: string
  type: FactType | string
  data: Record<string, unknown>
  confidence: number
  source: FactSource
  timestamp: string
  lifecycle?: FactLifecycle | "deleted" | null
  deleted?: boolean
  last_updated?: string | null
  source_timestamp?: string | null
  source_label?: string | null
  source_type?: string | null
  superseded_by?: string | null
  audit_url?: string | null
}

const TYPE_BADGES: Record<string, string> = {
  alumni: "border-[#0F766E]/20 bg-[#0F766E]/10 text-[#0F766E]",
  timeline_phase: "border-[#B45309]/20 bg-[#B45309]/10 text-[#B45309]",
  interview_stage: "border-[#1F2937]/15 bg-[#1F2937]/10 text-[#1F2937]",
  compensation: "border-[#B45309]/20 bg-[#B45309]/10 text-[#B45309]",
  skill_requirement: "border-[#5F6B76]/20 bg-[#5F6B76]/10 text-[#5F6B76]",
}

const LIFECYCLE_BADGES: Record<FactLifecycle, string> = {
  active: "border-[#0F766E]/20 bg-[#0F766E]/10 text-[#0F766E]",
  superseded: "border-[#5F6B76]/20 bg-[#F6F1E8] text-[#5F6B76]",
  archived: "border-[#B45309]/20 bg-[#B45309]/10 text-[#B45309]",
}

export function normalizeFactLifecycle(fact: Pick<Fact, "lifecycle" | "deleted">): FactLifecycle {
  if (fact.lifecycle === "active" || fact.lifecycle === "superseded" || fact.lifecycle === "archived") {
    return fact.lifecycle
  }
  if (fact.lifecycle === "deleted") return "superseded"
  if (fact.deleted) return "superseded"
  return "active"
}

export function isActiveFact(fact: Pick<Fact, "lifecycle" | "deleted">): boolean {
  return normalizeFactLifecycle(fact) === "active"
}

export function sortFactsForDisplay(facts: Fact[]): Fact[] {
  const rank: Record<FactLifecycle, number> = {
    active: 0,
    superseded: 1,
    archived: 2,
  }
  return [...facts].sort((a, b) => {
    const lifecycleDelta = rank[normalizeFactLifecycle(a)] - rank[normalizeFactLifecycle(b)]
    if (lifecycleDelta !== 0) return lifecycleDelta
    const aTime = new Date(a.last_updated || a.source_timestamp || a.timestamp || 0).getTime()
    const bTime = new Date(b.last_updated || b.source_timestamp || b.timestamp || 0).getTime()
    return bTime - aTime
  })
}

export function getFactTypeLabel(type: string): string {
  return type.replace(/_/g, " ")
}

export function getFactTypeBadgeClass(type: string): string {
  return TYPE_BADGES[type] || "border-[#D8D0C4] bg-[#FFFDFC] text-[#5F6B76]"
}

export function getFactLifecycleLabel(lifecycle: FactLifecycle): string {
  switch (lifecycle) {
    case "active":
      return "● Active"
    case "superseded":
      return "○ Superseded"
    case "archived":
      return "◦ Archived"
  }
}

export function getFactLifecycleBadgeClass(lifecycle: FactLifecycle): string {
  return LIFECYCLE_BADGES[lifecycle]
}

export function getFactKeyValue(fact: Pick<Fact, "type" | "data">): string {
  const { type, data } = fact
  switch (type) {
    case "alumni":
      return data.name ? String(data.name) : "(unnamed)"
    case "timeline_phase":
      return data.phase_name ? String(data.phase_name) : "(unnamed)"
    case "interview_stage":
      return data.name ? String(data.name) : `Stage ${data.order || "?"}`
    case "compensation":
      return data.role_level ? String(data.role_level) : "(unnamed)"
    case "skill_requirement":
      return "(skill)"
    default:
      return "(unknown)"
  }
}

export function getFactSourceLabel(source: FactSource | null | undefined): string {
  if (!source) return "Unknown"
  const normalized = String(source).trim()
  if (!normalized) return "Unknown"
  return {
    counselor: "Counselor",
    inferred: "Inferred",
    direct_from_alumni: "Alumni",
  }[normalized] || normalized
}

export function formatUnknown(value: string | null | undefined): string {
  const clean = typeof value === "string" ? value.trim() : ""
  return clean ? clean : "Unknown"
}
