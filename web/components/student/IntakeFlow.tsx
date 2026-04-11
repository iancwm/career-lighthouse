"use client"
import { useState, useEffect } from "react"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

export interface IntakeContext {
  background: string | null
  region: string | null
  interest: string | null
}

interface Props {
  onComplete: (ctx: IntakeContext) => void
  onBack: () => void
}

const BACKGROUNDS = [
  { id: "undergrad", label: "Undergrad" },
  { id: "masters", label: "Pre-exp Masters" },
  { id: "professional", label: "Working professional" },
]

const REGIONS = [
  { id: "sea", label: "Southeast Asia" },
  { id: "south_asia", label: "South Asia" },
  { id: "east_asia", label: "East Asia" },
  { id: "other", label: "Other" },
]

function PillGroup({
  options,
  selected,
  onSelect,
}: {
  options: { id: string; label: string }[]
  selected: string | null
  onSelect: (id: string) => void
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((opt) => (
        <button
          key={opt.id}
          onClick={() => onSelect(opt.id)}
          className={`px-3 py-2.5 rounded-full text-sm border transition-colors focus:outline-none focus:ring-2 focus:ring-blue-400 ${
            selected === opt.id
              ? "bg-blue-600 text-white border-blue-600"
              : "bg-white text-gray-700 border-gray-300 hover:border-blue-400"
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}

export default function IntakeFlow({ onComplete, onBack }: Props) {
  const [background, setBackground] = useState<string | null>(null)
  const [region, setRegion] = useState<string | null>(null)
  const [interest, setInterest] = useState<string | null>(null)
  const [interests, setInterests] = useState<{ id: string; label: string }[]>([])

  useEffect(() => {
    async function loadTracks() {
      try {
        const res = await fetch(`${API_URL}/api/tracks/active`)
        if (res.ok) {
          const data = await res.json()
          const options = data.map((t: any) => ({
            id: t.slug,
            label: t.label
          }))
          options.push({ id: "not_sure", label: "Not sure yet" })
          setInterests(options)
        }
      } catch (err) {
        console.error("Failed to load tracks", err)
        // Fallback to minimal static list if API is down
        setInterests([
          { id: "finance", label: "Finance / Banking" },
          { id: "consulting", label: "Consulting" },
          { id: "tech", label: "Tech / Product" },
          { id: "not_sure", label: "Not sure yet" },
        ])
      }
    }
    loadTracks()
  }, [])

  function handleSubmit() {
    onComplete({ background, region, interest })
  }

  return (
    <div className="flex flex-col py-6 space-y-6 max-w-lg mx-auto">
      <button
        onClick={onBack}
        className="self-start text-sm text-gray-400 hover:text-gray-600 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400 rounded"
      >
        ← Back
      </button>

      <div>
        <p className="text-sm font-medium text-gray-700 mb-2">Your background</p>
        <PillGroup options={BACKGROUNDS} selected={background} onSelect={setBackground} />
      </div>

      <div>
        <p className="text-sm font-medium text-gray-700 mb-2">Where you're from</p>
        <PillGroup options={REGIONS} selected={region} onSelect={setRegion} />
      </div>

      <div>
        <p className="text-sm font-medium text-gray-700 mb-2">What you're interested in</p>
        <PillGroup options={interests} selected={interest} onSelect={setInterest} />
      </div>

      <button
        onClick={handleSubmit}
        disabled={!interest}
        className="w-full py-3 bg-blue-600 text-white rounded-xl text-sm font-medium disabled:opacity-40 hover:bg-blue-700 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-400"
      >
        Let's go →
      </button>
    </div>
  )
}
