"use client"

/**
 * Shared loading/action status primitive: spinner + label + optional helper text.
 *
 * Variants
 *   active    — teal spinner, for trusted forward motion (default)
 *   caution   — amber spinner, for cancellable or delayed AI work
 *   on-dark   — white spinner, for use inside dark/filled buttons
 *
 * Sizes
 *   sm  — h-4 w-4 inline (default)
 *   md  — h-5 w-5 for standalone panels
 */

type Variant = "active" | "caution" | "on-dark"
type Size = "sm" | "md"

interface ActionStatusProps {
  label?: string
  helperText?: string
  variant?: Variant
  size?: Size
  className?: string
  /** Set false when the component is nested inside an existing aria-live region. */
  announce?: boolean
}

const borderColor: Record<Variant, string> = {
  active:  "border-[var(--cl-accent)] border-t-transparent",
  caution: "border-[var(--cl-warning)] border-t-transparent",
  "on-dark": "border-white border-t-transparent",
}

const labelColor: Record<Variant, string> = {
  active:  "text-[var(--cl-ink)]",
  caution: "text-[var(--cl-warning)]",
  "on-dark": "text-white",
}

const dim: Record<Size, string> = {
  sm: "h-4 w-4",
  md: "h-5 w-5",
}

export function ActionStatus({
  label,
  helperText,
  variant = "active",
  size = "sm",
  className = "",
  announce = true,
}: ActionStatusProps) {
  return (
    <span
      {...(announce ? { role: "status", "aria-live": "polite" } : {})}
      className={`inline-flex items-center gap-2 ${className}`}
    >
      <span
        aria-hidden="true"
        className={`shrink-0 rounded-full border-2 animate-spin ${dim[size]} ${borderColor[variant]}`}
      />
      {label && (
        <span className={`text-sm ${labelColor[variant]}`}>{label}</span>
      )}
      {helperText && (
        <span className="text-xs text-[var(--cl-muted)]">{helperText}</span>
      )}
    </span>
  )
}
