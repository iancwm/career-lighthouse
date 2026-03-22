"use client"
import { useState } from "react"

interface Props { onResume: (text: string) => void; hasResume: boolean }

export default function ResumeUpload({ onResume, hasResume }: Props) {
  const [text, setText] = useState("")
  const [mode, setMode] = useState<"idle" | "paste">("idle")

  function handlePaste() {
    if (text.trim()) { onResume(text.trim()); setMode("idle") }
  }

  if (hasResume) return (
    <div className="flex items-center gap-2 text-sm text-green-700 bg-green-50 border border-green-200 rounded px-3 py-2">
      Resume loaded — advice is personalized
      <button onClick={() => onResume("")} className="ml-auto text-xs text-gray-400 hover:text-gray-600">Clear</button>
    </div>
  )

  return (
    <div className="text-sm">
      {mode === "idle" ? (
        <div className="flex items-center gap-3">
          <button onClick={() => setMode("paste")} className="px-3 py-1.5 border rounded text-blue-600 hover:bg-blue-50">
            + Add resume for personalized advice
          </button>
          <span className="text-gray-400">or skip for general advice</span>
        </div>
      ) : (
        <div>
          <textarea value={text} onChange={e => setText(e.target.value)}
            placeholder="Paste your resume text…"
            className="w-full h-32 border rounded p-2 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-blue-400" />
          <div className="mt-1 flex gap-2">
            <button onClick={handlePaste} className="px-3 py-1.5 bg-blue-600 text-white rounded text-xs">Use this resume</button>
            <button onClick={() => setMode("idle")} className="px-3 py-1.5 text-gray-500 text-xs">Cancel</button>
          </div>
        </div>
      )}
    </div>
  )
}
