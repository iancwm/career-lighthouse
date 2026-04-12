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
      className="mb-6 rounded-r-[8px] border-l-4 border-[#0F766E] bg-[#F0E7DB] px-4 py-3"
    >
      <h2 id="directive-banner-label" className="sr-only">
        {label}
      </h2>
      <p className="mb-2 text-sm font-bold text-[#1F2937]" style={{ fontFamily: "'Instrument Sans', sans-serif" }}>
        {label}
      </p>
      <div className="space-y-1.5">
        <p className="text-sm">
          <span className="font-semibold text-[#1F2937]">What you do: </span>
          <span className="text-[#5F6B76]">{whatYouDo}</span>
        </p>
        <p className="text-sm">
          <span className="font-semibold text-[#1F2937]">What happens: </span>
          <span className="text-[#5F6B76]">{whatHappens}</span>
        </p>
      </div>
    </div>
  )
}
