"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import { adminFetch } from "@/lib/admin-api"

const API_URL = "/api/admin"

interface AlumniCompanyLink {
  company_name: string
  company_slug: string
  relationship: string
  notes: string
}

interface AlumniProfile {
  slug: string
  name: string
  degree: string
  school: string
  graduation_year: string
  current_company: string
  current_title: string
  available_for_mentoring: boolean
  notes: string
  company_links: AlumniCompanyLink[]
  last_updated: string | null
}

interface AlumniExtractedFact {
  slug?: string
  type?: string
  confidence?: number
  source?: string
  data?: Record<string, unknown>
  [key: string]: unknown
}

interface AlumniExtractionPreview {
  interpretation_bullets?: string[]
  summary_bullets?: string[]
  profile_updates?: Record<string, { old: string | null; new: string }>
  company_links?: AlumniCompanyLink[]
  facts?: AlumniExtractedFact[]
  raw?: unknown
  [key: string]: unknown
}

type LoadState = "loading" | "loaded" | "error"
type SaveState = "idle" | "saving" | "success" | "error"
type Mode = "view" | "create"

const EMPTY_PROFILE: AlumniProfile = {
  slug: "",
  name: "",
  degree: "",
  school: "",
  graduation_year: "",
  current_company: "",
  current_title: "",
  available_for_mentoring: false,
  notes: "",
  company_links: [],
  last_updated: null,
}

const ALUMNI_NOTE_STORAGE_KEY = "alumni_note_draft"

function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/\s+/g, "_")
    .replace(/[^a-z0-9_]/g, "")
}

function toText(value: unknown): string {
  if (typeof value === "string") return value
  if (typeof value === "number" || typeof value === "boolean") return String(value)
  return ""
}

function toBoolean(value: unknown): boolean {
  if (typeof value === "boolean") return value
  if (typeof value === "number") return value !== 0
  if (typeof value === "string") return ["true", "yes", "1"].includes(value.toLowerCase())
  return false
}

function getFirstString(source: Record<string, unknown>, keys: string[]): string {
  for (const key of keys) {
    const value = source[key]
    if (typeof value === "string" && value.trim()) return value
  }
  return ""
}

function getFirstValue(source: Record<string, unknown>, keys: string[]): unknown {
  for (const key of keys) {
    if (Object.prototype.hasOwnProperty.call(source, key)) return source[key]
  }
  return undefined
}

function normalizeCompanyLink(raw: unknown): AlumniCompanyLink {
  if (!raw || typeof raw !== "object") {
    const text = typeof raw === "string" ? raw : ""
    return {
      company_name: text,
      company_slug: slugify(text),
      relationship: "",
      notes: "",
    }
  }

  const source = raw as Record<string, unknown>
  const companyName = getFirstString(source, ["company_name", "companyName", "employer_name", "name", "label"])
  const companySlug = getFirstString(source, ["company_slug", "companySlug", "employer_slug", "slug"]) || slugify(companyName)

  return {
    company_name: companyName,
    company_slug: companySlug,
    relationship: getFirstString(source, ["relationship", "role", "connection", "link_type"]),
    notes: getFirstString(source, ["notes", "note", "summary"]),
  }
}

function normalizeProfile(raw: unknown): AlumniProfile {
  const source = (raw && typeof raw === "object") ? (raw as Record<string, unknown>) : {}
  const linksRaw = getFirstValue(source, ["company_links", "companyLinks", "links", "company_associations"])
  const companyLinks = Array.isArray(linksRaw)
    ? linksRaw.map((link) => normalizeCompanyLink(link)).filter((link) => link.company_name || link.company_slug)
    : []

  const name = getFirstString(source, ["name", "full_name", "alumni_name"])
  const currentCompany = getFirstString(source, ["current_company", "company_name", "employer_name"])
  const currentTitle = getFirstString(source, ["current_title", "title", "role_title"])

  return {
    slug: getFirstString(source, ["slug", "id"]) || slugify(name || currentCompany || "alumni"),
    name,
    degree: getFirstString(source, ["degree", "qualification"]),
    school: getFirstString(source, ["school", "university", "institution"]),
    graduation_year: toText(getFirstValue(source, ["graduation_year", "grad_year", "year"])),
    current_company: currentCompany,
    current_title: currentTitle,
    available_for_mentoring: toBoolean(getFirstValue(source, ["available_for_mentoring", "availableForMentoring", "mentor_available"])),
    notes: getFirstString(source, ["notes", "summary", "background_notes"]),
    company_links: companyLinks,
    last_updated: getFirstString(source, ["last_updated", "updated_at"]) || null,
  }
}

function normalizeProfileList(payload: unknown): AlumniProfile[] {
  const items = Array.isArray(payload)
    ? payload
    : Array.isArray((payload as Record<string, unknown> | null)?.results)
      ? ((payload as Record<string, unknown>).results as unknown[])
      : Array.isArray((payload as Record<string, unknown> | null)?.items)
        ? ((payload as Record<string, unknown>).items as unknown[])
        : Array.isArray((payload as Record<string, unknown> | null)?.alumni)
          ? ((payload as Record<string, unknown>).alumni as unknown[])
          : []

  return items.map((item) => normalizeProfile(item)).sort((a, b) => a.name.localeCompare(b.name))
}

function normalizePreview(payload: unknown): AlumniExtractionPreview {
  const source = (payload && typeof payload === "object") ? (payload as Record<string, unknown>) : {}
  const profileUpdates = getFirstValue(source, ["profile_updates", "profileUpdates"])
  const companyLinks = getFirstValue(source, ["company_links", "companyLinks"])
  const facts = getFirstValue(source, ["facts", "extracted_facts"])
  const bullets = getFirstValue(source, ["interpretation_bullets", "summary_bullets", "bullets"])

  return {
    ...source,
    interpretation_bullets: Array.isArray(bullets) ? bullets.map((item) => toText(item)).filter(Boolean) : [],
    summary_bullets: Array.isArray(source.summary_bullets) ? source.summary_bullets.map((item) => toText(item)).filter(Boolean) : [],
    profile_updates:
      profileUpdates && typeof profileUpdates === "object"
        ? (profileUpdates as Record<string, { old: string | null; new: string }>)
        : undefined,
    company_links: Array.isArray(companyLinks)
      ? companyLinks.map((link) => normalizeCompanyLink(link)).filter((link) => link.company_name || link.company_slug)
      : [],
    facts: Array.isArray(facts) ? (facts as AlumniExtractedFact[]) : [],
  }
}

function formatDate(value?: string | null): string {
  if (!value) return "Unknown"
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  })
}

function emptyLink(): AlumniCompanyLink {
  return {
    company_name: "",
    company_slug: "",
    relationship: "",
    notes: "",
  }
}

function buildPayload(profile: AlumniProfile, companyLinks: AlumniCompanyLink[], selectedSlug: string | null) {
  const cleanedLinks = companyLinks
    .map((link) => ({
      company_name: link.company_name.trim(),
      company_slug: (link.company_slug.trim() || slugify(link.company_name)).trim(),
      relationship: link.relationship.trim(),
      notes: link.notes.trim(),
    }))
    .filter((link) => link.company_name.length > 0 || link.company_slug.length > 0 || link.relationship.length > 0 || link.notes.length > 0)

  return {
    slug: selectedSlug || slugify(profile.name),
    name: profile.name.trim(),
    degree: profile.degree.trim() || null,
    school: profile.school.trim() || null,
    graduation_year: profile.graduation_year.trim() ? Number(profile.graduation_year.trim()) : null,
    current_company: profile.current_company.trim() || null,
    current_title: profile.current_title.trim() || null,
    available_for_mentoring: profile.available_for_mentoring,
    notes: profile.notes.trim() || null,
    company_links: cleanedLinks,
    last_updated: new Date().toISOString(),
  }
}

export default function AlumniFactsTab() {
  const [alumni, setAlumni] = useState<AlumniProfile[]>([])
  const [loadState, setLoadState] = useState<LoadState>("loading")
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null)
  const [mode, setMode] = useState<Mode>("view")
  const [form, setForm] = useState<AlumniProfile>(EMPTY_PROFILE)
  const [companyLinks, setCompanyLinks] = useState<AlumniCompanyLink[]>([])
  const [saveState, setSaveState] = useState<SaveState>("idle")
  const [banner, setBanner] = useState("")
  const [error, setError] = useState("")
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState("")
  const [preview, setPreview] = useState<AlumniExtractionPreview | null>(null)
  const bannerTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const selectedProfile = useMemo(
    () => alumni.find((item) => item.slug === selectedSlug) ?? null,
    [alumni, selectedSlug]
  )

  function showBanner(message: string) {
    if (bannerTimerRef.current) clearTimeout(bannerTimerRef.current)
    setBanner(message)
    bannerTimerRef.current = setTimeout(() => {
      setBanner("")
      setSaveState("idle")
    }, 3000)
  }

  function loadProfile(profile: AlumniProfile | null, nextMode: Mode = "view") {
    if (!profile) {
      setSelectedSlug(null)
      setForm(EMPTY_PROFILE)
      setCompanyLinks([])
      setMode(nextMode)
      return
    }

    setSelectedSlug(profile.slug)
    setForm({ ...profile, company_links: profile.company_links.map((link) => ({ ...link })) })
    setCompanyLinks(profile.company_links.map((link) => ({ ...link })))
    setPreview(null)
    setPreviewError("")
    setMode(nextMode)
  }

  async function loadAlumni(preferredSlug?: string | null) {
    const stagedNotes = typeof window !== "undefined" ? sessionStorage.getItem(ALUMNI_NOTE_STORAGE_KEY) : null
    if (stagedNotes) {
      sessionStorage.removeItem(ALUMNI_NOTE_STORAGE_KEY)
      loadProfile(null, "create")
      setForm({ ...EMPTY_PROFILE, notes: stagedNotes })
      setCompanyLinks([])
      setPreview(null)
      setPreviewError("")
      showBanner("Meeting note loaded from the Staging Area.")
    }

    setLoadState("loading")
    setError("")
    try {
      const res = await adminFetch("/api/kb/alumni")
      if (!res.ok) throw new Error("failed")
      const data = normalizeProfileList(await res.json())
      setAlumni(data)
      if (!stagedNotes) {
        const nextSlug = preferredSlug ?? selectedSlug ?? data[0]?.slug ?? null
        const nextProfile = nextSlug ? data.find((item) => item.slug === nextSlug) ?? data[0] ?? null : null
        if (nextProfile) {
          loadProfile(nextProfile)
        } else {
          loadProfile(null)
        }
      }
      setLoadState("loaded")
    } catch {
      setLoadState("error")
      setError("We could not load alumni records right now.")
    }
  }

  useEffect(() => {
    void loadAlumni()
    return () => {
      if (bannerTimerRef.current) clearTimeout(bannerTimerRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function selectProfile(profile: AlumniProfile) {
    setError("")
    setSaveState("idle")
    setPreview(null)
    loadProfile(profile)
  }

  function startCreate() {
    setError("")
    setSaveState("idle")
    setPreview(null)
    loadProfile(null, "create")
  }

  function updateField<K extends keyof AlumniProfile>(field: K, value: AlumniProfile[K]) {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  function updateLink(index: number, field: keyof AlumniCompanyLink, value: string) {
    setCompanyLinks((prev) => prev.map((link, i) => (i === index ? { ...link, [field]: value } : link)))
  }

  function addCompanyLink() {
    setCompanyLinks((prev) => [...prev, emptyLink()])
  }

  function removeCompanyLink(index: number) {
    setCompanyLinks((prev) => prev.filter((_, i) => i !== index))
  }

  async function handleSave() {
    if (!form.name.trim()) {
      setError("Add the alumni name before saving.")
      return
    }

    setSaveState("saving")
    setError("")
    try {
      const payload = buildPayload(form, companyLinks, selectedSlug)
      const method = mode === "create" || !selectedSlug ? "POST" : "PUT"
      const path = method === "POST" ? "/api/kb/alumni" : `/api/kb/alumni/${selectedSlug}`
      const res = await adminFetch(path, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || "Save failed.")
      }

      const saved = normalizeProfile(await res.json())
      setAlumni((prev) => {
        const exists = prev.some((item) => item.slug === saved.slug)
        if (exists) return prev.map((item) => (item.slug === saved.slug ? saved : item)).sort((a, b) => a.name.localeCompare(b.name))
        return [...prev, saved].sort((a, b) => a.name.localeCompare(b.name))
      })
      loadProfile(saved)
      setMode("view")
      showBanner(mode === "create" || !selectedSlug ? "Alumni profile created." : "Alumni profile saved.")
    } catch (err) {
      setSaveState("error")
      setError(err instanceof Error ? err.message : "Save failed.")
    }
  }

  async function handlePreviewExtraction() {
    const text = form.notes.trim()
    if (!text) {
      setPreviewError("Add a counselor note first to preview extraction.")
      return
    }

    setPreviewLoading(true)
    setPreviewError("")
    setPreview(null)

    try {
      const res = await adminFetch("/api/kb/alumni/extract-preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text,
          alumni_slug: selectedSlug,
        }),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || "Preview extraction failed.")
      }

      setPreview(normalizePreview(await res.json()))
    } catch (err) {
      setPreviewError(err instanceof Error ? err.message : "Preview extraction failed.")
    } finally {
      setPreviewLoading(false)
    }
  }

  function renderPreviewContent() {
    if (!preview) return null

    const bullets = preview.interpretation_bullets?.length ? preview.interpretation_bullets : preview.summary_bullets ?? []
    const updateEntries = preview.profile_updates ? Object.entries(preview.profile_updates) : []

    return (
      <div className="space-y-4">
        {bullets.length > 0 && (
          <div>
            <p className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">What the LLM saw</p>
            <ul className="mt-2 space-y-2 text-sm text-[var(--cl-ink)]">
              {bullets.map((bullet, index) => (
                <li key={`${bullet}-${index}`} className="rounded-2xl border border-[var(--cl-line)] bg-white px-4 py-3">
                  {bullet}
                </li>
              ))}
            </ul>
          </div>
        )}

        {updateEntries.length > 0 && (
          <div>
            <p className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Suggested profile changes</p>
            <div className="mt-2 space-y-2">
              {updateEntries.map(([field, change]) => (
                <div key={field} className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface)] px-4 py-3 text-sm">
                  <p className="font-medium text-[var(--cl-ink)]">{field.replace(/_/g, " ")}</p>
                  <p className="mt-1 text-[var(--cl-muted)]">
                    <span className="font-medium text-[var(--cl-ink)]">New:</span> {change.new}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {preview.company_links && preview.company_links.length > 0 && (
          <div>
            <p className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Suggested company links</p>
            <div className="mt-2 space-y-2">
              {preview.company_links.map((link, index) => (
                <div key={`${link.company_slug}-${index}`} className="rounded-2xl border border-[var(--cl-line)] bg-white px-4 py-3 text-sm">
                  <p className="font-medium text-[var(--cl-ink)]">{link.company_name || link.company_slug}</p>
                  <p className="mt-1 text-[var(--cl-muted)]">
                    {link.relationship || "Linked company"}
                    {link.notes ? ` · ${link.notes}` : ""}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {preview.facts && preview.facts.length > 0 && (
          <div>
            <p className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Raw extracted facts</p>
            <div className="mt-2 space-y-2">
              {preview.facts.map((fact, index) => (
                <div key={fact.slug ?? `${fact.type ?? "fact"}-${index}`} className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-4 py-3 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full bg-[var(--cl-accent)]/10 px-2.5 py-1 text-xs font-medium text-[var(--cl-accent)]">
                      {fact.type ?? "fact"}
                    </span>
                    {fact.confidence !== undefined && (
                      <span className="text-xs text-[var(--cl-muted)]">Confidence {fact.confidence}%</span>
                    )}
                  </div>
                  <p className="mt-2 font-medium text-[var(--cl-ink)]">{fact.slug ?? "untitled fact"}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {preview.raw !== undefined && preview.raw !== null && (
          <div>
            <p className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Preview payload</p>
            <pre className="mt-2 overflow-x-auto rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-4 text-xs text-[var(--cl-ink)]">
              {JSON.stringify(preview.raw, null, 2)}
            </pre>
          </div>
        )}
      </div>
    )
  }

  const selectedLabel = selectedProfile ? selectedProfile.name : mode === "create" ? "New alumni profile" : "No alumni selected"

  return (
    <section className="space-y-6">
      <div className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-6 shadow-[0_12px_30px_rgba(31,41,55,0.06)]">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="font-mono-display text-[11px] uppercase tracking-[0.26em] text-[var(--cl-secondary)]">Career Wire</p>
            <h2 className="mt-2 font-display text-3xl leading-tight text-[var(--cl-ink)]">Alumni Records</h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--cl-muted)]">
              Keep alumni profiles, company links, and meeting-note extraction previews in one counselor-facing workspace.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={startCreate}
              className="rounded-full border border-[var(--cl-accent)] bg-[var(--cl-accent)] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--cl-accent)]/90"
            >
              New Alumni
            </button>
            <button
              type="button"
              onClick={() => void loadAlumni(selectedSlug)}
              className="rounded-full border border-[var(--cl-line)] bg-white/70 px-4 py-2 text-sm text-[var(--cl-ink)] transition-colors hover:border-[var(--cl-accent)]/60 hover:bg-white"
            >
              Refresh
            </button>
          </div>
        </div>

        {banner && (
          <div className="mt-4 rounded-2xl border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
            {banner}
          </div>
        )}
        {error && (
          <div className="mt-4 rounded-2xl border border-[var(--cl-error)]/25 bg-[var(--cl-error)]/10 px-4 py-3 text-sm text-[var(--cl-error)]">
            {error}
          </div>
        )}
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(280px,0.82fr)_minmax(0,1.18fr)]">
        <aside className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-4 shadow-[0_12px_30px_rgba(31,41,55,0.06)]">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Alumni list</p>
              <p className="mt-1 font-display text-xl text-[var(--cl-ink)]">{alumni.length} profiles</p>
            </div>
            <span className="rounded-full bg-[var(--cl-surface-2)] px-3 py-1 text-xs font-medium text-[var(--cl-muted)]">
              {loadState === "loading" ? "Loading" : loadState === "error" ? "Offline" : "Ready"}
            </span>
          </div>

          <div className="space-y-2">
            {alumni.map((profile) => {
              const active = profile.slug === selectedSlug
              return (
                <button
                  key={profile.slug}
                  type="button"
                  onClick={() => selectProfile(profile)}
                  className={`w-full rounded-2xl border px-4 py-3 text-left transition-colors ${
                    active
                      ? "border-[var(--cl-accent)] bg-[var(--cl-accent)]/8"
                      : "border-[var(--cl-line)] bg-[var(--cl-surface)] hover:border-[var(--cl-accent)]/40"
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-display text-lg text-[var(--cl-ink)]">{profile.name || profile.slug}</p>
                      <p className="mt-1 text-sm text-[var(--cl-muted)]">
                        {profile.current_title || "No title"}{profile.current_company ? ` · ${profile.current_company}` : ""}
                      </p>
                      <p className="mt-1 text-xs uppercase tracking-[0.16em] text-[var(--cl-muted)]">
                        {profile.school || "No school"}{profile.graduation_year ? ` · ${profile.graduation_year}` : ""}
                      </p>
                    </div>
                    {profile.available_for_mentoring && (
                      <span className="rounded-full bg-[var(--cl-accent)] px-2.5 py-1 text-xs font-medium text-white">
                        Mentor
                      </span>
                    )}
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <span className="rounded-full bg-[var(--cl-surface-2)] px-2.5 py-1 text-xs font-medium text-[var(--cl-muted)]">
                      {profile.company_links.length} company link{profile.company_links.length === 1 ? "" : "s"}
                    </span>
                    <span className="rounded-full bg-[var(--cl-surface-2)] px-2.5 py-1 text-xs font-medium text-[var(--cl-muted)]">
                      Updated {formatDate(profile.last_updated)}
                    </span>
                  </div>
                </button>
              )
            })}

            {loadState !== "loading" && alumni.length === 0 && (
              <div className="rounded-2xl border border-dashed border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-4 py-6 text-center">
                <p className="font-display text-xl text-[var(--cl-ink)]">No alumni yet</p>
                <p className="mt-2 text-sm text-[var(--cl-muted)]">
                  Start with the first trusted alumnus and add company links after the profile is saved.
                </p>
              </div>
            )}
          </div>
        </aside>

        <div className="space-y-6">
          <section className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-6 shadow-[0_12px_30px_rgba(31,41,55,0.06)]">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Note extraction</p>
                <h3 className="mt-1 font-display text-2xl text-[var(--cl-ink)]">Paste the counselor note once</h3>
                <p className="mt-1 text-sm text-[var(--cl-muted)]">
                  The same note powers extraction preview and the saved counselor note field below.
                </p>
              </div>
              <button
                type="button"
                onClick={() => void handlePreviewExtraction()}
                disabled={previewLoading || !form.notes.trim()}
                className="rounded-full border border-[var(--cl-accent)] bg-[var(--cl-accent)] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--cl-accent)]/90 disabled:opacity-60"
              >
                {previewLoading ? "Previewing…" : "Preview extraction"}
              </button>
            </div>

            <label className="mt-4 block space-y-2">
              <span className="text-sm font-medium text-[var(--cl-ink)]">Counselor note</span>
              <textarea
                value={form.notes}
                onChange={(event) => updateField("notes", event.target.value)}
                className="min-h-[160px] w-full rounded-2xl border border-[var(--cl-line)] bg-white px-4 py-3 text-sm text-[var(--cl-ink)] outline-none transition-colors focus:border-[var(--cl-accent)]"
                placeholder="Paste the alumni conversation here. The preview and saved record both use this note."
              />
            </label>

            {previewError && (
              <div className="mt-4 rounded-2xl border border-[var(--cl-error)]/25 bg-[var(--cl-error)]/10 px-4 py-3 text-sm text-[var(--cl-error)]">
                {previewError}
              </div>
            )}

            {preview && <div className="mt-5">{renderPreviewContent()}</div>}
          </section>

          <section className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-6 shadow-[0_12px_30px_rgba(31,41,55,0.06)]">
            <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Selected profile</p>
                <h3 className="mt-1 font-display text-2xl text-[var(--cl-ink)]">{selectedLabel}</h3>
                <p className="mt-1 text-sm text-[var(--cl-muted)]">
                  Edit the profile fields below, then save the company links counselors rely on for referrals and mentoring.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <span className="rounded-full bg-[var(--cl-surface-2)] px-3 py-1 text-xs font-medium text-[var(--cl-muted)]">
                  {mode === "create" ? "Create mode" : "Edit mode"}
                </span>
                <span className="rounded-full bg-[var(--cl-surface-2)] px-3 py-1 text-xs font-medium text-[var(--cl-muted)]">
                  {companyLinks.length} link{companyLinks.length === 1 ? "" : "s"}
                </span>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <label className="space-y-2">
                <span className="text-sm font-medium text-[var(--cl-ink)]">Full name</span>
                <input
                  value={form.name}
                  onChange={(event) => updateField("name", event.target.value)}
                  className="w-full rounded-2xl border border-[var(--cl-line)] bg-white px-4 py-3 text-sm text-[var(--cl-ink)] outline-none transition-colors focus:border-[var(--cl-accent)]"
                  placeholder="Aditya Mehta"
                />
              </label>
              <label className="space-y-2">
                <span className="text-sm font-medium text-[var(--cl-ink)]">Current company</span>
                <input
                  value={form.current_company}
                  onChange={(event) => updateField("current_company", event.target.value)}
                  className="w-full rounded-2xl border border-[var(--cl-line)] bg-white px-4 py-3 text-sm text-[var(--cl-ink)] outline-none transition-colors focus:border-[var(--cl-accent)]"
                  placeholder="Stripe Singapore"
                />
              </label>
              <label className="space-y-2">
                <span className="text-sm font-medium text-[var(--cl-ink)]">Current title</span>
                <input
                  value={form.current_title}
                  onChange={(event) => updateField("current_title", event.target.value)}
                  className="w-full rounded-2xl border border-[var(--cl-line)] bg-white px-4 py-3 text-sm text-[var(--cl-ink)] outline-none transition-colors focus:border-[var(--cl-accent)]"
                  placeholder="Head of Compliance"
                />
              </label>
              <label className="space-y-2">
                <span className="text-sm font-medium text-[var(--cl-ink)]">School</span>
                <input
                  value={form.school}
                  onChange={(event) => updateField("school", event.target.value)}
                  className="w-full rounded-2xl border border-[var(--cl-line)] bg-white px-4 py-3 text-sm text-[var(--cl-ink)] outline-none transition-colors focus:border-[var(--cl-accent)]"
                  placeholder="NUS"
                />
              </label>
              <label className="space-y-2">
                <span className="text-sm font-medium text-[var(--cl-ink)]">Degree</span>
                <input
                  value={form.degree}
                  onChange={(event) => updateField("degree", event.target.value)}
                  className="w-full rounded-2xl border border-[var(--cl-line)] bg-white px-4 py-3 text-sm text-[var(--cl-ink)] outline-none transition-colors focus:border-[var(--cl-accent)]"
                  placeholder="LLM"
                />
              </label>
              <label className="space-y-2">
                <span className="text-sm font-medium text-[var(--cl-ink)]">Graduation year</span>
                <input
                  value={form.graduation_year}
                  onChange={(event) => updateField("graduation_year", event.target.value)}
                  className="w-full rounded-2xl border border-[var(--cl-line)] bg-white px-4 py-3 text-sm text-[var(--cl-ink)] outline-none transition-colors focus:border-[var(--cl-accent)]"
                  placeholder="2018"
                  inputMode="numeric"
                />
              </label>
            </div>

            <label className="mt-4 flex items-center gap-3 rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-4 py-3">
              <input
                type="checkbox"
                checked={form.available_for_mentoring}
                onChange={(event) => updateField("available_for_mentoring", event.target.checked)}
                className="h-4 w-4 rounded border-[var(--cl-line)] text-[var(--cl-accent)] focus:ring-[var(--cl-accent)]"
              />
              <span className="text-sm text-[var(--cl-ink)]">Available for mentoring</span>
            </label>

            <div className="mt-5 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => void handleSave()}
                className="rounded-full border border-[var(--cl-accent)] bg-[var(--cl-accent)] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--cl-accent)]/90 disabled:opacity-60"
                disabled={saveState === "saving"}
              >
                {saveState === "saving" ? "Saving…" : mode === "create" ? "Create alumni" : "Save alumni"}
              </button>
              {mode === "create" && (
                <button
                  type="button"
                  onClick={() => (selectedProfile ? loadProfile(selectedProfile) : loadProfile(null))}
                  className="rounded-full border border-[var(--cl-line)] bg-white/70 px-4 py-2 text-sm text-[var(--cl-ink)] transition-colors hover:border-[var(--cl-accent)]/60 hover:bg-white"
                >
                  Cancel
                </button>
              )}
            </div>
          </section>

          <section className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-6 shadow-[0_12px_30px_rgba(31,41,55,0.06)]">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Company links</p>
                <h3 className="mt-1 font-display text-2xl text-[var(--cl-ink)]">Trusted companies and referral context</h3>
                <p className="mt-1 text-sm text-[var(--cl-muted)]">
                  Add the companies this alumnus can speak about, refer into, or mentor students around.
                </p>
              </div>
              <button
                type="button"
                onClick={addCompanyLink}
                className="rounded-full border border-[var(--cl-line)] bg-white/70 px-4 py-2 text-sm text-[var(--cl-ink)] transition-colors hover:border-[var(--cl-accent)]/60 hover:bg-white"
              >
                Add company link
              </button>
            </div>

            <div className="mt-4 space-y-3">
              {companyLinks.length === 0 && (
                <div className="rounded-2xl border border-dashed border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-4 py-5 text-sm text-[var(--cl-muted)]">
                  No company links yet. Add the companies this alumnus can meaningfully help with.
                </div>
              )}

              {companyLinks.map((link, index) => (
                <div key={`${index}-${link.company_slug || link.company_name}`} className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] p-4">
                  <div className="grid gap-4 md:grid-cols-2">
                    <label className="space-y-2">
                      <span className="text-sm font-medium text-[var(--cl-ink)]">Company name</span>
                      <input
                        value={link.company_name}
                        onChange={(event) => updateLink(index, "company_name", event.target.value)}
                        className="w-full rounded-2xl border border-[var(--cl-line)] bg-white px-4 py-3 text-sm text-[var(--cl-ink)] outline-none transition-colors focus:border-[var(--cl-accent)]"
                        placeholder="Stripe Singapore"
                      />
                    </label>
                    <label className="space-y-2">
                      <span className="text-sm font-medium text-[var(--cl-ink)]">Company slug</span>
                      <input
                        value={link.company_slug}
                        onChange={(event) => updateLink(index, "company_slug", event.target.value)}
                        className="w-full rounded-2xl border border-[var(--cl-line)] bg-white px-4 py-3 text-sm text-[var(--cl-ink)] outline-none transition-colors focus:border-[var(--cl-accent)]"
                        placeholder="stripe_singapore"
                      />
                    </label>
                    <label className="space-y-2">
                      <span className="text-sm font-medium text-[var(--cl-ink)]">Relationship</span>
                      <input
                        value={link.relationship}
                        onChange={(event) => updateLink(index, "relationship", event.target.value)}
                        className="w-full rounded-2xl border border-[var(--cl-line)] bg-white px-4 py-3 text-sm text-[var(--cl-ink)] outline-none transition-colors focus:border-[var(--cl-accent)]"
                        placeholder="Mentor contact"
                      />
                    </label>
                    <label className="space-y-2">
                      <span className="text-sm font-medium text-[var(--cl-ink)]">Company notes</span>
                      <input
                        value={link.notes}
                        onChange={(event) => updateLink(index, "notes", event.target.value)}
                        className="w-full rounded-2xl border border-[var(--cl-line)] bg-white px-4 py-3 text-sm text-[var(--cl-ink)] outline-none transition-colors focus:border-[var(--cl-accent)]"
                        placeholder="Can refer students into compliance and risk roles"
                      />
                    </label>
                  </div>

                  <div className="mt-3 flex justify-end">
                    <button
                      type="button"
                      onClick={() => removeCompanyLink(index)}
                      className="rounded-full border border-[var(--cl-line)] bg-white px-3 py-1.5 text-xs font-medium text-[var(--cl-muted)] transition-colors hover:border-[var(--cl-accent)]/50 hover:text-[var(--cl-ink)]"
                    >
                      Remove link
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    </section>
  )
}
