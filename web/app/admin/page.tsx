import { Suspense } from "react"
import AdminWorkspace from "@/components/admin/AdminWorkspace"

export default function AdminPage() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:px-8">Loading admin workspace…</div>}>
      <AdminWorkspace />
    </Suspense>
  )
}
