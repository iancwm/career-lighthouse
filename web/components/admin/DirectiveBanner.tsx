interface DirectiveBannerProps {
  label: string
  whatYouDo: string
  whatHappens: string
}

export default function DirectiveBanner({ label, whatYouDo, whatHappens }: DirectiveBannerProps) {
  return (
    <div
      role="region"
      aria-labelledby="directive-banner-label"
      className="mb-4 rounded-r-[8px] border-l-4 border-[var(--cl-accent)] bg-[var(--cl-surface-2)] px-4 py-2.5"
    >
      <h2 id="directive-banner-label" className="sr-only">
        {label}
      </h2>
      <p className="text-sm font-semibold text-[var(--cl-ink)]">{label}</p>
      <p className="mt-0.5 text-xs text-[var(--cl-muted)]">
        {whatYouDo}
      </p>
    </div>
  )
}
