"use client"

import { useEffect, useRef, useCallback } from "react"

export type DrawerSurface = "knowledge" | "update" | "careers" | "employers" | "tracks" | "resume"

interface ToolsDrawerProps {
  open: boolean
  activeSurface: DrawerSurface | null
  onToggle: () => void
  onNavigate: (view: DrawerSurface) => void
  toggleButtonRef: React.RefObject<HTMLButtonElement | null>
}

const DRAWER_ITEMS: { id: DrawerSurface; label: string; description: string }[] = [
  { id: "knowledge", label: "Documents", description: "Upload, inspect, and measure the KB." },
  { id: "update", label: "Review Updates", description: "Turn notes into reviewed changes." },
  { id: "resume", label: "Resume Review", description: "Generate prep briefs from student resumes." },
  { id: "employers", label: "Employer Facts", description: "Maintain employer-specific facts." },
  { id: "tracks", label: "Track Builder", description: "Draft, publish, and rollback career tracks." },
  { id: "careers", label: "Career Tracks", description: "See structured chat metadata." },
]

export default function ToolsDrawer({ open, activeSurface, onToggle, onNavigate, toggleButtonRef }: ToolsDrawerProps) {
  const drawerRef = useRef<HTMLDivElement>(null)
  const firstCardRef = useRef<HTMLButtonElement>(null)

  // Focus management: on open, focus first card
  useEffect(() => {
    if (open && firstCardRef.current) {
      firstCardRef.current.focus()
    }
  }, [open])

  // Escape key closes drawer
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape" && open) {
        e.preventDefault()
        onToggle()
        // Return focus to toggle button
        setTimeout(() => toggleButtonRef.current?.focus(), 0)
      }
    },
    [open, onToggle, toggleButtonRef]
  )

  useEffect(() => {
    if (open) {
      document.addEventListener("keydown", handleKeyDown)
      return () => document.removeEventListener("keydown", handleKeyDown)
    }
  }, [open, handleKeyDown])

  if (!open) return null

  return (
    <div
      ref={drawerRef}
      role="region"
      aria-label="Knowledge management tools"
      className="relative mb-6"
    >
      <div className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-4 shadow-[0_12px_30px_rgba(31,41,55,0.06)]">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {DRAWER_ITEMS.map((item, index) => {
            const isActive = activeSurface === item.id
            return (
              <button
                key={item.id}
                ref={index === 0 ? firstCardRef : undefined}
                type="button"
                onClick={() => onNavigate(item.id)}
                className={`group flex flex-col items-start rounded-xl border px-4 py-3 text-left transition-colors ${
                  isActive
                    ? "border-l-[3px] border-l-[var(--cl-accent)] border-[var(--cl-line)] bg-[var(--cl-surface-2)]"
                    : "border-[var(--cl-line)] bg-[var(--cl-surface)] hover:bg-[var(--cl-surface-2)]"
                }`}
              >
                <span className="font-display text-[var(--cl-ink)]" style={{ fontSize: "22px", lineHeight: "1.15" }}>
                  {item.label}
                </span>
                <span className="mt-1 text-sm text-[var(--cl-muted)]" style={{ fontSize: "14px", lineHeight: "1.5" }}>
                  {item.description}
                </span>
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
