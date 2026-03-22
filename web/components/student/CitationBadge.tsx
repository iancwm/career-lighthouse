interface Props { filename: string; excerpt: string }

export default function CitationBadge({ filename, excerpt }: Props) {
  return (
    <span title={excerpt} className="inline-block text-xs bg-blue-50 border border-blue-200 text-blue-700 rounded px-2 py-0.5 mr-1 cursor-help">
      {filename}
    </span>
  )
}
