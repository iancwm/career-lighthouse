"use client"
import { useEffect, useState } from "react"

const API_URL = process.env.NEXT_PUBLIC_API_URL

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
  last_updated: string | null
}

interface TrackRegistryEntry {
  slug: string
  label: string
  status: string
  last_published: string | null
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
  last_updated: null,
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

export default function TrackBuilderTab() {
  const [drafts, setDrafts] = useState<DraftTrackDetail[]>([])
  const [tracks, setTracks] = useState<TrackRegistryEntry[]>([])
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null)
  const [form, setForm] = useState<DraftTrackDetail>(EMPTY_DRAFT)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")

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
      const nextSlug = preferredSlug ?? selectedSlug ?? draftData[0]?.slug ?? null
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
    loadAll()
  }, [])

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

  function startNewDraft() {
    setSelectedSlug(null)
    setForm(EMPTY_DRAFT)
    setError("")
    setNotice("")
  }

  return (
    <div>
      <h2 className="text-lg font-semibold mb-1">Track Builder</h2>
      <p className="text-sm text-gray-500 mb-4 max-w-3xl">
        Turn counsellor research into a draft career track, review the key fields, and publish it when the guidance is ready for students.
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
              <div key={track.slug} className="rounded-lg border border-gray-200 px-3 py-2">
                <p className="text-sm font-medium text-gray-800">{track.label}</p>
                <p className="text-xs text-gray-500">{track.slug}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-gray-200 p-5">
          <div className="grid grid-cols-2 gap-4 mb-4">
            <label className="text-sm text-gray-700">
              Track slug
              <input
                value={form.slug}
                onChange={(e) => updateField("slug", e.target.value)}
                disabled={Boolean(selectedSlug)}
                className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm"
                placeholder="data_science"
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
              <button
                onClick={saveDraft}
                disabled={saving || !form.slug || !form.track_name}
                className="rounded-xl border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-40"
              >
                {saving ? "Saving…" : "Save draft"}
              </button>
              <button
                onClick={publishDraft}
                disabled={publishing || !selectedSlug || form.status !== "ready_for_publish"}
                className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-40"
              >
                {publishing ? "Publishing…" : "Publish track"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
