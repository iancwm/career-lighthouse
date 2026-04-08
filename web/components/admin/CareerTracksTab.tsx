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

type ListState = "loading" | "loaded" | "error"

function formatSalary(min: number | null, max: number | null): string {
  if (min == null && max == null) return "n/a"
  if (min != null && max != null) return `SGD ${min.toLocaleString()} - ${max.toLocaleString()}`
  if (min != null) return `>= SGD ${min.toLocaleString()}`
  return `<= SGD ${max?.toLocaleString()}`
}

export default function CareerTracksTab() {
  const [profiles, setProfiles] = useState<CareerProfileMeta[]>([])
  const [listState, setListState] = useState<ListState>("loading")

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
    <div>
      <div className="mb-4">
        <h2 className="text-lg font-semibold">Career Tracks</h2>
        <p className="text-sm text-gray-500">Profile coverage and structured metadata used for chat context injection.</p>
      </div>
      <div className="overflow-x-auto border border-gray-200 rounded-lg bg-white">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 text-left text-gray-600">
            <tr>
              <th className="px-3 py-2 font-medium">Career Type</th>
              <th className="px-3 py-2 font-medium">Slug</th>
              <th className="px-3 py-2 font-medium">EP Tier</th>
              <th className="px-3 py-2 font-medium">EP Realistic</th>
              <th className="px-3 py-2 font-medium">Salary</th>
              <th className="px-3 py-2 font-medium">COMPASS</th>
              <th className="px-3 py-2 font-medium">Counsellor Contact</th>
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
  )
}
