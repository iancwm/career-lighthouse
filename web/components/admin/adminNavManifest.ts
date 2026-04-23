export type AdminView = "sessions" | "observability" | "student-insights" | "facts" | "traces" | "knowledge" | "update" | "careers" | "employers" | "alumni" | "tracks" | "resume" | "broken"

export type WorkstreamId = "career-wire" | "smart-counsellor" | "admin-room"

export interface DirectiveBannerContent {
  label: string
  whatYouDo: string
  whatHappens: string
}

export interface WorkstreamDefinition {
  id: WorkstreamId
  label: string
  description: string
  defaultView: AdminView
}

export interface AdminViewDefinition {
  id: AdminView
  label: string
  description: string
  workstreamId: WorkstreamId
  showInPrimaryNav: boolean
  showInDrawer: boolean
  isLegacyAlias?: boolean
  directive: DirectiveBannerContent
}

export const ADMIN_WORKSTREAMS: WorkstreamDefinition[] = [
  {
    id: "career-wire",
    label: "Career Wire",
    description: "Bring in new raw material, review it, and publish trusted career knowledge.",
    defaultView: "sessions",
  },
  {
    id: "smart-counsellor",
    label: "Smart Counsellor",
    description: "Prepare for a specific student using trusted knowledge and context.",
    defaultView: "resume",
  },
  {
    id: "admin-room",
    label: "Admin Room",
    description: "Monitor LLM behavior and inspect operational traces without cluttering daily counselling work.",
    defaultView: "observability",
  },
]

const TRACKS_DIRECTIVE: DirectiveBannerContent = {
  label: "Draft and publish tracks",
  whatYouDo: "Draft a career track from research notes, then publish or rollback when the content is ready.",
  whatHappens: "Publishing writes the track to the live career profile with versioned history for rollback.",
}

export const ADMIN_VIEWS: Record<AdminView, AdminViewDefinition> = {
  sessions: {
    id: "sessions",
    label: "Staging Area",
    description: "Bring in meeting notes and research before they become trusted knowledge.",
    workstreamId: "career-wire",
    showInPrimaryNav: true,
    showInDrawer: true,
    directive: {
      label: "Stage incoming material",
      whatYouDo: "Upload or paste counsellor notes, then open a staging session to review extracted update cards.",
      whatHappens: "Approved cards write to the knowledge base while discarded cards are ignored.",
    },
  },
  knowledge: {
    id: "knowledge",
    label: "Documents",
    description: "Upload career-knowledge files and check retrieval quality.",
    workstreamId: "career-wire",
    showInPrimaryNav: true,
    showInDrawer: true,
    directive: {
      label: "Manage knowledge documents",
      whatYouDo: "Upload files, inspect indexed documents, and validate retrieval quality against the current KB.",
      whatHappens: "Files are chunked, embedded, and indexed for semantic search.",
    },
  },
  update: {
    id: "update",
    label: "Quick Update",
    description: "Review one note or file update before saving it.",
    workstreamId: "career-wire",
    showInPrimaryNav: true,
    showInDrawer: true,
    directive: {
      label: "Quick update lane",
      whatYouDo: "Paste a short note or upload a file for one employer or track.",
      whatHappens: "You get a compact diff to review before saving it.",
    },
  },
  employers: {
    id: "employers",
    label: "Employer Records",
    description: "Maintain structured employer knowledge with full audit history.",
    workstreamId: "career-wire",
    showInPrimaryNav: true,
    showInDrawer: true,
    directive: {
      label: "Maintain employer records",
      whatYouDo: "View, create, edit, or retire employer records while keeping historical versions visible.",
      whatHappens: "Changes are written to employer YAML files with audit-friendly history.",
    },
  },
  alumni: {
    id: "alumni",
    label: "Alumni Records",
    description: "Maintain alumni profiles and link trusted contacts to the companies they know best.",
    workstreamId: "career-wire",
    showInPrimaryNav: true,
    showInDrawer: true,
    directive: {
      label: "Maintain alumni profiles",
      whatYouDo: "Create and edit alumni profiles, then connect each alumnus to relevant companies and referral context.",
      whatHappens: "Alumni profiles are written with company links, notes, and extraction previews for counselor review.",
    },
  },
  tracks: {
    id: "tracks",
    label: "Track Builder",
    description: "Draft, publish, rollback, and inspect track history in one place.",
    workstreamId: "career-wire",
    showInPrimaryNav: true,
    showInDrawer: true,
    directive: TRACKS_DIRECTIVE,
  },
  careers: {
    id: "careers",
    label: "Track Builder",
    description: "Legacy route kept for compatibility. Career Tracks now lives inside Track Builder.",
    workstreamId: "career-wire",
    showInPrimaryNav: false,
    showInDrawer: false,
    isLegacyAlias: true,
    directive: TRACKS_DIRECTIVE,
  },
  broken: {
    id: "broken",
    label: "Profile Repair",
    description: "Fix missing required fields in career profiles before they affect student guidance.",
    workstreamId: "career-wire",
    showInPrimaryNav: true,
    showInDrawer: true,
    directive: {
      label: "Repair broken profiles",
      whatYouDo: "Review profiles with missing required fields and auto-complete them with AI suggestions.",
      whatHappens: "Missing fields are filled from existing profile content and can be reviewed before save.",
    },
  },
  resume: {
    id: "resume",
    label: "Resume Review",
    description: "Generate quick session prep briefs from a student resume.",
    workstreamId: "smart-counsellor",
    showInPrimaryNav: true,
    showInDrawer: true,
    directive: {
      label: "Prepare for a student session",
      whatYouDo: "Paste a student resume to generate fit assessment, risks, and talking points.",
      whatHappens: "The system returns a prep brief you can use directly in the next counselling conversation.",
    },
  },
  observability: {
    id: "observability",
    label: "LLM Observability",
    description: "Track latency, retrieval quality, and source-state health across the system.",
    workstreamId: "admin-room",
    showInPrimaryNav: true,
    showInDrawer: true,
    directive: {
      label: "Inspect LLM traces",
      whatYouDo: "Review structured LLM calls, latency, and retrieval health before changing prompts.",
      whatHappens: "You can see what the model saw, how long it took, and where retrieval is drifting.",
    },
  },
  "student-insights": {
    id: "student-insights",
    label: "Student Insights",
    description: "Semantically search recent student questions from chat history.",
    workstreamId: "admin-room",
    showInPrimaryNav: true,
    showInDrawer: true,
    directive: {
      label: "Search student concerns",
      whatYouDo: "Run semantic search over student questions and narrow results with optional metadata filters.",
      whatHappens: "Results show matching student questions with timestamps and context labels for rapid counselling prep.",
    },
  },
  facts: {
    id: "facts",
    label: "Facts Dashboard",
    description: "Review captured structured facts and spot coverage gaps across employers and profiles.",
    workstreamId: "smart-counsellor",
    showInPrimaryNav: true,
    showInDrawer: true,
    directive: {
      label: "Review captured facts",
      whatYouDo: "Filter structured facts by employer, school, source, or type and inspect grouped coverage.",
      whatHappens: "The dashboard shows what the KB knows, where it came from, and what still needs review.",
    },
  },
  traces: {
    id: "traces",
    label: "Trace Explorer",
    description: "Deep-dive trace inspection for live sessions and operational debugging.",
    workstreamId: "admin-room",
    showInPrimaryNav: false,
    showInDrawer: false,
    directive: {
      label: "Trace explorer",
      whatYouDo: "Filter individual LLM traces by session, status, or operation.",
      whatHappens: "Started rows appear immediately so you can follow an active session while it is still processing.",
    },
  },
}

export function isAdminView(value: string | null): value is AdminView {
  if (!value) return false
  return Object.prototype.hasOwnProperty.call(ADMIN_VIEWS, value)
}

export function getViewDefinition(view: AdminView): AdminViewDefinition {
  return ADMIN_VIEWS[view]
}

export function getWorkstreamById(id: WorkstreamId): WorkstreamDefinition {
  const workstream = ADMIN_WORKSTREAMS.find((item) => item.id === id)
  if (!workstream) throw new Error(`Unknown workstream: ${id}`)
  return workstream
}

export function getWorkstreamForView(view: AdminView): WorkstreamDefinition {
  return getWorkstreamById(getViewDefinition(view).workstreamId)
}

interface GetWorkstreamViewsOptions {
  includeHidden?: boolean
  includeLegacy?: boolean
  forDrawer?: boolean
}

export function getWorkstreamViews(workstreamId: WorkstreamId, options?: GetWorkstreamViewsOptions): AdminViewDefinition[] {
  const includeHidden = options?.includeHidden ?? false
  const includeLegacy = options?.includeLegacy ?? false
  const forDrawer = options?.forDrawer ?? false

  return Object.values(ADMIN_VIEWS).filter((view) => {
    if (view.workstreamId !== workstreamId) return false
    if (!includeLegacy && view.isLegacyAlias) return false
    if (includeHidden) return true
    if (forDrawer) return view.showInDrawer
    return view.showInPrimaryNav
  })
}
