"use client"
import { useEffect, useState } from "react"
import KnowledgeUpload from "@/components/admin/KnowledgeUpload"
import DocList from "@/components/admin/DocList"
import BriefGenerator from "@/components/admin/BriefGenerator"
import StatCards from "@/components/admin/StatCards"
import TestQueryBox from "@/components/admin/TestQueryBox"
import DocCoverageList from "@/components/admin/DocCoverageList"
import LowConfidenceLog from "@/components/admin/LowConfidenceLog"
import RedundancyPanel from "@/components/admin/RedundancyPanel"
import KnowledgeUpdateTab from "@/components/admin/KnowledgeUpdateTab"

interface KBHealth {
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

type Tab = "knowledge" | "update"

export default function AdminPage() {
  const [tab, setTab] = useState<Tab>("knowledge")
  const [refreshKey, setRefreshKey] = useState(0)
  const [health, setHealth] = useState<KBHealth | null>(null)
  const [healthError, setHealthError] = useState(false)
  const apiUrl = process.env.NEXT_PUBLIC_API_URL

  function fetchHealth() {
    setHealthError(false)
    fetch(`${apiUrl}/api/kb/health`)
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`)
        return r.json()
      })
      .then(setHealth)
      .catch(() => setHealthError(true))
  }

  useEffect(() => {
    fetchHealth()
  }, [refreshKey])

  return (
    <div className="max-w-6xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-1">Career Lighthouse</h1>
      <p className="text-sm text-gray-500 mb-6">Career Office Dashboard</p>

      {/* Tab nav */}
      <div className="flex gap-1 mb-8 border-b border-gray-200">
        <TabButton active={tab === "knowledge"} onClick={() => setTab("knowledge")}>
          Knowledge Base
        </TabButton>
        <TabButton active={tab === "update"} onClick={() => setTab("update")}>
          Update Knowledge
        </TabButton>
      </div>

      {/* Knowledge Base tab */}
      {tab === "knowledge" && (
        <>
          <div className="grid grid-cols-2 gap-8">
            <div>
              <KnowledgeUpload onUploaded={() => setRefreshKey((k) => k + 1)} />
              <DocList refreshKey={refreshKey} onDeleted={fetchHealth} />
            </div>
            <div>
              <BriefGenerator />
            </div>
          </div>

          <div className="mt-12">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">KB Health</h2>
              <button
                onClick={fetchHealth}
                className="text-xs text-blue-600 hover:text-blue-800"
              >
                Refresh
              </button>
            </div>

            {healthError && (
              <div className="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 mb-4">
                Knowledge base unavailable — check that Qdrant is running.
              </div>
            )}

            {health && (
              <>
                <StatCards
                  totalDocs={health.total_docs}
                  totalChunks={health.total_chunks}
                  lowConfidenceCount={health.low_confidence_queries.length}
                  avgMatchScore={health.avg_match_score}
                  diversityScore={health.retrieval_diversity_score}
                />

                <TestQueryBox apiUrl={apiUrl} />

                <div className="grid grid-cols-2 gap-8 mt-4">
                  <DocCoverageList docs={health.doc_coverage} />
                  <LowConfidenceLog
                    avgMatchScore={health.avg_match_score}
                    queries={health.low_confidence_queries}
                  />
                </div>

                {health.high_overlap_pairs.length > 0 && (
                  <div className="mt-6">
                    <RedundancyPanel pairs={health.high_overlap_pairs} />
                  </div>
                )}
              </>
            )}
          </div>
        </>
      )}

      {/* Update Knowledge tab */}
      {tab === "update" && (
        <KnowledgeUpdateTab onCommitted={() => setRefreshKey((k) => k + 1)} />
      )}
    </div>
  )
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-400 rounded-t -mb-px ${
        active
          ? "border-blue-600 text-blue-600"
          : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
      }`}
    >
      {children}
    </button>
  )
}
