import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { vi } from "vitest"
import AdminWorkspace from "../AdminWorkspace"

let currentQuery = ""
const replace = vi.fn()
const push = vi.fn()

vi.mock("next/navigation", () => ({
  usePathname: () => "/admin",
  useRouter: () => ({ replace, push }),
  useSearchParams: () => new URLSearchParams(currentQuery),
}))

vi.mock("@/components/admin/KnowledgeUpload", () => ({ default: () => <div>knowledge-upload</div> }))
vi.mock("@/components/admin/DocList", () => ({ default: () => <div>doc-list</div> }))
vi.mock("@/components/admin/BriefGenerator", () => ({ default: () => <div>brief-generator</div> }))
vi.mock("@/components/admin/StatCards", () => ({ default: () => <div>stat-cards</div> }))
vi.mock("@/components/admin/TestQueryBox", () => ({ default: () => <div>test-query-box</div> }))
vi.mock("@/components/admin/DocCoverageList", () => ({ default: () => <div>doc-coverage</div> }))
vi.mock("@/components/admin/LowConfidenceLog", () => ({ default: () => <div>low-confidence</div> }))
vi.mock("@/components/admin/RedundancyPanel", () => ({ default: () => <div>redundancy-panel</div> }))
vi.mock("@/components/admin/KnowledgeUpdateTab", () => ({ default: () => <div>knowledge-update-tab</div> }))
vi.mock("@/components/admin/EmployerFactsTab", () => ({ default: () => <div>employer-facts-tab</div> }))
vi.mock("@/components/admin/CareerTracksTab", () => ({ default: () => <div>career-tracks-tab</div> }))
vi.mock("@/components/admin/SessionInbox", () => ({
  default: ({ onSelectSession }: { onSelectSession: (sessionId: string) => void }) => (
    <button type="button" onClick={() => onSelectSession("session-1")}>
      open session
    </button>
  ),
}))
vi.mock("@/components/admin/SmartCanvas", () => ({
  default: ({ onBack }: { onBack: () => void }) => (
    <button type="button" onClick={onBack}>
      back to inbox
    </button>
  ),
}))
vi.mock("@/components/admin/TrackBuilderTab", () => ({
  default: ({
    selectedSlug,
    onSelectedSlugChange,
  }: {
    selectedSlug?: string | null
    onSelectedSlugChange?: (slug: string | null) => void
  }) => (
    <div>
      <p>track-builder:{selectedSlug ?? "none"}</p>
      <button type="button" onClick={() => onSelectedSlugChange?.("dsai")}>
        pick track
      </button>
    </div>
  ),
}))

describe("AdminWorkspace", () => {
  beforeEach(() => {
    currentQuery = ""
    replace.mockReset()
    push.mockReset()
    process.env.NEXT_PUBLIC_API_URL = "http://test"
    vi.stubGlobal("fetch", vi.fn())
  })

  it("defaults to sessions and normalizes the URL", async () => {
    render(<AdminWorkspace />)

    expect(screen.getByRole("button", { name: /open session/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /session editor/i })).toBeInTheDocument()

    await waitFor(() =>
      expect(replace).toHaveBeenCalledWith("/admin?view=sessions", { scroll: false })
    )
  })

  it("fetches KB health only when the knowledge view is active", async () => {
    currentQuery = "view=knowledge"
    const fetchMock = vi.mocked(global.fetch)
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        total_docs: 1,
        total_chunks: 2,
        avg_match_score: 0.8,
        retrieval_diversity_score: 0.5,
        low_confidence_queries: [],
        doc_coverage: [],
        high_overlap_pairs: [],
      }),
    } as Response)

    render(<AdminWorkspace />)

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith("http://test/api/kb/health")
    )
    expect(screen.getByRole("heading", { name: /KB Health/i })).toBeInTheDocument()
  })

  it("routes session selection and return-to-inbox through the URL", async () => {
    currentQuery = "view=sessions"
    render(<AdminWorkspace />)

    fireEvent.click(screen.getByRole("button", { name: /open session/i }))

    expect(push).toHaveBeenCalledWith("/admin?view=sessions&sessionId=session-1", {
      scroll: false,
    })

    currentQuery = "view=sessions&sessionId=session-1"
    render(<AdminWorkspace />)

    fireEvent.click(screen.getByRole("button", { name: /back to inbox/i }))

    expect(push).toHaveBeenCalledWith("/admin?view=sessions", { scroll: false })
  })

  it("routes Track Builder selection through the URL", async () => {
    currentQuery = "view=tracks"
    render(<AdminWorkspace />)

    fireEvent.click(screen.getByRole("button", { name: /pick track/i }))

    expect(push).toHaveBeenCalledWith("/admin?view=tracks&trackSlug=dsai", {
      scroll: false,
    })
  })
})
