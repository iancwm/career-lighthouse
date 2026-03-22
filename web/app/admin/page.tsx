"use client"
import { useState } from "react"
import KnowledgeUpload from "@/components/admin/KnowledgeUpload"
import DocList from "@/components/admin/DocList"
import BriefGenerator from "@/components/admin/BriefGenerator"

export default function AdminPage() {
  const [refreshKey, setRefreshKey] = useState(0)
  return (
    <div className="max-w-6xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-1">Career Lighthouse</h1>
      <p className="text-sm text-gray-500 mb-8">Career Office Dashboard</p>
      <div className="grid grid-cols-2 gap-8">
        <div>
          <KnowledgeUpload onUploaded={() => setRefreshKey(k => k + 1)} />
          <DocList refreshKey={refreshKey} />
        </div>
        <div>
          <BriefGenerator />
        </div>
      </div>
    </div>
  )
}
