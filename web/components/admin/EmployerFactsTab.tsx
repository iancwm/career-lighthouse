"use client"
import { useEffect, useRef, useState } from "react"

const API_URL = "/api/admin"

// ── Types ─────────────────────────────────────────────────────────────────

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
  const saveBannerTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const isDirty = useRef(false)

  const trackOptions = profiles.map((p) => ({ value: p.slug, label: p.career_type }))

  useEffect(() => {
    fetchEmployers()
    fetchProfiles()
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
    if (isDirty.current) {
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
    isDirty.current = false
    setUnsavedConfirm(null)
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
    isDirty.current = false
  }

  function updateField(field: keyof EmployerDetail, value: unknown) {
    setForm((prev) => ({ ...prev, [field]: value }))
    isDirty.current = true
    if (field === "employer_name" && !slugManuallyEdited && mode === "create") {
      setSlugPreview(slugify(value as string))
    }
  }

  async function handleSave() {
    if (mode === "create") {
      await handleCreate()
    } else {
      await handleUpdate()
    }
  }

  async function handleCreate() {
    if (!form.employer_name?.trim()) return
    const slug = slugPreview || slugify(form.employer_name)
    if (!slug) return

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
        return
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
    } catch {
      setSaveState("error")
      setSaveBanner("Save failed — network error.")
    }
  }

  async function handleUpdate() {
    if (!selected) return
    setSaveState("saving")
    try {
      const body: EmployerDetail = {
        ...selected,
        ...form,
        slug: selected.slug,
        completeness: "amber",
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
        return
      }
      const updated: EmployerDetail = await r.json()
      setEmployers((prev) => prev.map((e) => (e.slug === updated.slug ? updated : e)))
      setSelected(updated)
      setForm({ ...updated })
      setSaveState("success")
      showSuccessBanner("Saved.")
      isDirty.current = false
    } catch {
      setSaveState("error")
      setSaveBanner("Save failed — network error.")
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

  const canSave = mode === "create"
    ? Boolean(form.employer_name?.trim() && (slugPreview || slugify(form.employer_name || "")))
    : Boolean(selected)

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
                      className={`flex items-center gap-2 px-3 py-2.5 cursor-pointer transition-colors border-b border-gray-100 group ${
                        isSelected
                          ? "bg-blue-50 border-l-2 border-l-blue-400"
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
          {unsavedConfirm && (
            <div className="flex items-center gap-3 px-4 py-2.5 bg-amber-50 border-b border-amber-200 text-xs text-amber-800">
              <span>Unsaved changes to <span className="font-medium">{selected?.employer_name || "this employer"}</span></span>
              <button
                onClick={() => { handleSave().then(() => { if (unsavedConfirm) commitSelection(unsavedConfirm) }) }}
                className="px-2 py-1 bg-amber-600 text-white rounded hover:bg-amber-700 focus:outline-none focus:ring-2 focus:ring-amber-400"
              >
                Save
              </button>
              <button
                onClick={() => { isDirty.current = false; commitSelection(unsavedConfirm) }}
                className="px-2 py-1 border border-amber-300 text-amber-700 rounded hover:bg-amber-100 focus:outline-none focus:ring-2 focus:ring-amber-400"
              >
                Discard
              </button>
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
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                <h3 className="text-sm font-semibold text-gray-700">
                  {mode === "create" ? "New employer record" : selected?.employer_name}
                </h3>

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

              {/* Sticky Save button */}
              <div className="border-t border-gray-100 px-4 py-3 bg-white">
                <button
                  onClick={handleSave}
                  disabled={!canSave || saveState === "saving"}
                  className="w-full py-2.5 bg-blue-600 text-white text-sm font-medium rounded-xl hover:bg-blue-700 disabled:opacity-40 focus:outline-none focus:ring-2 focus:ring-blue-400"
                >
                  {saveState === "saving" ? (
                    <span className="flex items-center justify-center gap-2">
                      <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Saving...
                    </span>
                  ) : mode === "create" ? "Create employer record" : "Save employer updates"}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
