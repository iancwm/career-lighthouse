"use client"
import { useState } from "react"
import { Fact, FactType, FactSource } from "@/types/facts"

interface FactEditorProps {
  onAdd: (fact: Fact) => void
  onCancel?: () => void
  existingSlugs?: string[]
}

// ── Field schema per fact type ────────────────────────────────────

const fieldSchemas: Record<FactType, Array<{
  name: string
  label: string
  type: "text" | "number" | "select" | "checkbox" | "chips"
  required?: boolean
  options?: { value: string; label: string }[]
  placeholder?: string
}>> = {
  timeline_phase: [
    { name: "phase_name", label: "Phase name", type: "text", required: true, placeholder: "e.g., Summer internship application" },
    { name: "value", label: "Date or window", type: "text", required: true, placeholder: "e.g., June 1 – August 31" },
    { name: "role_type", label: "Role type", type: "select", required: true, options: [
      { value: "summer_internship", label: "Summer internship" },
      { value: "full_time", label: "Full-time" },
      { value: "winter_internship", label: "Winter internship" },
      { value: "grad_scheme", label: "Graduate scheme" },
      { value: "entry_level", label: "Entry-level" },
    ] },
    { name: "duration_days", label: "Duration (days)", type: "number", placeholder: "e.g., 92" },
  ],
  alumni: [
    { name: "name", label: "Name", type: "text", required: true, placeholder: "e.g., Aditya Mehta" },
    { name: "degree", label: "Degree", type: "text", placeholder: "e.g., LLM" },
    { name: "school", label: "School/University", type: "text", placeholder: "e.g., NUS" },
    { name: "graduation_year", label: "Graduation year", type: "number", placeholder: "e.g., 2018" },
    { name: "current_company", label: "Current company", type: "text", placeholder: "e.g., Stripe Singapore" },
    { name: "current_title", label: "Current title", type: "text", placeholder: "e.g., Head of Compliance" },
    { name: "joined_year", label: "Joined company year", type: "number", placeholder: "e.g., 2020" },
    { name: "available_for_mentoring", label: "Available for mentoring?", type: "checkbox" },
  ],
  interview_stage: [
    { name: "order", label: "Stage order", type: "number", required: true, placeholder: "e.g., 1" },
    { name: "name", label: "Stage name", type: "text", required: true, placeholder: "e.g., HR screening" },
    { name: "format", label: "Format", type: "select", required: true, options: [
      { value: "phone_call", label: "Phone call" },
      { value: "video_interview", label: "Video interview" },
      { value: "technical_assessment", label: "Technical assessment" },
      { value: "in_person", label: "In-person" },
      { value: "group", label: "Group interview" },
      { value: "case_study", label: "Case study" },
    ] },
    { name: "duration_minutes", label: "Duration (minutes)", type: "number", placeholder: "e.g., 30" },
    { name: "focus", label: "Focus areas", type: "chips", placeholder: "e.g., behavioral, technical" },
    { name: "typical_advance_rate", label: "Advance rate (%)", type: "number", placeholder: "e.g., 75" },
  ],
  compensation: [
    { name: "role_level", label: "Role level", type: "text", required: true, placeholder: "e.g., Junior Analyst" },
    { name: "currency", label: "Currency", type: "text", placeholder: "SGD" },
    { name: "base_salary_min", label: "Base salary min", type: "number", placeholder: "e.g., 80000" },
    { name: "base_salary_max", label: "Base salary max", type: "number", placeholder: "e.g., 110000" },
    { name: "bonus_range", label: "Bonus range", type: "text", placeholder: "e.g., 15-20%" },
    { name: "equity", label: "Offers equity?", type: "checkbox" },
  ],
  skill_requirement: [
    { name: "focus", label: "Technical focus areas", type: "chips", placeholder: "e.g., Python, data analysis" },
    { name: "preferred_background", label: "Preferred background", type: "chips", placeholder: "e.g., statistics, CS" },
  ],
}

// ── Sub-components ────────────────────────────────────────────────

function ChipInputField({ value, onChange, placeholder }: { value: string[]; onChange: (v: string[]) => void; placeholder?: string }) {
  const [inputVal, setInputVal] = useState("")

  function addChip(raw: string) {
    const tag = raw.trim()
    if (tag && !value.includes(tag)) {
      onChange([...value, tag])
    }
    setInputVal("")
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault()
      addChip(inputVal)
    } else if (e.key === "Backspace" && inputVal === "" && value.length > 0) {
      onChange(value.slice(0, -1))
    }
  }

  return (
    <div className="flex flex-wrap gap-1.5 rounded-lg border border-gray-300 px-2.5 py-2 focus-within:ring-2 focus-within:ring-blue-400 min-h-[40px] bg-white">
      {value.map((v) => (
        <span key={v} className="inline-flex items-center gap-1 rounded-full bg-blue-100 text-blue-700 text-xs px-2 py-0.5">
          {v}
          <button
            type="button"
            onClick={() => onChange(value.filter((x) => x !== v))}
            className="hover:text-blue-900 leading-none"
            aria-label={`Remove ${v}`}
          >
            ×
          </button>
        </span>
      ))}
      <input
        className="flex-1 min-w-[80px] text-sm outline-none bg-transparent placeholder-gray-400"
        value={inputVal}
        onChange={(e) => setInputVal(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={() => { if (inputVal.trim()) addChip(inputVal) }}
        placeholder={value.length === 0 ? placeholder : ""}
      />
    </div>
  )
}

function generateSlug(type: FactType, data: Record<string, unknown>, employerSlug: string): string {
  let keyField = ""
  switch (type) {
    case "alumni":
      keyField = data.name ? String(data.name).toLowerCase().replace(/\s+/g, "-") : "alumni"
      break
    case "timeline_phase":
      keyField = data.phase_name ? String(data.phase_name).toLowerCase().replace(/\s+/g, "-") : "phase"
      break
    case "interview_stage":
      keyField = data.name ? String(data.name).toLowerCase().replace(/\s+/g, "-") : `stage-${data.order || 1}`
      break
    case "compensation":
      keyField = data.role_level ? String(data.role_level).toLowerCase().replace(/\s+/g, "-") : "compensation"
      break
    case "skill_requirement":
      keyField = "skills"
      break
    default:
      keyField = "fact"
  }
  return `${employerSlug}-${keyField}`
}

// ── Main component ────────────────────────────────────────────────

export default function FactEditor({ onAdd, onCancel, existingSlugs = [] }: FactEditorProps) {
  const [type, setType] = useState<FactType>("alumni")
  const [data, setData] = useState<Record<string, unknown>>({})
  const [source, setSource] = useState<FactSource>("counselor")
  const [confidence, setConfidence] = useState(85)
  const [error, setError] = useState("")

  const fields = fieldSchemas[type]

  function updateData(field: string, value: unknown) {
    setData((prev) => ({ ...prev, [field]: value }))
    setError("")
  }

  function handleAdd() {
    const requiredFields = fields.filter((f) => f.required)
    const missing = requiredFields.filter((f) => !data[f.name])

    if (missing.length > 0) {
      setError(`Missing required fields: ${missing.map((f) => f.label).join(", ")}`)
      return
    }

    // Generate slug (simplified; no collision handling yet)
    const baseSlug = generateSlug(type, data, "temp")
    let slug = baseSlug
    if (existingSlugs.includes(slug)) {
      const today = new Date().toISOString().split("T")[0].replace(/-/g, "")
      slug = `${baseSlug}-${today}`
    }

    const now = new Date().toISOString()

    const newFact: Fact = {
      slug,
      type,
      data,
      confidence,
      source,
      timestamp: now,
      lifecycle: "active",
      last_updated: now,
      source_timestamp: now,
    }

    onAdd(newFact)
    setData({})
    setType("alumni")
    setSource("counselor")
    setConfidence(85)
  }

  return (
    <div className="space-y-4 p-4 border-t border-gray-200 bg-gray-50 rounded-lg">
      <h4 className="text-sm font-semibold text-gray-700">New fact</h4>

      {/* Type selector */}
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-2">Fact type</label>
        <div className="flex flex-wrap gap-2">
          {(["alumni", "timeline_phase", "interview_stage", "compensation", "skill_requirement"] as FactType[]).map((t) => (
            <label key={t} className="flex items-center gap-1.5 cursor-pointer">
              <input
                type="radio"
                name="type"
                value={t}
                checked={type === t}
                onChange={(e) => { setType(e.target.value as FactType); setData({}); setError("") }}
                className="w-4 h-4"
              />
              <span className="text-xs text-gray-700">{t.replace(/_/g, " ")}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Type-specific fields */}
      <div className="space-y-3">
        {fields.map((field) => {
          const fieldValue = data[field.name]

          if (field.type === "text") {
            return (
              <div key={field.name}>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  {field.label}
                  {field.required && <span className="text-red-500"> *</span>}
                </label>
                <input
                  type="text"
                  value={fieldValue as string || ""}
                  onChange={(e) => updateData(field.name, e.target.value)}
                  placeholder={field.placeholder}
                  className="w-full rounded border border-gray-300 px-2.5 py-1.5 text-sm outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent"
                />
              </div>
            )
          }

          if (field.type === "number") {
            return (
              <div key={field.name}>
                <label className="block text-xs font-medium text-gray-600 mb-1">{field.label}</label>
                <input
                  type="number"
                  value={fieldValue as number || ""}
                  onChange={(e) => updateData(field.name, e.target.value ? parseInt(e.target.value, 10) : "")}
                  placeholder={field.placeholder}
                  className="w-full rounded border border-gray-300 px-2.5 py-1.5 text-sm outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent"
                />
              </div>
            )
          }

          if (field.type === "checkbox") {
            return (
              <div key={field.name} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id={field.name}
                  checked={Boolean(fieldValue)}
                  onChange={(e) => updateData(field.name, e.target.checked)}
                  className="w-4 h-4"
                />
                <label htmlFor={field.name} className="text-xs text-gray-700 cursor-pointer">{field.label}</label>
              </div>
            )
          }

          if (field.type === "select") {
            return (
              <div key={field.name}>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  {field.label}
                  {field.required && <span className="text-red-500"> *</span>}
                </label>
                <select
                  value={fieldValue as string || ""}
                  onChange={(e) => updateData(field.name, e.target.value)}
                  className="w-full rounded border border-gray-300 px-2.5 py-1.5 text-sm outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent bg-white"
                >
                  <option value="">Select {field.label}...</option>
                  {field.options?.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>
            )
          }

          if (field.type === "chips") {
            return (
              <div key={field.name}>
                <label className="block text-xs font-medium text-gray-600 mb-1">{field.label}</label>
                <ChipInputField
                  value={(fieldValue as string[]) || []}
                  onChange={(v) => updateData(field.name, v)}
                  placeholder={field.placeholder}
                />
              </div>
            )
          }

          return null
        })}
      </div>

      {/* Common fields: source + confidence */}
      <div className="grid grid-cols-2 gap-3 pt-3 border-t border-gray-200">
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Source</label>
          <select
            value={source}
            onChange={(e) => setSource(e.target.value as SourceType)}
            className="w-full rounded border border-gray-300 px-2.5 py-1.5 text-sm outline-none focus:ring-2 focus:ring-blue-400 bg-white"
          >
            <option value="counselor">Counselor</option>
            <option value="inferred">Inferred</option>
            <option value="direct_from_alumni">Direct from alumni</option>
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Confidence: {confidence}%</label>
          <input
            type="range"
            min="1"
            max="100"
            value={confidence}
            onChange={(e) => setConfidence(parseInt(e.target.value, 10))}
            className="w-full h-2 bg-gray-300 rounded-lg appearance-none cursor-pointer"
          />
        </div>
      </div>

      {/* Error message */}
      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-2.5 text-xs text-red-700">
          {error}
        </div>
      )}

      {/* Action buttons */}
      <div className="flex gap-2 justify-end pt-2">
        {onCancel && (
          <button
            onClick={onCancel}
            className="px-3 py-1.5 rounded-lg border border-gray-300 text-sm text-gray-600 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-400"
          >
            Cancel
          </button>
        )}
        <button
          onClick={handleAdd}
          className="px-3 py-1.5 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-400"
        >
          Add fact
        </button>
      </div>
    </div>
  )
}
