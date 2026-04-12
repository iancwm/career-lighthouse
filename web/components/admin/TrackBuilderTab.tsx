"use client"
import { useEffect, useState } from "react"

interface DraftTrackDetail {
  slug: string
  track_name: string
  status: string
  match_description: string
  match_keywords: string[]
  ep_sponsorship: string
  compass_score_typical: string
  top_employers_smu: string[]
  recruiting_timeline: string
  international_realistic: boolean
  entry_paths: string[]
  salary_range_2024: string
  typical_background: string
  counselor_contact: string | null
  notes: string
  source_refs: { type: string; label: string }[]
  last_updated: string | null
  archived_at: string | null
}

interface TrackRegistryEntry {
  slug: string
  label: string
  status: string
  last_published: string | null
}

interface TrackReferenceDetail {
  slug: string
  label: string
  status: string
  last_published: string | null
  track_name: string
  match_description: string
  match_keywords: string[]
  ep_sponsorship: string
  compass_score_typical: string
  top_employers_smu: string[]
  recruiting_timeline: string
  international_realistic: boolean
  entry_paths: string[]
  salary_range_2024: string
  typical_background: string
  counselor_contact: string | null
  notes: string
}

interface TrackVersionInfo {
  version: string
  published_at: string
  filename: string
}

interface TrackBuilderTabProps {
  selectedSlug?: string | null
  onSelectedSlugChange?: (slug: string | null) => void
}

const EMPTY_DRAFT: DraftTrackDetail = {
  slug: "",
  track_name: "",
  status: "draft",
  match_description: "",
  match_keywords: [],
  ep_sponsorship: "",
  compass_score_typical: "",
  top_employers_smu: [],
  recruiting_timeline: "",
  international_realistic: true,
  entry_paths: [],
  salary_range_2024: "",
  typical_background: "",
  counselor_contact: "",
  notes: "",
  source_refs: [],
  last_updated: null,
  archived_at: null,
}

function parseMultiLine(value: string) {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean)
}

function parseCommaList(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
}

export default function TrackBuilderTab({
  selectedSlug: selectedSlugProp,
  onSelectedSlugChange,
}: TrackBuilderTabProps = {}) {
  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
  const [drafts, setDrafts] = useState<DraftTrackDetail[]>([])
  const [tracks, setTracks] = useState<TrackRegistryEntry[]>([])
  const [internalSelectedSlug, setInternalSelectedSlug] = useState<string | null>(null)
  const [form, setForm] = useState<DraftTrackDetail>(EMPTY_DRAFT)
  const [sourceMode, setSourceMode] = useState<"note" | "file">("note")
  const [sourceText, setSourceText] = useState("")
  const [sourceFile, setSourceFile] = useState<File | null>(null)
  const [history, setHistory] = useState<TrackVersionInfo[]>([])
  const [publishedDetail, setPublishedDetail] = useState<TrackReferenceDetail | null>(null)
  const [publishedLoading, setPublishedLoading] = useState(false)
  const [publishedError, setPublishedError] = useState("")
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [rollingBack, setRollingBack] = useState(false)
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")
  const isControlled = selectedSlugProp !== undefined
  const selectedSlug = isControlled ? selectedSlugProp : internalSelectedSlug

  function setSelectedSlug(next: string | null) {
    if (!isControlled) {
      setInternalSelectedSlug(next)
    }
    if (next !== selectedSlugProp) {
      onSelectedSlugChange?.(next)
    }
  }

  async function loadAll(preferredSlug?: string | null) {
    setLoading(true)
    setError("")
    try {
      const [draftRes, trackRes] = await Promise.all([
        fetch(`${API_URL}/api/kb/draft-tracks`),
        fetch(`${API_URL}/api/kb/tracks`),
      ])
      if (!draftRes.ok || !trackRes.ok) throw new Error("load failed")
      const [draftData, trackData]: [DraftTrackDetail[], TrackRegistryEntry[]] = await Promise.all([
        draftRes.json(),
        trackRes.json(),
      ])
      setDrafts(draftData)
      setTracks(trackData)
      const nextSlug =
        preferredSlug === undefined
          ? selectedSlug ?? draftData[0]?.slug ?? null
          : preferredSlug
      setSelectedSlug(nextSlug)
      const selected = draftData.find((item) => item.slug === nextSlug)
      setForm(selected ?? EMPTY_DRAFT)
    } catch {
      setError("We could not load draft tracks right now.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadAll(isControlled ? selectedSlugProp : undefined)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isControlled, selectedSlugProp])

  useEffect(() => {
    if (!selectedSlug) {
      setPublishedDetail(null)
      setPublishedError("")
      return
    }
    if (!tracks.some((track) => track.slug === selectedSlug)) {
      setPublishedDetail(null)
      return
    }
    let cancelled = false
    setPublishedLoading(true)
    setPublishedError("")
    fetch(`${API_URL}/api/kb/tracks/${selectedSlug}`)
      .then((r) => {
        if (!r.ok) throw new Error("published track fetch failed")
        return r.json()
      })
      .then((data: TrackReferenceDetail) => {
        if (!cancelled) setPublishedDetail(data)
      })
      .catch(() => {
        if (!cancelled) setPublishedError("We could not load the published reference summary.")
      })
      .finally(() => {
        if (!cancelled) setPublishedLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [selectedSlug, tracks])

  useEffect(() => {
    if (!selectedSlug || !tracks.some((track) => track.slug === selectedSlug)) {
      setHistory([])
      return
    }
    fetch(`${API_URL}/api/kb/tracks/${selectedSlug}/history`)
      .then((r) => {
        if (!r.ok) throw new Error("history failed")
        return r.json()
      })
      .then((data: TrackVersionInfo[]) => setHistory(data))
      .catch(() => setHistory([]))
  }, [selectedSlug, tracks])

  function updateField<K extends keyof DraftTrackDetail>(key: K, value: DraftTrackDetail[K]) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  async function saveDraft() {
    setSaving(true)
    setError("")
    setNotice("")
    const payload = { ...form }
    const method = selectedSlug ? "PUT" : "POST"
    const url = selectedSlug
      ? `${API_URL}/api/kb/draft-tracks/${selectedSlug}`
      : `${API_URL}/api/kb/draft-tracks`
    try {
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
      if (!res.ok) throw new Error("save failed")
      const saved: DraftTrackDetail = await res.json()
      setNotice("Draft saved.")
      await loadAll(saved.slug)
    } catch {
      setError("We could not save this draft track.")
    } finally {
      setSaving(false)
    }
  }

  async function publishDraft() {
    if (!selectedSlug) return
    setPublishing(true)
    setError("")
    setNotice("")
    try {
      const res = await fetch(`${API_URL}/api/kb/draft-tracks/${selectedSlug}/publish`, {
        method: "POST",
      })
      if (!res.ok) throw new Error("publish failed")
      setNotice("Track published.")
      await loadAll(selectedSlug)
    } catch {
      setError("We could not publish this draft yet.")
    } finally {
      setPublishing(false)
    }
  }

  async function rollbackTrack() {
    if (!selectedSlug) return
    setRollingBack(true)
    setError("")
    setNotice("")
    try {
      const res = await fetch(`${API_URL}/api/kb/tracks/${selectedSlug}/rollback`, {
        method: "POST",
      })
      if (!res.ok) throw new Error("rollback failed")
      setNotice("Published track rolled back.")
      await loadAll(selectedSlug)
    } catch {
      setError("We could not roll back this published track.")
    } finally {
      setRollingBack(false)
    }
  }

  async function generateDraft() {
    setGenerating(true)
    setError("")
    setNotice("")
    try {
      const payload = new FormData()
      payload.append("slug", form.slug.trim())
      payload.append("track_name", form.track_name.trim())
      if (sourceMode === "file" && sourceFile) {
        payload.append("source_type", "file")
        payload.append("file", sourceFile)
      } else {
        payload.append("source_type", "note")
        payload.append("text", sourceText.trim())
      }
      const res = await fetch(`${API_URL}/api/kb/draft-tracks/generate`, {
        method: "POST",
        body: payload,
      })
      if (!res.ok) throw new Error("generate failed")
      const generated: DraftTrackDetail = await res.json()
      setNotice("Draft created from research.")
      setSourceText("")
      setSourceFile(null)
      await loadAll(generated.slug)
    } catch {
      setError("We could not turn this research into a draft yet.")
    } finally {
      setGenerating(false)
    }
  }

  async function refreshDraftFromResearch() {
    if (!selectedSlug) return
    setGenerating(true)
    setError("")
    setNotice("")
    try {
      const payload = new FormData()
      if (sourceMode === "file" && sourceFile) {
        payload.append("source_type", "file")
        payload.append("file", sourceFile)
      } else {
        payload.append("source_type", "note")
        payload.append("text", sourceText.trim())
      }
      const res = await fetch(`${API_URL}/api/kb/draft-tracks/${selectedSlug}/generate-update`, {
        method: "POST",
        body: payload,
      })
      if (!res.ok) throw new Error("refresh failed")
      const refreshed: DraftTrackDetail = await res.json()
      setNotice("Draft updated from new research.")
      setSourceText("")
      setSourceFile(null)
      await loadAll(refreshed.slug)
    } catch {
      setError("We could not update this draft from the new research yet.")
    } finally {
      setGenerating(false)
    }
  }

  function startNewDraft() {
    setSelectedSlug(null)
    setForm(EMPTY_DRAFT)
    setSourceText("")
    setSourceFile(null)
    setHistory([])
    setPublishedDetail(null)
    setPublishedError("")
    setError("")
    setNotice("")
  }

  const selectedPublishedTrack = publishedDetail

  return (
    <div>
      <h2 className="text-lg font-semibold mb-1">Track Builder</h2>
      <p className="text-sm text-gray-500 mb-4 max-w-3xl">
        Use this only when recurring evidence suggests a distinct new or revised track. Draft from research here, compare against the live reference, and publish only after expert review.
      </p>

      {error && (
        <div className="mb-4 rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}
      {notice && (
        <div className="mb-4 rounded border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
          {notice}
        </div>
      )}

      <div className="grid grid-cols-[280px_minmax(0,1fr)] gap-6">
        <div className="rounded-xl border border-gray-200 p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-gray-700">Draft Tracks</h3>
            <button
              onClick={startNewDraft}
              className="text-xs text-blue-600 hover:text-blue-800"
            >
              New draft
            </button>
          </div>

          {loading ? (
            <p className="text-sm text-gray-400">Loading drafts…</p>
          ) : drafts.length === 0 ? (
            <p className="text-sm text-gray-400">No draft tracks yet.</p>
          ) : (
            <div className="space-y-2 mb-5">
              {drafts.map((draft) => (
                <button
                  key={draft.slug}
                  onClick={() => {
                    setSelectedSlug(draft.slug)
                    setForm(draft)
                    setError("")
                    setNotice("")
                  }}
                  className={`w-full rounded-lg border px-3 py-2 text-left ${
                    selectedSlug === draft.slug ? "border-blue-500 bg-blue-50" : "border-gray-200 hover:border-gray-300"
                  }`}
                >
                  <p className="text-sm font-medium text-gray-800">{draft.track_name || draft.slug}</p>
                  <p className="text-xs text-gray-500">{draft.slug}</p>
                  <p className="text-xs text-gray-500 mt-1">Status: {draft.status}</p>
                </button>
              ))}
            </div>
          )}

          <h3 className="text-sm font-semibold text-gray-700 mb-2">Published Tracks</h3>
            <div className="space-y-2">
              {tracks.map((track) => (
                <button
                  key={track.slug}
                  type="button"
                  onClick={() => {
                    setSelectedSlug(track.slug)
                    setError("")
                    setNotice("")
                  }}
                  className={`w-full rounded-lg border px-3 py-2 text-left transition-colors ${
                    selectedSlug === track.slug
                      ? "border-blue-500 bg-blue-50"
                      : "border-gray-200 hover:border-gray-300"
                  }`}
                >
                  <p className="text-sm font-medium text-gray-800">{track.label}</p>
                  <p className="text-xs text-gray-500">{track.slug}</p>
                </button>
              ))}
            </div>
          </div>

        <div className="rounded-xl border border-gray-200 p-5">
          <div className="mb-5 rounded-xl border border-blue-100 bg-blue-50/60 p-4">
            <h3 className="text-sm font-semibold text-gray-800 mb-1">
              {selectedSlug ? "Refresh Draft With New Research" : "Start From Research"}
            </h3>
            <p className="text-sm text-gray-600 mb-3">
              {selectedSlug
                ? "Paste follow-up notes or upload a file to improve the selected draft while keeping its existing structure and source history."
                : "Paste counsellor notes or upload a file to generate a first draft for this track, then edit the result before publishing."}
            </p>
            <div className="flex rounded-lg border border-blue-200 overflow-hidden text-sm mb-3">
              <button
                onClick={() => { setSourceMode("note"); setSourceFile(null) }}
                className={`flex-1 py-2 font-medium transition-colors ${sourceMode === "note" ? "bg-blue-600 text-white" : "bg-white text-gray-600 hover:bg-blue-50"}`}
                type="button"
              >
                Counsellor note
              </button>
              <button
                onClick={() => setSourceMode("file")}
                className={`flex-1 py-2 font-medium transition-colors ${sourceMode === "file" ? "bg-blue-600 text-white" : "bg-white text-gray-600 hover:bg-blue-50"}`}
                type="button"
              >
                Uploaded file
              </button>
            </div>
            {sourceMode === "note" ? (
              <textarea
                value={sourceText}
                onChange={(e) => setSourceText(e.target.value)}
                className="w-full rounded border border-gray-300 px-3 py-2 text-sm min-h-[110px] mb-3"
                placeholder={
                  selectedSlug
                    ? "Example: A recent alumni conversation suggests DBS data roles value experimentation, stakeholder communication, and SQL-heavy analytics more than deeper ML research..."
                    : "Example: After speaking to alumni, we think data science roles in Singapore value Python, SQL, experimentation, and applied ML more than pure theory..."
                }
              />
            ) : (
              <div className="mb-3 rounded border border-dashed border-gray-300 p-4">
                <input
                  type="file"
                  accept=".pdf,.docx,.txt"
                  onChange={(e) => setSourceFile(e.target.files?.[0] ?? null)}
                  className="text-sm"
                />
                {sourceFile && <p className="mt-2 text-sm text-gray-600">{sourceFile.name}</p>}
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4 mb-4">
            <label className="text-sm text-gray-700">
              Track slug
              <input
                value={form.slug}
                onChange={(e) => updateField("slug", e.target.value)}
                disabled={Boolean(selectedSlug)}
                className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm"
                placeholder="dsai"
              />
            </label>
            <label className="text-sm text-gray-700">
              Track name
              <input
                value={form.track_name}
                onChange={(e) => updateField("track_name", e.target.value)}
                className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm"
                placeholder="Data Science"
              />
            </label>
          </div>

          <label className="block text-sm text-gray-700 mb-4">
            Match description
            <textarea
              value={form.match_description}
              onChange={(e) => updateField("match_description", e.target.value)}
              className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm min-h-[84px]"
              placeholder="Describe the field in the language students and counsellors would naturally use."
            />
          </label>

          {form.source_refs.length > 0 && (
            <div className="mb-4 rounded-lg border border-gray-200 bg-gray-50 p-3">
              <p className="text-xs font-medium text-gray-500 mb-2">Source references</p>
              <div className="flex flex-wrap gap-2">
                {form.source_refs.map((ref, index) => (
                  <span
                    key={`${ref.type}-${ref.label}-${index}`}
                    className="inline-flex items-center rounded-full bg-white border border-gray-200 px-3 py-1 text-xs text-gray-700"
                  >
                    {ref.type}: {ref.label}
                  </span>
                ))}
              </div>
            </div>
          )}

          <label className="block text-sm text-gray-700 mb-4">
            Match keywords
            <input
              value={form.match_keywords.join(", ")}
              onChange={(e) => updateField("match_keywords", parseCommaList(e.target.value))}
              className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm"
              placeholder="data science, machine learning, ml engineer, analytics"
            />
          </label>

          <label className="block text-sm text-gray-700 mb-4">
            EP sponsorship guidance
            <textarea
              value={form.ep_sponsorship}
              onChange={(e) => updateField("ep_sponsorship", e.target.value)}
              className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm min-h-[84px]"
            />
          </label>

          <label className="block text-sm text-gray-700 mb-4">
            Typical COMPASS score
            <textarea
              value={form.compass_score_typical}
              onChange={(e) => updateField("compass_score_typical", e.target.value)}
              className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm min-h-[72px]"
            />
          </label>

          <div className="grid grid-cols-2 gap-4 mb-4">
            <label className="text-sm text-gray-700">
              Recruiting timeline
              <textarea
                value={form.recruiting_timeline}
                onChange={(e) => updateField("recruiting_timeline", e.target.value)}
                className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm min-h-[96px]"
              />
            </label>
            <label className="text-sm text-gray-700">
              Salary range
              <textarea
                value={form.salary_range_2024}
                onChange={(e) => updateField("salary_range_2024", e.target.value)}
                className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm min-h-[96px]"
              />
            </label>
          </div>

          <div className="grid grid-cols-2 gap-4 mb-4">
            <label className="text-sm text-gray-700">
              Example employers
              <textarea
                value={form.top_employers_smu.join("\n")}
                onChange={(e) => updateField("top_employers_smu", parseMultiLine(e.target.value))}
                className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm min-h-[120px]"
              />
            </label>
            <label className="text-sm text-gray-700">
              Entry paths
              <textarea
                value={form.entry_paths.join("\n")}
                onChange={(e) => updateField("entry_paths", parseMultiLine(e.target.value))}
                className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm min-h-[120px]"
              />
            </label>
          </div>

          <label className="block text-sm text-gray-700 mb-4">
            Typical background
            <textarea
              value={form.typical_background}
              onChange={(e) => updateField("typical_background", e.target.value)}
              className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm min-h-[96px]"
            />
          </label>

          <label className="block text-sm text-gray-700 mb-4">
            Counsellor notes
            <textarea
              value={form.notes}
              onChange={(e) => updateField("notes", e.target.value)}
              className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm min-h-[96px]"
            />
          </label>

          <div className="flex items-center justify-between pt-3 border-t border-gray-100">
            <p className="text-xs text-gray-500">
              {form.status === "ready_for_publish" ? "This draft is ready to publish." : "Complete the required fields to make this draft publish-ready."}
            </p>
            <div className="flex gap-3">
              {!selectedSlug && (
                <button
                  onClick={generateDraft}
                  disabled={
                    generating ||
                    !form.slug.trim() ||
                    !form.track_name.trim() ||
                    (sourceMode === "note" ? !sourceText.trim() : !sourceFile)
                  }
                  className="rounded-xl border border-blue-300 px-4 py-2 text-sm font-medium text-blue-700 hover:bg-blue-50 disabled:opacity-40"
                >
                  {generating ? "Generating…" : "Generate from research"}
                </button>
              )}
              {selectedSlug && (
                <button
                  onClick={refreshDraftFromResearch}
                  disabled={
                    generating ||
                    (sourceMode === "note" ? !sourceText.trim() : !sourceFile)
                  }
                  className="rounded-xl border border-blue-300 px-4 py-2 text-sm font-medium text-blue-700 hover:bg-blue-50 disabled:opacity-40"
                >
                  {generating ? "Refreshing…" : "Refresh from research"}
                </button>
              )}
              <button
                onClick={saveDraft}
                disabled={saving || generating || !form.slug || !form.track_name}
                className="rounded-xl border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-40"
              >
                {saving ? "Saving…" : "Save draft"}
              </button>
                <button
                  onClick={publishDraft}
                  disabled={publishing || generating || !selectedSlug || form.status !== "ready_for_publish"}
                  className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-40"
                >
                  {publishing ? "Publishing…" : "Publish track"}
                </button>
              </div>
            </div>
          {selectedSlug && (
            <div className="mt-5 rounded-xl border border-gray-200 p-4">
              {(form.status === "published" || form.archived_at) && (
                <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                  This is the archived working copy for a published track. The live student-facing version is shown below for reference.
                </div>
              )}
              <div className="flex items-start justify-between gap-4 mb-3">
                <div>
                  <h3 className="text-sm font-semibold text-gray-800">Published reference summary</h3>
                  <p className="text-xs text-gray-500 mt-1">
                    Last published version: {selectedPublishedTrack?.last_published || "Unknown"}
                  </p>
                </div>
                <button
                  onClick={rollbackTrack}
                  disabled={rollingBack || history.length === 0}
                  className="rounded-lg border border-gray-300 px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-40"
                >
                  {rollingBack ? "Rolling back…" : "Rollback published track"}
                </button>
              </div>
              {publishedLoading && <p className="text-sm text-gray-400">Loading published reference…</p>}
              {publishedError && <p className="text-sm text-red-600">{publishedError}</p>}
              {selectedPublishedTrack && (
                <div className="mb-4 rounded-lg border border-gray-200 bg-gray-50 p-4">
                  <p className="text-sm font-medium text-gray-800">{selectedPublishedTrack.track_name}</p>
                  <p className="mt-1 text-sm text-gray-600">{selectedPublishedTrack.match_description}</p>
                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    <div>
                      <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Key paths</p>
                      <p className="mt-1 text-sm text-gray-700">{selectedPublishedTrack.entry_paths.join(", ") || "n/a"}</p>
                    </div>
                    <div>
                      <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Typical employers</p>
                      <p className="mt-1 text-sm text-gray-700">{selectedPublishedTrack.top_employers_smu.join(", ") || "n/a"}</p>
                    </div>
                    <div>
                      <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Salary range</p>
                      <p className="mt-1 text-sm text-gray-700">{selectedPublishedTrack.salary_range_2024 || "n/a"}</p>
                    </div>
                    <div>
                      <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Timeline</p>
                      <p className="mt-1 text-sm text-gray-700">{selectedPublishedTrack.recruiting_timeline || "n/a"}</p>
                    </div>
                  </div>
                </div>
              )}
              <div className="space-y-2">
                {history.length === 0 ? (
                  <p className="text-sm text-gray-400">No published versions recorded yet.</p>
                ) : (
                  history.map((item) => (
                    <div key={item.version} className="rounded-lg border border-gray-200 px-3 py-2">
                      <p className="text-sm font-medium text-gray-800">{item.version}</p>
                      <p className="text-xs text-gray-500">{item.filename}</p>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
