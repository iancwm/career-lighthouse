"use client"

interface Props {
  onOptionSelected: (option: string) => void
  onSkip: () => void
}

const OPTIONS = [
  {
    id: "explore",
    label: "I don't know where to start",
    description: "Help me figure out what's realistic for me",
  },
  {
    id: "specific",
    label: "Exploring a specific career",
    description: "I have a track in mind and want to learn more",
  },
  {
    id: "market",
    label: "Understanding Singapore",
    description: "How does the job market work here?",
  },
  {
    id: "interview",
    label: "I have an interview",
    description: "Help me prepare for an upcoming interview",
  },
]

export default function GuidedEntry({ onOptionSelected, onSkip }: Props) {
  return (
    <div className="flex flex-col items-center py-8">
      <h2 className="text-lg font-semibold text-gray-800 mb-1">Where would you like to start?</h2>
      <p className="text-sm text-gray-500 mb-6">We'll tailor the conversation to what's most useful for you.</p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-lg">
        {OPTIONS.map((opt) => (
          <button
            key={opt.id}
            onClick={() => onOptionSelected(opt.id)}
            className="flex flex-col items-start text-left p-4 border border-gray-200 rounded-xl hover:border-blue-400 hover:bg-blue-50 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-400"
          >
            <span className="text-sm font-medium text-gray-800 mb-1">{opt.label}</span>
            <span className="text-xs text-gray-500">{opt.description}</span>
          </button>
        ))}
      </div>

      <button
        onClick={onSkip}
        className="mt-5 text-sm text-gray-400 hover:text-gray-600 underline underline-offset-2 py-2 px-2 focus:outline-none focus:ring-2 focus:ring-blue-400 rounded"
      >
        or just chat →
      </button>
    </div>
  )
}
