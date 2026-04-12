"use client"
import { useEffect, useState } from "react"

const API_URL = process.env.NEXT_PUBLIC_API_URL

interface BrokenProfile {
  slug: string
  filename: string
  missing_fields: string[]
  has_career_type: boolean
  existing_fields: string[]
}

export default function BrokenProfilesTab() {
  const [broken, setBroken] = useState<BrokenProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [autocompleting, setAutocompleting] = useState<string | null>(null)
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")

  async function loadBroken() {
    try {
      const res = await fetch(`${API_URL}/api/kb/career-profiles/broken`)
      if (!res.ok) throw new Error("failed")
      const data: BrokenProfile[] = await res.json()
      setBroken(data)
    } catch {
      setError("Could not load broken profiles.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadBroken() }, [])

  async function handleAutoComplete(slug: string) {
    setAutocompleting(slug)
    setError("")
    setNotice("")
    try {
      const res = await fetch(`${API_URL}/api/kb/career-profiles/${slug}/auto-complete`, {
        method: "POST",
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || "Auto-complete failed")
      }
      const data = await res.json()
      setNotice(`✓ ${slug}: filled ${data.completed_fields.length} field(s): ${data.completed_fields.join(", ")}. Profile is now active.`)
      await loadBroken()
    } catch (err: any) {
      setError(err.message || "Could not auto-complete profile.")
    } finally {
      setAutocompleting(null)
    }
  }

  if (loading) return <p className="text-sm text-gray-400">Checking profiles…</p>

  if (broken.length === 0) {
    return (
      <div className="rounded-xl border border-green-200 bg-green-50 p-6 text-center">
        <p className="text-lg font-semibold text-green-700">All profiles healthy</p>
        <p className="text-sm text-green-600 mt-1">No broken career profiles detected.</p>
      </div>
    )
  }

  return (
    <div>
      <div className="mb-4 rounded-lg bg-[#F6F1E8] border border-[#D8D0C4] px-4 py-3 text-sm text-[#5F6B76]">
        <span className="font-medium text-[#1F2937]">⚠ Broken profiles detected</span>{" "}
        These files are on disk but could not be loaded due to missing required fields.
        Click "Auto-complete with AI" to fill in the missing fields automatically.
      </div>

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

      <div className="space-y-4">
        {broken.map((bp) => (
          <div key={bp.slug} className="rounded-xl border border-red-200 bg-red-50/50 p-4">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <h3 className="text-sm font-semibold text-red-800">
                  {bp.has_career_type ? bp.slug : <span className="text-gray-400 italic">(no career_type)</span>}
                </h3>
                <p className="text-xs text-gray-500 mt-0.5 font-mono">{bp.filename}</p>
                <div className="mt-2">
                  <p className="text-xs font-medium text-red-700 mb-1">Missing fields:</p>
                  <div className="flex flex-wrap gap-1">
                    {bp.missing_fields.map((f) => (
                      <span key={f} className="inline-block rounded bg-red-100 text-red-700 px-2 py-0.5 text-xs font-mono">
                        {f}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="mt-2">
                  <p className="text-xs font-medium text-gray-500 mb-1">
                    Existing fields ({bp.existing_fields.length}):
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {bp.existing_fields.map((f) => (
                      <span key={f} className="inline-block rounded bg-gray-100 text-gray-600 px-2 py-0.5 text-xs font-mono">
                        {f}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
              <button
                onClick={() => handleAutoComplete(bp.slug)}
                disabled={autocompleting !== null}
                className="shrink-0 rounded-lg bg-[#0F766E] px-4 py-2 text-sm font-medium text-white hover:bg-[#0A5C57] disabled:opacity-40 transition-colors"
                style={{ minHeight: "44px" }}
              >
                {autocompleting === bp.slug ? "Completing…" : "Auto-complete with AI"}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
