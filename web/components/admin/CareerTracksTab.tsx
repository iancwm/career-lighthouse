"use client"
import { useEffect, useState } from "react"

const API_URL = process.env.NEXT_PUBLIC_API_URL

interface CareerProfileMeta {
  slug: string
  career_type: string
  ep_tier: string | null
  ep_realistic: boolean | null
  salary_min_sgd: number | null
  salary_max_sgd: number | null
  compass_points_typical: string | null
  has_counselor_contact: boolean
}

interface DraftTrackDetail {
  slug: string
  track_name: string
  status: string
  last_updated: string | null
  source_refs: { type: string; label: string }[]
}

interface JournalEntry {
  ts: string
  action: string
  slug: string
  version: string
  actor?: string
  source_refs?: { type: string; label: string }[]
}

type ListState = "loading" | "loaded" | "error"

interface ProvenanceRow {
  slug: string
  trackName: string
  status: string
  lastUpdated: string | null
  sourceLabels: string
  publishedBy: string
}

function formatSalary(min: number | null, max: number | null): string {
  if (min == null && max == null) return "n/a"
  if (min != null && max != null) return `SGD ${min.toLocaleString()} - ${max.toLocaleString()}`
  if (min != null) return `>= SGD ${min.toLocaleString()}`
  return `<= SGD ${max?.toLocaleString()}`
}

function statusBadge(status: string): React.ReactNode {
  const normalised = (status || "").toLowerCase()
  if (normalised === "published") {
    return (
      <span className="inline-flex rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
        Published
      </span>
    )
  }
  if (normalised === "draft") {
    return (
      <span className="inline-flex rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
        Draft
      </span>
    )
  }
  return (
    <span className="inline-flex rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
      Archived
    </span>
  )
}

export default function CareerTracksTab() {
  const [profiles, setProfiles] = useState<CareerProfileMeta[]>([])
  const [listState, setListState] = useState<ListState>("loading")

  const [provenance, setProvenance] = useState<ProvenanceRow[]>([])
  const [provState, setProvState] = useState<ListState>("loading")

  useEffect(() => {
    setListState("loading")
    fetch(`${API_URL}/api/kb/career-profiles`)
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`)
        return r.json()
      })
      .then((data: CareerProfileMeta[]) => {
        setProfiles(data)
        setListState("loaded")
      })
      .catch(() => setListState("error"))
  }, [])

  useEffect(() => {
    setProvState("loading")
    Promise.all([
      fetch(`${API_URL}/api/kb/draft-tracks`).then((r) => {
        if (!r.ok) throw new Error(`${r.status}`)
        return r.json() as Promise<DraftTrackDetail[]>
      }),
      fetch(`${API_URL}/api/kb/publish-journal`).then((r) => {
        if (!r.ok) throw new Error(`${r.status}`)
        return r.json() as Promise<JournalEntry[]>
      }),
    ])
      .then(([drafts, journal]) => {
        // Build a lookup: slug -> latest publish_completed entry
        const latestPublish = new Map<string, JournalEntry>()
        for (const entry of journal) {
          if (entry.action === "publish_completed" && entry.slug) {
            latestPublish.set(entry.slug, entry)
          }
        }

        const rows: ProvenanceRow[] = drafts.map((draft) => {
          const journalEntry = latestPublish.get(draft.slug)
          const sourceLabels =
            draft.source_refs && draft.source_refs.length > 0
              ? draft.source_refs.map((r) => r.label).join(", ")
              : journalEntry?.source_refs && journalEntry.source_refs.length > 0
                ? journalEntry.source_refs.map((r) => r.label).join(", ")
                : "Source: unknown"
          const publishedBy = journalEntry?.actor ?? "—"
          return {
            slug: draft.slug,
            trackName: draft.track_name || draft.slug,
            status: draft.status || "draft",
            lastUpdated: draft.last_updated,
            sourceLabels,
            publishedBy,
          }
        })

        setProvenance(rows)
        setProvState("loaded")
      })
      .catch(() => setProvState("error"))
  }, [])

  if (listState === "loading") {
    return <p className="text-sm text-gray-500">Loading career tracks...</p>
  }

  if (listState === "error") {
    return (
      <div className="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
        Failed to load career tracks.
      </div>
    )
  }

  if (profiles.length === 0) {
    return <p className="text-sm text-gray-400">No career tracks found.</p>
  }

  return (
    <div className="space-y-8">
      <div>
        <div className="mb-4">
          <h2 className="text-lg font-semibold">Career Tracks</h2>
          <p className="text-sm text-gray-500">Profile coverage and structured metadata used for chat context injection.</p>
        </div>
        <div className="overflow-x-auto border border-gray-200 rounded-lg bg-white">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50 text-left text-gray-600">
              <tr>
                <th scope="col" className="px-3 py-2 font-medium">Career Type</th>
                <th scope="col" className="px-3 py-2 font-medium">Slug</th>
                <th scope="col" className="px-3 py-2 font-medium">EP Tier</th>
                <th scope="col" className="px-3 py-2 font-medium">EP Realistic</th>
                <th scope="col" className="px-3 py-2 font-medium">Salary</th>
                <th scope="col" className="px-3 py-2 font-medium">COMPASS</th>
                <th scope="col" className="px-3 py-2 font-medium">Counsellor Contact</th>
              </tr>
            </thead>
            <tbody>
              {profiles.map((profile) => (
                <tr key={profile.slug} className="border-t border-gray-100">
                  <td className="px-3 py-2 text-gray-900">{profile.career_type}</td>
                  <td className="px-3 py-2 font-mono text-xs text-gray-500">{profile.slug}</td>
                  <td className="px-3 py-2 text-gray-700">{profile.ep_tier ?? "n/a"}</td>
                  <td className="px-3 py-2 text-gray-700">{profile.ep_realistic == null ? "n/a" : profile.ep_realistic ? "yes" : "no"}</td>
                  <td className="px-3 py-2 text-gray-700">{formatSalary(profile.salary_min_sgd, profile.salary_max_sgd)}</td>
                  <td className="px-3 py-2 text-gray-700">{profile.compass_points_typical ?? "n/a"}</td>
                  <td className="px-3 py-2">
                    <span
                      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                        profile.has_counselor_contact
                          ? "bg-green-100 text-green-700"
                          : "bg-amber-100 text-amber-700"
                      }`}
                    >
                      {profile.has_counselor_contact ? "set" : "missing"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div>
        <div className="mb-4">
          <h2 className="text-lg font-semibold">Track Provenance</h2>
          <p className="text-sm text-gray-500">Source documents, last updated dates, and publishing counsellors for each career track.</p>
        </div>

        {provState === "loading" && (
          <p className="text-sm text-gray-500">Loading provenance...</p>
        )}

        {provState === "error" && (
          <div className="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            Could not load provenance.
          </div>
        )}

        {provState === "loaded" && provenance.length === 0 && (
          <div className="rounded-lg border border-gray-200 bg-[#F0E7DB] px-4 py-6 text-center">
            <p className="text-sm text-gray-700">
              No career tracks published yet.
            </p>
            <p className="mt-2 text-sm text-gray-500">
              Use Track Builder to draft and publish your first career track from research notes. Published tracks will appear here with their source attribution.
            </p>
          </div>
        )}

        {provState === "loaded" && provenance.length > 0 && (
          <div className="overflow-x-auto border border-gray-200 rounded-lg bg-white">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 text-left text-gray-600">
                <tr>
                  <th scope="col" className="px-3 py-2 font-medium">Track</th>
                  <th scope="col" className="px-3 py-2 font-medium">Status</th>
                  <th scope="col" className="px-3 py-2 font-medium">Last updated</th>
                  <th scope="col" className="px-3 py-2 font-medium">Source documents</th>
                  <th scope="col" className="px-3 py-2 font-medium">Published by</th>
                </tr>
              </thead>
              <tbody>
                {provenance.map((row) => (
                  <tr key={row.slug} className="border-t border-gray-100">
                    <td className="px-3 py-2 text-gray-900">
                      <button
                        type="button"
                        className="text-teal-700 underline hover:text-teal-900"
                        onClick={() => {
                          const url = new URL(window.location.href)
                          url.searchParams.set("view", "track-builder")
                          url.searchParams.set("slug", row.slug)
                          window.history.pushState({}, "", url.toString())
                          window.dispatchEvent(new PopStateEvent("popstate"))
                        }}
                      >
                        {row.trackName}
                      </button>
                    </td>
                    <td className="px-3 py-2">{statusBadge(row.status)}</td>
                    <td className="px-3 py-2 font-mono text-xs text-gray-500">
                      {row.lastUpdated ?? "—"}
                    </td>
                    <td
                      className="px-3 py-2 text-gray-700"
                      aria-label={row.sourceLabels === "Source: unknown" ? "Source information not available for this track" : undefined}
                    >
                      {row.sourceLabels}
                    </td>
                    <td className="px-3 py-2 text-gray-700">{row.publishedBy}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
