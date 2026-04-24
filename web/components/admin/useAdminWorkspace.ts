"use client"

import { useEffect, useRef, useState, type Dispatch, type RefObject, type SetStateAction } from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { adminFetch } from "@/lib/admin-api"
import type { AdminView, AdminViewDefinition, WorkstreamDefinition } from "@/components/admin/adminNavManifest"
import {
  getViewDefinition,
  getWorkstreamForView,
  getWorkstreamViews,
  isAdminView,
} from "@/components/admin/adminNavManifest"

export interface KBHealth {
  total_docs: number
  total_chunks: number
  avg_match_score: number | null
  retrieval_diversity_score: number | null
  low_confidence_queries: {
    ts: string
    query_text: string
    max_score: number
    doc_matched: string | null
  }[]
  doc_coverage: {
    filename: string
    chunk_count: number
    coverage_status: "good" | "thin"
    has_overlap_warning: boolean
  }[]
  high_overlap_pairs: {
    doc_a: string
    doc_b: string
    overlap_pct: number
    recommendation: string
  }[]
}

interface BuildUrlInput {
  view?: AdminView | null
  sessionId?: string | null
  trackSlug?: string | null
}

export interface AdminWorkspaceController {
  view: AdminView
  viewParam: string | null
  sessionParam: string | null
  trackParam: string | null
  currentSurface: AdminViewDefinition
  activeWorkstream: WorkstreamDefinition
  workstreamViews: AdminViewDefinition[]
  activeSurfaceId: AdminView
  refreshKey: number
  health: KBHealth | null
  healthError: boolean
  healthLoading: boolean
  drawerOpen: boolean
  toggleButtonRef: RefObject<HTMLButtonElement>
  setRefreshKey: Dispatch<SetStateAction<number>>
  navigate: (next: BuildUrlInput) => void
  toggleDrawer: () => void
  handleDrawerNavigate: (nextView: AdminView) => void
  selectWorkstream: (viewId: AdminView) => void
}

export function useAdminWorkspace(): AdminWorkspaceController {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const viewParam = searchParams.get("view")
  const sessionParam = searchParams.get("sessionId")
  const trackParam = searchParams.get("trackSlug")
  const view: AdminView = isAdminView(viewParam) ? viewParam : "sessions"

  const [refreshKey, setRefreshKey] = useState(0)
  const [health, setHealth] = useState<KBHealth | null>(null)
  const [healthError, setHealthError] = useState(false)
  const [healthLoading, setHealthLoading] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const toggleButtonRef = useRef<HTMLButtonElement>(null)

  function buildUrl(next: BuildUrlInput) {
    const params = new URLSearchParams(searchParams.toString())

    if (next.view !== undefined) {
      if (next.view) params.set("view", next.view)
      else params.delete("view")
    } else if (!params.get("view")) {
      params.set("view", "sessions")
    }

    if (next.sessionId !== undefined) {
      if (next.sessionId) params.set("sessionId", next.sessionId)
      else params.delete("sessionId")
    }

    if (next.trackSlug !== undefined) {
      if (next.trackSlug) params.set("trackSlug", next.trackSlug)
      else params.delete("trackSlug")
    }

    if (next.view && next.view !== "sessions" && next.view !== "traces") {
      params.delete("sessionId")
    }
    if (next.view && next.view !== "tracks" && next.view !== "careers") {
      params.delete("trackSlug")
    }

    if (params.size === 0) return pathname
    return `${pathname}?${params.toString()}`
  }

  function navigate(next: BuildUrlInput) {
    router.push(buildUrl(next), { scroll: false })
  }

  useEffect(() => {
    if (!isAdminView(viewParam)) {
      const fallback = viewParam === null ? "sessions" : view
      if (fallback !== viewParam) {
        router.replace(buildUrl({ view: fallback }), { scroll: false })
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewParam])

  useEffect(() => {
    if (view !== "knowledge") return
    let cancelled = false
    setHealthLoading(true)
    setHealthError(false)
    adminFetch("/api/kb/health")
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`)
        return r.json()
      })
      .then((data: KBHealth) => {
        if (!cancelled) setHealth(data)
      })
      .catch(() => {
        if (!cancelled) setHealthError(true)
      })
      .finally(() => {
        if (!cancelled) setHealthLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [view, refreshKey])

  const currentSurface = getViewDefinition(view)
  const activeWorkstream = getWorkstreamForView(view)
  const workstreamViews = getWorkstreamViews(activeWorkstream.id)
  const activeSurfaceId = view === "careers" ? "tracks" : view

  function toggleDrawer() {
    setDrawerOpen((value) => !value)
  }

  function handleDrawerNavigate(nextView: AdminView) {
    setDrawerOpen(false)
    navigate({
      view: nextView,
      sessionId: nextView === "traces" ? sessionParam : null,
      trackSlug: nextView === "tracks" || nextView === "careers" ? trackParam : null,
    })
  }

  function selectWorkstream(viewId: AdminView) {
    setDrawerOpen(false)
    navigate({ view: viewId, sessionId: null, trackSlug: null })
  }

  return {
    view,
    viewParam,
    sessionParam,
    trackParam,
    currentSurface,
    activeWorkstream,
    workstreamViews,
    activeSurfaceId,
    refreshKey,
    health,
    healthError,
    healthLoading,
    drawerOpen,
    toggleButtonRef,
    setRefreshKey,
    navigate,
    toggleDrawer,
    handleDrawerNavigate,
    selectWorkstream,
  }
}
