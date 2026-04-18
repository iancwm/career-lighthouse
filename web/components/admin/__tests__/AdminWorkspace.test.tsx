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
  default: ({
    onSelectSession,
    onOpenTraces,
  }: {
    onSelectSession: (sessionId: string) => void
    onOpenTraces: (sessionId: string) => void
  }) => (
    <div>
      <button type="button" onClick={() => onSelectSession("session-1")}>
        open session
      </button>
      <button type="button" onClick={() => onOpenTraces("session-1")}>
        open traces
      </button>
    </div>
  ),
}))
vi.mock("@/components/admin/SmartCanvas", () => ({
  default: ({ onBack, onOpenTraces }: { onBack: () => void; onOpenTraces: (sessionId: string) => void }) => (
    <div>
      <button type="button" onClick={onBack}>
        back to inbox
      </button>
      <button type="button" onClick={() => onOpenTraces("session-1")}>
        view traces
      </button>
    </div>
  ),
}))
vi.mock("@/components/admin/TraceExplorerTab", () => ({ default: () => <div>trace-explorer-tab</div> }))
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
      <button type="button" onClick={() => onSelectedSlugChange?.("data_science")}>
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
    vi.stubGlobal("fetch", vi.fn())
  })

  it("defaults to sessions and normalizes the URL", async () => {
    render(<AdminWorkspace />)

    expect(screen.getByRole("button", { name: /open session/i })).toBeInTheDocument()

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
      expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/kb/health", {
        headers: {},
      })
    )
    expect(screen.getByRole("heading", { name: /KB Health/i })).toBeInTheDocument()
  })

  it("renders the observability workspace when requested", async () => {
    currentQuery = "view=observability"
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        total_docs: 0,
        total_chunks: 0,
        avg_match_score: null,
        retrieval_diversity_score: null,
        low_confidence_queries: [],
        doc_coverage: [],
        high_overlap_pairs: [],
      }),
    } as Response)
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => [],
    } as Response)

    render(<AdminWorkspace />)

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: /Trace every call/i })).toBeInTheDocument()
    )
  })

  it("renders the trace explorer when requested", async () => {
    currentQuery = "view=traces&sessionId=session-1"
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        total_docs: 0,
        total_chunks: 0,
        avg_match_score: null,
        retrieval_diversity_score: null,
        low_confidence_queries: [],
        doc_coverage: [],
        high_overlap_pairs: [],
      }),
    } as Response)

    render(<AdminWorkspace />)

    await waitFor(() => expect(screen.getByText("trace-explorer-tab")).toBeInTheDocument())
  })

  it("routes session selection and return-to-inbox through the URL", async () => {
    currentQuery = "view=sessions"
    render(<AdminWorkspace />)

    fireEvent.click(screen.getByRole("button", { name: /open session/i }))

    expect(push).toHaveBeenCalledWith("/admin?view=sessions&sessionId=session-1", {
      scroll: false,
    })

    fireEvent.click(screen.getByRole("button", { name: /open traces/i }))

    expect(push).toHaveBeenCalledWith("/admin?view=traces&sessionId=session-1", {
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

    expect(push).toHaveBeenCalledWith("/admin?view=tracks&trackSlug=data_science", {
      scroll: false,
    })
  })
})
