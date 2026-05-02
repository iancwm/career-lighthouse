"use client"
import { useEffect, useRef, useState } from "react"
import FactCard from "./forms/FactCard"
import FactEditor from "./forms/FactEditor"
import ExtractedFactsModal from "./modals/ExtractedFactsModal"
import { ActionStatus } from "@/components/admin/ui/ActionStatus"
import { Fact, getFactKeyValue, getFactTypeLabel, isActiveFact, normalizeFactLifecycle, sortFactsForDisplay } from "@/types/facts"

const API_URL = "/api/admin"

// ── Replace-flow types ─────────────────────────────────────────────────────

interface ReplacePFChange {
  old: string | null
  new: string
  source_type?: string | null
  source_label?: string | null
  source_timestamp?: string | null
}

interface ReplaceNewChunk {
  text: string
  source_type: string
  source_label: string
  source_timestamp?: string | null
  career_type: string | null
  chunk_id: string
}

interface ReplaceAnalysisResult {
  interpretation_bullets: string[]
  profile_updates: Record<string, Record<string, ReplacePFChange>>
  employer_updates: Record<string, Record<string, ReplacePFChange>>
  new_chunks: ReplaceNewChunk[]
  already_covered: { excerpt: string; source_doc: string }[]
}

interface ReplaceDiffState {
  result: ReplaceAnalysisResult
  employerEdits: Record<string, Record<string, string>>
  profileEdits: Record<string, Record<string, string>>
  chunkEdits: string[]
}

interface ReplaceTarget {
  factSlug: string
  factLabel: string
  factTypeLabel: string
}

interface ReplaceConfirmation {
  employerName: string
  factTypeLabel: string
  factLabel: string
  newValue: string
  updatedAt: string
}

type ReplaceFlowState = "idle" | "input" | "analysing" | "diff" | "publishing" | "error_analyse" | "error_publish" | "success"

interface EmployerDetail {
  slug: string
  employer_name: string
  tracks: string[]
  ep_requirement: string | null
  intake_seasons: string[]
  singapore_headcount_estimate: string | null
  application_process: string | null
  counsellor_contact: string | null
  notes: string | null
  structured?: Record<string, unknown>
  last_updated: string | null
  completeness: "green" | "amber"
}

interface CareerProfile {
  slug: string
  career_type: string
}

type SaveState = "idle" | "saving" | "success" | "error"
type ListState = "loading" | "loaded" | "error"
type Mode = "view" | "create"
type TabType = "details" | "facts"

// ── Helpers ────────────────────────────────────────────────────────────────

function slugify(name: string): string {
  return name.toLowerCase().replace(/\s+/g, "_").replace(/[^a-z0-9_]/g, "")
}

function completenessTooltip(emp: EmployerDetail): string {
  if (emp.completeness === "green") return "All key fields filled"
  const missing: string[] = []
  if (!emp.employer_name) missing.push("employer_name")
  if (!emp.tracks?.length) missing.push("tracks")
  if (!emp.ep_requirement) missing.push("ep_requirement")
  return missing.length > 0 ? `Missing: ${missing.join(", ")}` : "Incomplete"
}

function normalizeFacts(facts: Fact[]): Fact[] {
  return sortFactsForDisplay(
    facts.map((fact) => {
      const lifecycle = normalizeFactLifecycle(fact)
      const timestamp = fact.timestamp || fact.last_updated || fact.source_timestamp || new Date().toISOString()
      return {
        ...fact,
        lifecycle,
        deleted: lifecycle !== "active",
        source_timestamp: fact.source_timestamp || timestamp,
        last_updated: fact.last_updated || timestamp,
      }
    })
  )
}

function persistFacts(facts: Fact[]): Record<string, unknown> {
  return {
    facts: normalizeFacts(facts).map((fact) => ({
      ...fact,
      lifecycle: normalizeFactLifecycle(fact),
      deleted: normalizeFactLifecycle(fact) !== "active",
    })),
  }
}

// ── Sub-components ─────────────────────────────────────────────────────────

function CompletenessIndicator({ emp }: { emp: EmployerDetail }) {
  const [showTip, setShowTip] = useState(false)
  return (
    <div className="relative inline-block">
      <div
        className={`w-2.5 h-2.5 rounded-full flex-shrink-0 cursor-default ${emp.completeness === "green" ? "bg-green-400" : "bg-amber-400"}`}
        onMouseEnter={() => setShowTip(true)}
        onMouseLeave={() => setShowTip(false)}
        aria-label={completenessTooltip(emp)}
      />
      {showTip && (
        <div className="absolute left-4 top-0 z-10 whitespace-nowrap rounded bg-gray-800 px-2 py-1 text-xs text-white shadow">
          {completenessTooltip(emp)}
        </div>
      )}
    </div>
  )
}

function SkeletonRow() {
  return (
    <div className="flex items-center gap-2 px-3 py-2.5">
      <div className="w-2.5 h-2.5 rounded-full bg-gray-100 animate-pulse flex-shrink-0" />
      <div className="h-3.5 bg-gray-100 animate-pulse rounded flex-1" />
    </div>
  )
}

interface ChipInputProps {
  values: string[]
  onChange: (values: string[]) => void
  placeholder?: string
  disabled?: boolean
}

function ChipInput({ values, onChange, placeholder, disabled }: ChipInputProps) {
  const [inputVal, setInputVal] = useState("")

  function addChip(raw: string) {
    const tag = raw.trim()
    if (tag && !values.includes(tag)) {
      onChange([...values, tag])
    }
    setInputVal("")
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault()
      addChip(inputVal)
    } else if (e.key === "Backspace" && inputVal === "" && values.length > 0) {
      onChange(values.slice(0, -1))
    }
  }

  return (
    <div className="flex flex-wrap gap-1.5 rounded-lg border border-gray-300 px-2.5 py-2 focus-within:ring-2 focus-within:ring-blue-400 min-h-[40px] bg-white">
      {values.map((v) => (
        <span
          key={v}
          className="inline-flex items-center gap-1 rounded-full bg-blue-100 text-blue-700 text-xs px-2 py-0.5"
        >
          {v}
          {!disabled && (
            <button
              type="button"
              onClick={() => onChange(values.filter((x) => x !== v))}
              className="hover:text-blue-900 leading-none"
              aria-label={`Remove ${v}`}
            >
              ×
            </button>
          )}
        </span>
      ))}
      <input
        className="flex-1 min-w-[80px] text-sm outline-none bg-transparent placeholder-gray-400"
        value={inputVal}
        onChange={(e) => setInputVal(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={() => { if (inputVal.trim()) addChip(inputVal) }}
        placeholder={values.length === 0 ? placeholder : ""}
        disabled={disabled}
      />
    </div>
  )
}

interface PillToggleGroupProps {
  options: { value: string; label: string }[]
  selected: string[]
  onChange: (selected: string[]) => void
  disabled?: boolean
}

function PillToggleGroup({ options, selected, onChange, disabled }: PillToggleGroupProps) {
  function toggle(value: string) {
    if (selected.includes(value)) {
      onChange(selected.filter((v) => v !== value))
    } else {
      onChange([...selected, value])
    }
  }
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((opt) => {
        const active = selected.includes(opt.value)
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => !disabled && toggle(opt.value)}
            className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-blue-400 ${
              active
                ? "bg-blue-600 text-white"
                : "border border-gray-300 text-gray-600 hover:border-blue-400 hover:text-blue-600"
            } ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
            aria-pressed={active}
          >
            {opt.label}
          </button>
        )
      })}
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────

export default function EmployerFactsTab() {
  const [employers, setEmployers] = useState<EmployerDetail[]>([])
  const [listState, setListState] = useState<ListState>("loading")
  const [selected, setSelected] = useState<EmployerDetail | null>(null)
  const [form, setForm] = useState<Partial<EmployerDetail>>({})
  const [slugPreview, setSlugPreview] = useState("")
  const [slugManuallyEdited, setSlugManuallyEdited] = useState(false)
  const [mode, setMode] = useState<Mode>("view")
  const [saveState, setSaveState] = useState<SaveState>("idle")
  const [saveBanner, setSaveBanner] = useState("")
  const [profiles, setProfiles] = useState<CareerProfile[]>([])
  const [deleteConfirmSlug, setDeleteConfirmSlug] = useState<string | null>(null)
  const [unsavedConfirm, setUnsavedConfirm] = useState<EmployerDetail | null>(null)
  const [activeTab, setActiveTab] = useState<TabType>("details")
  const [facts, setFacts] = useState<Fact[]>([])
  const [showFactEditor, setShowFactEditor] = useState(false)
  const [showExtractModal, setShowExtractModal] = useState(false)
  const [extractedFacts, setExtractedFacts] = useState<Fact[]>([])
  const [extractLoading, setExtractLoading] = useState(false)
  const [extractError, setExtractError] = useState("")
  const [undoToast, setUndoToast] = useState<{ slug: string; label: string; remaining: number } | null>(null)
  const [replaceTarget, setReplaceTarget] = useState<ReplaceTarget | null>(null)
  const [replaceFlowState, setReplaceFlowState] = useState<ReplaceFlowState>("idle")
  const [replaceMode, setReplaceMode] = useState<"note" | "file">("note")
  const [replaceNote, setReplaceNote] = useState("")
  const [replaceFile, setReplaceFile] = useState<File | null>(null)
  const [replaceDiff, setReplaceDiff] = useState<ReplaceDiffState | null>(null)
  const [replaceConfirmation, setReplaceConfirmation] = useState<ReplaceConfirmation | null>(null)
  const replaceFileInputRef = useRef<HTMLInputElement | null>(null)
  const replaceConfirmTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const saveBannerTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const undoTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const undoTickRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const isDirty = useRef(false)
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false)
  const [pendingExtractedCount, setPendingExtractedCount] = useState(0)

  const trackOptions = profiles.map((p) => ({ value: p.slug, label: p.career_type }))

  useEffect(() => {
    fetchEmployers()
    fetchProfiles()
  }, [])

  useEffect(() => {
    if (!hasUnsavedChanges) return
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ""
    }
    window.addEventListener("beforeunload", handler)
    return () => window.removeEventListener("beforeunload", handler)
  }, [hasUnsavedChanges])

  useEffect(() => {
    return () => {
      if (saveBannerTimerRef.current) clearTimeout(saveBannerTimerRef.current)
      if (undoTimerRef.current) clearTimeout(undoTimerRef.current)
      if (undoTickRef.current) clearInterval(undoTickRef.current)
      if (replaceConfirmTimerRef.current) clearTimeout(replaceConfirmTimerRef.current)
    }
  }, [])

  function fetchEmployers() {
    setListState("loading")
    fetch(`${API_URL}/api/kb/employers`)
      .then((r) => { if (!r.ok) throw new Error(`${r.status}`); return r.json() })
      .then((data: EmployerDetail[]) => {
        setEmployers(data)
        setListState("loaded")
      })
      .catch(() => setListState("error"))
  }

  function fetchProfiles() {
    fetch(`${API_URL}/api/kb/career-profiles`)
      .then((r) => r.ok ? r.json() : [])
      .then((data: CareerProfile[]) => setProfiles(data))
      .catch(() => setProfiles([]))
  }

  function selectEmployer(emp: EmployerDetail) {
    if (saveState === "saving") {
      return
    }
    if (isDirty.current || hasUnsavedChanges) {
      setUnsavedConfirm(emp)
      return
    }
    commitSelection(emp)
  }

  function commitSelection(emp: EmployerDetail) {
    setSelected(emp)
    setForm({ ...emp })
    setMode("view")
    setSaveState("idle")
    setSaveBanner("")
    setActiveTab("details")
    isDirty.current = false
    setHasUnsavedChanges(false)
    setPendingExtractedCount(0)
    setUnsavedConfirm(null)
    setShowFactEditor(false)
    setUndoToast(null)
    // Load facts from structured data
    const structuredFacts = (emp.structured?.facts as Fact[]) || []
    setFacts(normalizeFacts(structuredFacts))
  }

  function startCreate() {
    if (isDirty.current) {
      setUnsavedConfirm(null)  // no target — handled by startCreate guard
    }
    setSelected(null)
    setForm({
      employer_name: "",
      tracks: [],
      ep_requirement: "",
      intake_seasons: [],
      singapore_headcount_estimate: "",
      application_process: "",
      counsellor_contact: "",
      notes: "",
    })
    setSlugPreview("")
    setSlugManuallyEdited(false)
    setMode("create")
    setSaveState("idle")
    setSaveBanner("")
    setActiveTab("details")
    isDirty.current = false
    setHasUnsavedChanges(false)
    setFacts([])
    setShowFactEditor(false)
    setUndoToast(null)
  }

  function handleAddFact(newFact: Fact) {
    setFacts((prev) => normalizeFacts([...prev, newFact]))
    setShowFactEditor(false)
    isDirty.current = true
    setHasUnsavedChanges(true)
  }

  function handleDeleteFact(slug: string) {
    const target = facts.find((fact) => fact.slug === slug)
    if (!target) return
    if (undoTimerRef.current) clearTimeout(undoTimerRef.current)
    if (undoTickRef.current) clearInterval(undoTickRef.current)
    setFacts((prev) =>
      prev.map((fact) =>
        fact.slug === slug
          ? { ...fact, lifecycle: "superseded", deleted: true, last_updated: new Date().toISOString() }
          : fact
      )
    )
    setUndoToast({ slug, label: getFactKeyValue(target), remaining: 5 })
    undoTickRef.current = setInterval(() => {
      setUndoToast((current) => {
        if (!current || current.slug !== slug) return current
        const remaining = current.remaining - 1
        if (remaining <= 0) return { ...current, remaining: 0 }
        return { ...current, remaining }
      })
    }, 1000)
    undoTimerRef.current = setTimeout(() => {
      if (undoTickRef.current) clearInterval(undoTickRef.current)
      undoTickRef.current = null
      undoTimerRef.current = null
      setUndoToast(null)
    }, 5000)
    isDirty.current = true
    setHasUnsavedChanges(true)
  }

  function handleUndoDelete() {
    if (!undoToast) return
    if (undoTimerRef.current) clearTimeout(undoTimerRef.current)
    if (undoTickRef.current) clearInterval(undoTickRef.current)
    undoTimerRef.current = null
    undoTickRef.current = null
    setFacts((prev) =>
      prev.map((fact) =>
        fact.slug === undoToast.slug
          ? { ...fact, lifecycle: "active", deleted: false, last_updated: new Date().toISOString() }
          : fact
      )
    )
    setUndoToast(null)
    isDirty.current = true
    setHasUnsavedChanges(true)
  }

  async function handleExtractFacts() {
    if (!selected) return
    if (!form.notes?.trim()) {
      setExtractError("Add counsellor notes first to extract facts.")
      return
    }

    setExtractLoading(true)
    setExtractError("")
    setExtractedFacts([])

    try {
      const r = await fetch(`${API_URL}/api/kb/employers/${selected.slug}/extract-facts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      })

      if (!r.ok) {
        const err = await r.json().catch(() => ({}))
        throw new Error(err.detail || "Extraction failed")
      }

      const data = await r.json()
      setExtractedFacts(data.facts || [])
      setShowExtractModal(true)
    } catch (err) {
      setExtractError(err instanceof Error ? err.message : "Extraction failed")
    } finally {
      setExtractLoading(false)
    }
  }

  function handleAddExtractedFacts(factsToAdd: Fact[]) {
    setFacts((prev) => [...prev, ...factsToAdd])
    setShowExtractModal(false)
    setExtractedFacts([])
    isDirty.current = true
    setHasUnsavedChanges(true)
    setPendingExtractedCount((prev) => prev + factsToAdd.length)
  }

  function handleDiscardChanges() {
    if (!selected) return
    const structuredFacts = (selected.structured?.facts as Fact[]) || []
    setFacts(normalizeFacts(structuredFacts))
    setForm({ ...selected })
    isDirty.current = false
    setHasUnsavedChanges(false)
    setPendingExtractedCount(0)
  }

  function updateField(field: keyof EmployerDetail, value: unknown) {
    setForm((prev) => ({ ...prev, [field]: value }))
    isDirty.current = true
    setHasUnsavedChanges(true)
    if (field === "employer_name" && !slugManuallyEdited && mode === "create") {
      setSlugPreview(slugify(value as string))
    }
  }

  async function handleSave() {
    if (mode === "create") {
      return await handleCreate()
    }
    return await handleUpdate()
  }

  async function handleCreate() {
    if (!form.employer_name?.trim()) return false
    const slug = slugPreview || slugify(form.employer_name)
    if (!slug) return false

    setSaveState("saving")
    try {
      const body: EmployerDetail = {
        slug,
        employer_name: form.employer_name!.trim(),
        tracks: form.tracks || [],
        ep_requirement: form.ep_requirement || null,
        intake_seasons: form.intake_seasons || [],
        singapore_headcount_estimate: form.singapore_headcount_estimate || null,
        application_process: form.application_process || null,
        counsellor_contact: form.counsellor_contact || null,
        notes: form.notes || null,
        structured: facts.length > 0 ? persistFacts(facts) : {},
        last_updated: null,
        completeness: "amber",
      }
      const r = await fetch(`${API_URL}/api/kb/employers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
      if (!r.ok) {
        const err = await r.json().catch(() => ({}))
        setSaveState("error")
        setSaveBanner(r.status === 409 ? `Employer '${slug}' already exists.` : (err.detail || "Save failed."))
        return false
      }
      const created: EmployerDetail = await r.json()
      const updated = [...employers, created]
      setEmployers(updated)
      setSelected(created)
      setForm({ ...created })
      setMode("view")
      setSaveState("success")
      showSuccessBanner("Employer created.")
      isDirty.current = false
      setHasUnsavedChanges(false)
      setPendingExtractedCount(0)
      return true
    } catch {
      setSaveState("error")
      setSaveBanner("Save failed — network error.")
      return false
    }
  }

  async function handleUpdate() {
    if (!selected) return false
    setSaveState("saving")
    try {
      const body: EmployerDetail = {
        ...selected,
        ...form,
        slug: selected.slug,
        completeness: "amber",
        structured: facts.length > 0 ? persistFacts(facts) : {},
      }
      const r = await fetch(`${API_URL}/api/kb/employers/${selected.slug}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
      if (!r.ok) {
        const err = await r.json().catch(() => ({}))
        setSaveState("error")
        setSaveBanner(err.detail || "Save failed.")
        return false
      }
      const updated: EmployerDetail = await r.json()
      setEmployers((prev) => prev.map((e) => (e.slug === updated.slug ? updated : e)))
      setSelected(updated)
      setForm({ ...updated })
      setSaveState("success")
      showSuccessBanner("Saved.")
      isDirty.current = false
      setHasUnsavedChanges(false)
      setPendingExtractedCount(0)
      return true
    } catch {
      setSaveState("error")
      setSaveBanner("Save failed — network error.")
      return false
    }
  }

  async function handleDelete(slug: string) {
    try {
      const r = await fetch(`${API_URL}/api/kb/employers/${slug}`, { method: "DELETE" })
      if (!r.ok && r.status !== 204) {
        setDeleteConfirmSlug(null)
        return
      }
      setEmployers((prev) => prev.filter((e) => e.slug !== slug))
      if (selected?.slug === slug) {
        setSelected(null)
        setForm({})
        setMode("view")
      }
      setDeleteConfirmSlug(null)
    } catch {
      setDeleteConfirmSlug(null)
    }
  }

  function showSuccessBanner(msg: string) {
    if (saveBannerTimerRef.current) clearTimeout(saveBannerTimerRef.current)
    setSaveBanner(msg)
    saveBannerTimerRef.current = setTimeout(() => {
      setSaveBanner("")
      setSaveState("idle")
    }, 3000)
  }

  // ── Replace flow ──────────────────────────────────────────────────────────

  function handleStartReplace(factSlug: string) {
    const fact = facts.find((f) => f.slug === factSlug)
    if (!fact) return
    setReplaceTarget({
      factSlug: fact.slug,
      factLabel: getFactKeyValue(fact),
      factTypeLabel: getFactTypeLabel(fact.type),
    })
    setReplaceFlowState("input")
    setReplaceMode("note")
    setReplaceNote("")
    setReplaceFile(null)
    setReplaceDiff(null)
    setReplaceConfirmation(null)
    if (replaceConfirmTimerRef.current) clearTimeout(replaceConfirmTimerRef.current)
  }

  function handleCancelReplace() {
    if (replaceConfirmTimerRef.current) clearTimeout(replaceConfirmTimerRef.current)
    setReplaceTarget(null)
    setReplaceFlowState("idle")
    setReplaceNote("")
    setReplaceFile(null)
    setReplaceDiff(null)
    setReplaceConfirmation(null)
  }

  async function handleReplaceAnalyse() {
    if (!replaceTarget || !selected) return
    setReplaceFlowState("analysing")
    const formData = new FormData()
    if (replaceMode === "note") {
      formData.append("text", replaceNote.trim())
      formData.append("source_type", "note")
    } else if (replaceFile) {
      formData.append("file", replaceFile)
      formData.append("source_type", "file")
    }
    try {
      const res = await fetch(`${API_URL}/api/kb/analyse`, { method: "POST", body: formData })
      if (!res.ok) { setReplaceFlowState("error_analyse"); return }
      const result: ReplaceAnalysisResult = await res.json()
      const employerEdits: Record<string, Record<string, string>> = {}
      for (const [slug, fields] of Object.entries(result.employer_updates ?? {})) {
        employerEdits[slug] = {}
        for (const [field, change] of Object.entries(fields)) {
          employerEdits[slug][field] = change.new
        }
      }
      const profileEdits: Record<string, Record<string, string>> = {}
      for (const [slug, fields] of Object.entries(result.profile_updates ?? {})) {
        profileEdits[slug] = {}
        for (const [field, change] of Object.entries(fields)) {
          profileEdits[slug][field] = change.new
        }
      }
      setReplaceDiff({ result, employerEdits, profileEdits, chunkEdits: result.new_chunks.map((c) => c.text) })
      setReplaceFlowState("diff")
    } catch {
      setReplaceFlowState("error_analyse")
    }
  }

  async function handleReplacePublish() {
    if (!replaceDiff || !selected || !replaceTarget) return
    setReplaceFlowState("publishing")

    const employerUpdates: Record<string, Record<string, ReplacePFChange>> = {}
    for (const [slug, fields] of Object.entries(replaceDiff.result.employer_updates ?? {})) {
      employerUpdates[slug] = {}
      for (const [field, change] of Object.entries(fields)) {
        employerUpdates[slug][field] = {
          old: change.old,
          new: replaceDiff.employerEdits[slug]?.[field] ?? change.new,
          source_type: change.source_type ?? null,
          source_label: change.source_label ?? null,
          source_timestamp: change.source_timestamp ?? null,
        }
      }
    }
    const profileUpdates: Record<string, Record<string, ReplacePFChange>> = {}
    for (const [slug, fields] of Object.entries(replaceDiff.result.profile_updates ?? {})) {
      profileUpdates[slug] = {}
      for (const [field, change] of Object.entries(fields)) {
        profileUpdates[slug][field] = {
          old: change.old,
          new: replaceDiff.profileEdits[slug]?.[field] ?? change.new,
          source_type: change.source_type ?? null,
          source_label: change.source_label ?? null,
          source_timestamp: change.source_timestamp ?? null,
        }
      }
    }
    const newChunks = replaceDiff.result.new_chunks.map((chunk, i) => ({
      ...chunk,
      text: replaceDiff.chunkEdits[i] ?? chunk.text,
    }))

    try {
      const commitRes = await fetch(`${API_URL}/api/kb/commit-analysis`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile_updates: profileUpdates, employer_updates: employerUpdates, new_chunks: newChunks }),
      })
      if (!commitRes.ok) { setReplaceFlowState("error_publish"); return }

      // Mark the replaced fact as superseded and save employer
      const now = new Date().toISOString()
      const newFacts = normalizeFacts(
        facts.map((f) =>
          f.slug === replaceTarget.factSlug
            ? { ...f, lifecycle: "superseded" as const, deleted: true, last_updated: now }
            : f
        )
      )
      setFacts(newFacts)
      isDirty.current = false
      setHasUnsavedChanges(false)

      const updatedBody = {
        ...selected,
        ...form,
        slug: selected.slug,
        completeness: "amber" as const,
        structured: persistFacts(newFacts),
      }
      fetch(`${API_URL}/api/kb/employers/${selected.slug}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updatedBody),
      }).then(async (r) => {
        if (r.ok) {
          const updated: EmployerDetail = await r.json()
          setEmployers((prev) => prev.map((e) => (e.slug === updated.slug ? updated : e)))
          setSelected(updated)
          setForm({ ...updated })
        }
      }).catch(() => { /* commit succeeded; employer update is best-effort */ })

      // Derive confirmation content from the diff
      const changesForThisEmployer = employerUpdates[selected.slug]
      const firstChange = changesForThisEmployer ? Object.values(changesForThisEmployer)[0] : null

      setReplaceConfirmation({
        employerName: selected.employer_name,
        factTypeLabel: replaceTarget.factTypeLabel,
        factLabel: replaceTarget.factLabel,
        newValue: firstChange?.new ?? "",
        updatedAt: new Date().toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }),
      })
      setReplaceDiff(null)
      setReplaceFlowState("success")

      replaceConfirmTimerRef.current = setTimeout(() => {
        handleCancelReplace()
      }, 6000)
    } catch {
      setReplaceFlowState("error_publish")
    }
  }

  function formatReplaceSourceLabel(value?: string | null) {
    if (!value || !value.trim()) return "Unknown"
    const clean = value.trim().replace(/_/g, " ")
    return clean.replace(/\b\w/g, (c) => c.toUpperCase())
  }

  function formatReplaceSourceDate(value?: string | null) {
    if (!value || !value.trim()) return "Unknown"
    const parsed = new Date(value)
    if (Number.isNaN(parsed.getTime())) return value
    return parsed.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })
  }

  const canSave = mode === "create"
    ? Boolean(form.employer_name?.trim() && (slugPreview || slugify(form.employer_name || "")))
    : Boolean(selected)
  const navigationLocked = hasUnsavedChanges || saveState === "saving"
  const navigationLockedMessage = saveState === "saving"
    ? "Saving changes. Employer switching is disabled until the save completes."
    : hasUnsavedChanges
      ? "You have unsaved changes. Save or discard them before switching employers."
      : ""
  const saveButtonLabel = mode === "create"
    ? "Create employer record"
    : pendingExtractedCount > 0
      ? `Save ${pendingExtractedCount} extracted fact${pendingExtractedCount === 1 ? "" : "s"}`
      : "Save employer updates"
  const historyHref = selected ? `${API_URL}/api/kb/employers/${selected.slug}/history` : null
  const supersededByBySlug = new Map<string, string>()
  for (const fact of facts) {
    if (normalizeFactLifecycle(fact) !== "superseded") continue
    const matching = facts.find(
      (candidate) =>
        candidate.slug !== fact.slug &&
        normalizeFactLifecycle(candidate) === "active" &&
        candidate.type === fact.type &&
        getFactKeyValue(candidate) === getFactKeyValue(fact)
    )
    if (matching) supersededByBySlug.set(fact.slug, matching.slug)
  }

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div>
      <h2 className="text-lg font-semibold mb-1">Employer Fact Library</h2>
      <p className="text-sm text-gray-500 mb-4 max-w-3xl">
        Keep employer-specific information current here. These facts are used to answer direct student questions about hiring requirements, timelines, and application process.
      </p>

      <div className="flex gap-0 rounded-xl border border-gray-200 overflow-hidden min-h-[560px]">
        {/* ── Left panel (35%) ─────────────────────────────────── */}
        <div className="w-[35%] border-r border-gray-200 flex flex-col">
          {listState === "loading" && (
            <div className="flex-1 py-1">
              <SkeletonRow />
              <SkeletonRow />
              <SkeletonRow />
            </div>
          )}

          {listState === "error" && (
            <div className="flex-1 flex items-center justify-center p-4">
              <p className="text-sm text-red-600 text-center">
                Failed to load employers.{" "}
                <button onClick={fetchEmployers} className="underline">Retry</button>
              </p>
            </div>
          )}

          {listState === "loaded" && employers.length === 0 && (
            <div className="flex-1 flex flex-col items-center justify-center gap-3 p-6 text-center">
              <p className="text-sm text-gray-500">No employers yet</p>
              <p className="text-xs text-gray-400">
                Add an employer record so counsellors can maintain one current source of truth for student-facing answers.
              </p>
              <button
                onClick={startCreate}
                className="px-3 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-medium hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-400"
              >
                + Add employer
              </button>
            </div>
          )}

          {listState === "loaded" && employers.length > 0 && (
            <>
              {navigationLocked && (
                <div className="px-3 py-2 bg-amber-50 border-b border-amber-200 text-xs text-amber-700 flex items-center gap-1.5">
                  <span className="shrink-0">⚠</span>
                  <span>Unsaved changes — save or discard before switching.</span>
                </div>
              )}
              <div className="flex-1 overflow-y-auto">
                {employers.map((emp) => {
                  const isSelected = selected?.slug === emp.slug && mode !== "create"
                  if (deleteConfirmSlug === emp.slug) {
                    return (
                      <div key={emp.slug} className="px-3 py-2 bg-red-50 border-b border-red-100 text-xs">
                        <p className="text-red-700 mb-1.5">
                          Remove <span className="font-medium">{emp.employer_name}</span> from AI context?
                        </p>
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleDelete(emp.slug)}
                            className="px-2 py-1 bg-red-600 text-white rounded text-xs hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-400"
                          >
                            Remove
                          </button>
                          <button
                            onClick={() => setDeleteConfirmSlug(null)}
                            className="px-2 py-1 border border-gray-300 text-gray-600 rounded text-xs hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-400"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    )
                  }
                  return (
                    <div
                      key={emp.slug}
                      onClick={() => selectEmployer(emp)}
                      aria-disabled={navigationLocked && selected?.slug !== emp.slug}
                      className={`flex items-center gap-2 px-3 py-2.5 cursor-pointer transition-colors border-b border-gray-100 group ${
                          isSelected
                            ? "bg-blue-50 border-l-2 border-l-blue-400"
                            : navigationLocked && selected?.slug !== emp.slug
                            ? "bg-gray-50 opacity-50 cursor-not-allowed"
                            : "hover:bg-gray-50"
                      }`}
                    >
                      <CompletenessIndicator emp={emp} />
                      <span className="flex-1 text-sm text-gray-800 truncate">{emp.employer_name}</span>
                      <button
                        onClick={(e) => { e.stopPropagation(); setDeleteConfirmSlug(emp.slug) }}
                        className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 text-xs transition-opacity focus:outline-none focus:ring-2 focus:ring-red-400 rounded"
                        aria-label={`Delete ${emp.employer_name}`}
                      >
                        ✕
                      </button>
                    </div>
                  )
                })}
              </div>

              <div className="border-t border-gray-100 p-3">
                <button
                  onClick={startCreate}
                  disabled={navigationLocked}
                  className="w-full py-2 rounded-lg text-xs text-blue-600 font-medium border border-blue-200 hover:bg-blue-50 focus:outline-none focus:ring-2 focus:ring-blue-400"
                >
                  + Add employer
                </button>
              </div>
            </>
          )}
        </div>

        {/* ── Right panel (65%) ─────────────────────────────────── */}
        <div className="flex-1 flex flex-col">
          {/* Unsaved changes warning */}
          {(unsavedConfirm || navigationLockedMessage) && (
            <div className="flex items-center gap-3 px-4 py-2.5 bg-amber-50 border-b border-amber-200 text-xs text-amber-800">
              <span>
                {unsavedConfirm ? (
                  <>
                    Unsaved changes to <span className="font-medium">{selected?.employer_name || "this employer"}</span>.{" "}
                    Save or discard before opening <span className="font-medium">{unsavedConfirm.employer_name}</span>.
                  </>
                ) : (
                  navigationLockedMessage
                )}
              </span>
              {unsavedConfirm && (
                <>
                  <button
                    onClick={() => { handleSave().then((saved) => { if (saved && unsavedConfirm) commitSelection(unsavedConfirm) }) }}
                    className="px-2 py-1 bg-amber-600 text-white rounded hover:bg-amber-700 focus:outline-none focus:ring-2 focus:ring-amber-400"
                  >
                    Save
                  </button>
                  <button
                    onClick={() => { isDirty.current = false; setHasUnsavedChanges(false); commitSelection(unsavedConfirm) }}
                    className="px-2 py-1 border border-amber-300 text-amber-700 rounded hover:bg-amber-100 focus:outline-none focus:ring-2 focus:ring-amber-400"
                  >
                    Discard
                  </button>
                </>
              )}
            </div>
          )}

          {navigationLocked && !unsavedConfirm && (
            <div className="px-4 pb-2 text-xs text-amber-700">
              Switch employers is blocked until the current edit is saved or discarded.
            </div>
          )}

          {/* Save banner (success / error) */}
          {saveState === "success" && saveBanner && (
            <div className="px-4 py-2.5 bg-green-50 border-b border-green-200 text-xs text-green-700">
              {saveBanner}
            </div>
          )}
          {saveState === "error" && saveBanner && (
            <div className="flex items-center gap-3 px-4 py-2.5 bg-red-50 border-b border-red-200 text-xs text-red-700">
              <span>{saveBanner}</span>
              <button
                onClick={handleSave}
                className="px-2 py-1 bg-red-600 text-white rounded hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-400"
              >
                Retry
              </button>
            </div>
          )}

          {/* No selection placeholder */}
          {!selected && mode !== "create" && (
            <div className="flex-1 flex items-center justify-center rounded-r-xl border-2 border-dashed border-gray-200 m-4">
              <p className="text-sm text-gray-400">Select an employer to edit, or add a new one</p>
            </div>
          )}

          {/* Form (view / create) */}
          {(selected || mode === "create") && (
            <div className="flex-1 flex flex-col overflow-hidden">
              {/* Tab selector */}
              <div className="flex border-b border-gray-200 px-4 pt-3">
                <button
                  onClick={() => setActiveTab("details")}
                  className={`px-4 py-2.5 text-sm font-medium transition-colors border-b-2 ${
                    activeTab === "details"
                      ? "border-blue-600 text-blue-600"
                      : "border-transparent text-gray-600 hover:text-gray-700"
                  }`}
                >
                  Details
                </button>
                <button
                  onClick={() => setActiveTab("facts")}
                  className={`px-4 py-2.5 text-sm font-medium transition-colors border-b-2 ${
                    activeTab === "facts"
                      ? "border-blue-600 text-blue-600"
                      : "border-transparent text-gray-600 hover:text-gray-700"
                  }`}
                >
                  Facts {facts.length > 0 && <span className="inline-block ml-1 px-1.5 py-0 rounded-full bg-blue-100 text-blue-700 text-xs">{facts.length}</span>}
                </button>
              </div>

              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                <h3 className="text-sm font-semibold text-gray-700">
                  {mode === "create" ? "New employer record" : selected?.employer_name}
                </h3>

                {/* Details Tab */}
                {activeTab === "details" && (
                <div className="space-y-4">

                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">Employer name</label>
                  <input
                    type="text"
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                    placeholder="e.g. Goldman Sachs"
                    value={(form.employer_name ?? "") as string}
                    onChange={(e) => updateField("employer_name", e.target.value)}
                  />
                </div>

                {mode === "create" && (
                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">
                      Record ID <span className="text-gray-400 font-normal">(auto-generated, editable)</span>
                    </label>
                    <input
                      type="text"
                      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-400"
                      placeholder="Example: goldman_sachs"
                      value={slugPreview}
                      onChange={(e) => {
                        setSlugPreview(e.target.value)
                        setSlugManuallyEdited(true)
                      }}
                    />
                  </div>
                )}

                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1.5">Relevant career tracks</label>
                  <PillToggleGroup
                    options={trackOptions.length > 0 ? trackOptions : [
                      { value: "investment_banking", label: "Investment Banking" },
                      { value: "consulting", label: "Consulting" },
                      { value: "tech_product", label: "Tech & Product" },
                    ]}
                    selected={(form.tracks ?? []) as string[]}
                    onChange={(v) => updateField("tracks", v)}
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">Work pass / EP requirement</label>
                  <input
                    type="text"
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                    placeholder="Example: EP4 typically required as of Q1 2026"
                    value={(form.ep_requirement ?? "") as string}
                    onChange={(e) => updateField("ep_requirement", e.target.value || null)}
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">
                    Intake timing <span className="text-gray-400 font-normal">— press Enter or comma to add each window</span>
                  </label>
                  <ChipInput
                    values={(form.intake_seasons ?? []) as string[]}
                    onChange={(v) => updateField("intake_seasons", v)}
                    placeholder="Example: July"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">Singapore hiring estimate</label>
                  <input
                    type="text"
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                    placeholder="e.g. 15-20 per year"
                    value={(form.singapore_headcount_estimate ?? "") as string}
                    onChange={(e) => updateField("singapore_headcount_estimate", e.target.value || null)}
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">Application process</label>
                  <textarea
                    rows={3}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-400"
                    placeholder="Example: Online application, HireVue, assessment centre, final interviews"
                    value={(form.application_process ?? "") as string}
                    onChange={(e) => updateField("application_process", e.target.value || null)}
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">Internal counsellor contact</label>
                  <input
                    type="text"
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                    placeholder="e.g. Jane Tan, SMU Career Centre"
                    value={(form.counsellor_contact ?? "") as string}
                    onChange={(e) => updateField("counsellor_contact", e.target.value || null)}
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">Counsellor notes</label>
                  <textarea
                    rows={4}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-400"
                    placeholder="Add context for counsellors, for example when the requirement changed or any known exceptions"
                    value={(form.notes ?? "") as string}
                    onChange={(e) => updateField("notes", e.target.value || null)}
                  />
                </div>

                {selected?.last_updated && mode !== "create" && (
                  <p className="text-xs text-gray-400">Last updated: {selected.last_updated}</p>
                )}
                </div>
                )}

                {/* Facts Tab */}
                {activeTab === "facts" && (
                <div className="space-y-4">
                  {/* Facts list */}
                  {facts.length === 0 && !showFactEditor && replaceFlowState === "idle" && (
                    <div className="rounded-2xl border border-[#D8D0C4] bg-[#FFFDFC] px-5 py-6 text-left">
                      <p className="text-sm text-[#1F2937]">
                        No facts yet for {selected?.employer_name || "this employer"}.
                      </p>
                      <p className="mt-2 text-sm text-[#5F6B76]">
                        Facts you add here stay visible for audit and help counsellors answer student questions with current employer guidance.
                      </p>
                      <button
                        onClick={() => setShowFactEditor(true)}
                        className="mt-4 rounded-full bg-[#0F766E] px-4 py-2.5 text-sm font-medium text-white hover:bg-[#115e59] focus:outline-none focus:ring-2 focus:ring-[#0F766E]"
                      >
                        + Add first fact
                      </button>
                    </div>
                  )}

                  {facts.length > 0 && (
                    <div className="space-y-2.5">
                      <p className="text-xs font-medium text-gray-600 mb-3">
                        Captured facts ({facts.length}) - active and superseded records stay visible
                      </p>
                      {facts.map((fact) => (
                        <FactCard
                          key={fact.slug}
                          fact={fact}
                          supersededBy={supersededByBySlug.get(fact.slug)}
                          historyHref={historyHref}
                          onDelete={handleDeleteFact}
                          onReplace={replaceFlowState === "idle" && isActiveFact(fact) ? handleStartReplace : undefined}
                        />
                      ))}
                    </div>
                  )}

                  {/* Replace fact workflow panel */}
                  {replaceFlowState !== "idle" && replaceTarget && (
                    <div className="rounded-2xl border border-[#D8D0C4] bg-[#FFFDFC] p-4">
                      <div className="flex items-start justify-between mb-3">
                        <div>
                          <h4 className="text-sm font-semibold text-[#1F2937]">Replace current content</h4>
                          <p className="text-xs text-[#5F6B76] mt-0.5">
                            {replaceTarget.factTypeLabel}: <span className="font-medium text-[#1F2937]">{replaceTarget.factLabel}</span>
                          </p>
                        </div>
                        <button
                          onClick={handleCancelReplace}
                          className="p-1 text-[#5F6B76] hover:text-[#1F2937] focus:outline-none focus:ring-2 focus:ring-[#0F766E] rounded"
                          aria-label="Cancel replace"
                        >
                          ✕
                        </button>
                      </div>

                      {/* Input phase */}
                      {replaceFlowState === "input" && (
                        <div className="space-y-3">
                          <div className="flex rounded-lg border border-gray-200 overflow-hidden text-sm">
                            <button
                              onClick={() => { setReplaceMode("note"); setReplaceFile(null) }}
                              className={`flex-1 py-2 font-medium transition-colors focus:outline-none ${replaceMode === "note" ? "bg-[#0F766E] text-white" : "bg-white text-gray-600 hover:bg-gray-50"}`}
                            >
                              Counsellor note
                            </button>
                            <button
                              onClick={() => setReplaceMode("file")}
                              className={`flex-1 py-2 font-medium transition-colors focus:outline-none ${replaceMode === "file" ? "bg-[#0F766E] text-white" : "bg-white text-gray-600 hover:bg-gray-50"}`}
                            >
                              Uploaded file
                            </button>
                          </div>

                          {replaceMode === "note" ? (
                            <textarea
                              value={replaceNote}
                              onChange={(e) => setReplaceNote(e.target.value)}
                              placeholder="Describe the updated content, for example: Goldman changed their EP threshold to 50+ COMPASS from Q2 2026."
                              className="w-full border border-gray-300 rounded-lg p-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-[#0F766E] min-h-[100px]"
                            />
                          ) : (
                            <div
                              className="border-2 border-dashed border-gray-300 rounded-lg p-5 text-center cursor-pointer hover:border-[#0F766E] transition-colors"
                              onClick={() => replaceFileInputRef.current?.click()}
                              onDragOver={(e) => e.preventDefault()}
                              onDrop={(e) => {
                                e.preventDefault()
                                const f = e.dataTransfer.files[0]
                                if (f) setReplaceFile(f)
                              }}
                            >
                              {replaceFile ? (
                                <p className="text-sm text-gray-700 font-medium">{replaceFile.name}</p>
                              ) : (
                                <>
                                  <p className="text-gray-500 text-sm">Drag and drop or click to choose a file</p>
                                  <p className="text-xs text-gray-400 mt-1">Accepted formats: PDF, DOCX, TXT</p>
                                </>
                              )}
                              <input
                                ref={replaceFileInputRef}
                                type="file"
                                accept=".pdf,.docx,.txt"
                                className="hidden"
                                onChange={(e) => { const f = e.target.files?.[0]; if (f) setReplaceFile(f) }}
                              />
                            </div>
                          )}

                          <button
                            onClick={handleReplaceAnalyse}
                            disabled={replaceMode === "note" ? !replaceNote.trim() : !replaceFile}
                            className="min-h-[44px] w-full py-2.5 bg-[#0F766E] text-white text-sm font-medium rounded-xl hover:bg-[#0A5C57] disabled:opacity-40 focus:outline-none focus:ring-2 focus:ring-[#0F766E]"
                          >
                            Review proposed changes
                          </button>
                        </div>
                      )}

                      {/* Analysing / publishing spinner */}
                      {(replaceFlowState === "analysing" || replaceFlowState === "publishing") && (
                        <div className="flex items-center justify-center py-8">
                          <ActionStatus
                            size="md"
                            label={replaceFlowState === "publishing" ? "Publishing update…" : "Preparing review…"}
                          />
                        </div>
                      )}

                      {/* Error: analysis failed */}
                      {replaceFlowState === "error_analyse" && (
                        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                          <p>Could not prepare the review. Please try again or make the note more specific.</p>
                          <button
                            onClick={handleReplaceAnalyse}
                            className="mt-2 min-h-[44px] px-3 py-2 bg-red-600 text-white rounded-lg text-xs hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-400"
                          >
                            Retry
                          </button>
                        </div>
                      )}

                      {/* Error: publish failed */}
                      {replaceFlowState === "error_publish" && replaceDiff && (
                        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 mb-3">
                          <p>Could not save this update yet. Please retry.</p>
                          <button
                            onClick={handleReplacePublish}
                            className="mt-2 min-h-[44px] px-3 py-2 bg-red-600 text-white rounded-lg text-xs hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-400"
                          >
                            Retry
                          </button>
                        </div>
                      )}

                      {/* Diff review */}
                      {(replaceFlowState === "diff" || replaceFlowState === "error_publish") && replaceDiff && (
                        <div className="space-y-3">
                          {replaceDiff.result.interpretation_bullets.length > 0 && (
                            <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                              <p className="text-xs font-medium text-gray-500 mb-2">Summary of what will change:</p>
                              <ul className="space-y-1">
                                {replaceDiff.result.interpretation_bullets.map((b, i) => (
                                  <li key={i} className="text-xs text-gray-700 flex gap-2">
                                    <span className="text-[#0F766E] mt-0.5 shrink-0">•</span>
                                    <span>{b}</span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {/* Employer fact updates */}
                          {Object.keys(replaceDiff.result.employer_updates ?? {}).length > 0 && (
                            <section>
                              <h5 className="text-xs font-semibold text-gray-600 mb-2">Employer updates</h5>
                              <div className="space-y-2">
                                {Object.entries(replaceDiff.result.employer_updates).map(([slug, fields]) =>
                                  Object.entries(fields).map(([field, change]) => (
                                    <div key={`${slug}-${field}`} className="rounded-lg border border-gray-200 p-3 text-xs">
                                      <p className="font-medium text-gray-600 mb-1">{slug} / {field}</p>
                                      {change.old && (
                                        <p className="text-gray-400 line-through mb-1 leading-relaxed">{change.old}</p>
                                      )}
                                      <textarea
                                        className="w-full border border-[#D8D0C4] bg-[#F0E7DB] rounded p-2 text-gray-800 resize-none focus:outline-none focus:ring-2 focus:ring-[#0F766E] leading-relaxed"
                                        rows={2}
                                        value={replaceDiff.employerEdits[slug]?.[field] ?? change.new}
                                        onChange={(e) => {
                                          const val = e.target.value
                                          setReplaceDiff((prev) => {
                                            if (!prev) return prev
                                            return {
                                              ...prev,
                                              employerEdits: {
                                                ...prev.employerEdits,
                                                [slug]: { ...prev.employerEdits[slug], [field]: val },
                                              },
                                            }
                                          })
                                        }}
                                      />
                                      <div className="mt-1.5 text-[11px] leading-5 text-[#5F6B76]">
                                        Source: {formatReplaceSourceLabel(change.source_label)} · {formatReplaceSourceDate(change.source_timestamp)}
                                      </div>
                                    </div>
                                  ))
                                )}
                              </div>
                            </section>
                          )}

                          {/* Profile updates */}
                          {Object.keys(replaceDiff.result.profile_updates ?? {}).length > 0 && (
                            <section>
                              <h5 className="text-xs font-semibold text-gray-600 mb-2">Career profile updates</h5>
                              <div className="space-y-2">
                                {Object.entries(replaceDiff.result.profile_updates).map(([slug, fields]) =>
                                  Object.entries(fields).map(([field, change]) => (
                                    <div key={`${slug}-${field}`} className="rounded-lg border border-gray-200 p-3 text-xs">
                                      <p className="font-medium text-gray-600 mb-1">{slug} / {field}</p>
                                      {change.old && (
                                        <p className="text-gray-400 line-through mb-1 leading-relaxed">{change.old}</p>
                                      )}
                                      <textarea
                                        className="w-full border border-[#D8D0C4] bg-[#F0E7DB] rounded p-2 text-gray-800 resize-none focus:outline-none focus:ring-2 focus:ring-[#0F766E] leading-relaxed"
                                        rows={2}
                                        value={replaceDiff.profileEdits[slug]?.[field] ?? change.new}
                                        onChange={(e) => {
                                          const val = e.target.value
                                          setReplaceDiff((prev) => {
                                            if (!prev) return prev
                                            return {
                                              ...prev,
                                              profileEdits: {
                                                ...prev.profileEdits,
                                                [slug]: { ...prev.profileEdits[slug], [field]: val },
                                              },
                                            }
                                          })
                                        }}
                                      />
                                      <div className="mt-1.5 text-[11px] leading-5 text-[#5F6B76]">
                                        Source: {formatReplaceSourceLabel(change.source_label)} · {formatReplaceSourceDate(change.source_timestamp)}
                                      </div>
                                    </div>
                                  ))
                                )}
                              </div>
                            </section>
                          )}

                          {Object.keys(replaceDiff.result.employer_updates ?? {}).length === 0 &&
                            Object.keys(replaceDiff.result.profile_updates ?? {}).length === 0 &&
                            replaceDiff.result.new_chunks.length === 0 && (
                            <p className="text-sm text-gray-500 rounded-lg border border-gray-200 bg-gray-50 p-3">
                              No specific updates detected. Check the note and try again, or publish to save any new searchable chunks.
                            </p>
                          )}

                          {replaceFlowState === "diff" && (
                            <div className="flex gap-2 pt-2 border-t border-gray-100">
                              <button
                                onClick={handleReplacePublish}
                                className="min-h-[44px] flex-1 py-2.5 bg-[#0F766E] text-white text-sm font-medium rounded-xl hover:bg-[#0A5C57] focus:outline-none focus:ring-2 focus:ring-[#0F766E]"
                              >
                                Publish updated content
                              </button>
                              <button
                                onClick={handleCancelReplace}
                                className="min-h-[44px] px-4 py-2.5 border border-gray-300 text-gray-600 text-sm font-medium rounded-xl hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-[#0F766E]"
                              >
                                Cancel
                              </button>
                            </div>
                          )}
                        </div>
                      )}

                      {/* Success confirmation */}
                      {replaceFlowState === "success" && replaceConfirmation && (
                        <div className="rounded-xl border border-green-200 bg-green-50 p-4">
                          <p className="text-sm font-semibold text-green-800 mb-2">
                            {replaceConfirmation.employerName} · {replaceConfirmation.factTypeLabel} updated
                          </p>
                          <div className="text-xs text-green-700 space-y-1">
                            {replaceConfirmation.newValue && (
                              <p>Now active: <span className="font-medium">{replaceConfirmation.newValue}</span></p>
                            )}
                            <p>Superseded: <span className="font-medium">{replaceConfirmation.factLabel}</span></p>
                            <p className="text-green-600">Updated: {replaceConfirmation.updatedAt}</p>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Action buttons */}
                  {!showFactEditor && replaceFlowState === "idle" && (
                    <div className="flex gap-2 pt-2">
                      <button
                        onClick={() => setShowFactEditor(true)}
                        className="flex-1 py-2.5 rounded-lg border border-blue-300 text-blue-600 text-sm font-medium hover:bg-blue-50 focus:outline-none focus:ring-2 focus:ring-blue-400"
                      >
                        + New fact
                      </button>
                      <button
                        onClick={handleExtractFacts}
                        disabled={extractLoading || !form.notes?.trim()}
                        className="flex-1 py-2.5 rounded-lg border border-gray-300 text-gray-700 text-sm font-medium hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-blue-400"
                        title={!form.notes?.trim() ? "Add notes first" : ""}
                      >
                        {extractLoading
                          ? <ActionStatus variant="active" size="sm" label="Extracting…" />
                          : "🔍 Extract from notes"}
                      </button>
                    </div>
                  )}

                  {showFactEditor && replaceFlowState === "idle" && (
                    <FactEditor
                      onAdd={handleAddFact}
                      onCancel={() => setShowFactEditor(false)}
                      existingSlugs={facts.map((f) => f.slug)}
                    />
                  )}

                  {undoToast && (
                    <div className="flex items-center justify-between gap-3 rounded-2xl border border-[#D8D0C4] bg-[#FFFDFC] px-4 py-3 text-sm">
                      <span className="text-[#1F2937]">
                        Fact moved to superseded: <span className="font-medium">{undoToast.label}</span>
                      </span>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={handleUndoDelete}
                          className="rounded-full bg-[#0F766E] px-3 py-1.5 text-xs font-medium text-white hover:bg-[#115e59] focus:outline-none focus:ring-2 focus:ring-[#0F766E]"
                        >
                          Undo · {undoToast.remaining}s
                        </button>
                        <button
                          onClick={() => {
                            if (undoTimerRef.current) clearTimeout(undoTimerRef.current)
                            if (undoTickRef.current) clearInterval(undoTickRef.current)
                            undoTimerRef.current = null
                            undoTickRef.current = null
                            setUndoToast(null)
                          }}
                          className="rounded-full px-2 text-xs font-medium text-[#5F6B76] hover:text-[#1F2937]"
                          aria-label="Dismiss undo toast"
                        >
                          ×
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Extraction error banner */}
                  {extractError && (
                    <div className="rounded-lg bg-red-50 border border-red-200 p-3 text-xs text-red-700">
                      {extractError}
                    </div>
                  )}
                </div>
                )}
              </div>

              {/* Extract modal */}
              {showExtractModal && (
                <ExtractedFactsModal
                  extracted={extractedFacts}
                  existing={facts}
                  onAdd={handleAddExtractedFacts}
                  onClose={() => setShowExtractModal(false)}
                  isLoading={extractLoading}
                  error={extractError}
                />
              )}

              {/* Sticky save bar */}
              <div className="sticky bottom-0 z-10 border-t border-[var(--cl-line)] px-4 py-3 bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/80 shadow-[0_-6px_20px_rgba(15,23,42,0.06)]">
                {pendingExtractedCount > 0 && saveState !== "saving" && (
                  <p className="text-xs text-[var(--cl-warning)] mb-2">
                    {pendingExtractedCount} extracted fact{pendingExtractedCount === 1 ? "" : "s"} not saved yet.
                  </p>
                )}
                <div className="flex gap-2">
                  <button
                    onClick={handleSave}
                    disabled={!canSave || saveState === "saving"}
                    className="flex-1 flex items-center justify-center py-2.5 bg-[var(--cl-accent)] text-white text-sm font-medium rounded-xl hover:bg-[var(--cl-accent-strong)] disabled:opacity-40 focus:outline-none focus:ring-2 focus:ring-[var(--cl-accent)]"
                  >
                    {saveState === "saving"
                      ? <ActionStatus variant="on-dark" size="sm" label="Saving…" />
                      : saveButtonLabel}
                  </button>
                  {hasUnsavedChanges && saveState !== "saving" && mode !== "create" && (
                    <button
                      onClick={handleDiscardChanges}
                      className="px-3 py-2.5 border border-[var(--cl-line)] text-[var(--cl-muted)] text-sm font-medium rounded-xl hover:bg-[var(--cl-surface-2)] focus:outline-none focus:ring-2 focus:ring-[var(--cl-line)]"
                    >
                      Discard
                    </button>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
