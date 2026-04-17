import { render, screen, waitFor } from "@testing-library/react"
import { vi } from "vitest"
import SmartCanvas from "../SmartCanvas"

describe("SmartCanvas", () => {
  afterEach(() => {
    vi.resetAllMocks()
  })

  it("shows clustered track guidance after analysis", async () => {
    let sessionGetCount = 0
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith("/api/sessions/session-1") && (!init || init.method === undefined)) {
        sessionGetCount += 1
        if (sessionGetCount === 1) {
          return {
            ok: true,
            json: async () => ({
              id: "session-1",
              status: "in-progress",
              raw_input: "DRW quantitative research",
              intent_cards: [],
              created_by: "counsellor",
              created_at: "2026-04-12T00:00:00Z",
              updated_at: "2026-04-12T00:00:00Z",
            }),
          } as Response
        }
        return {
          ok: true,
          json: async () => ({
            id: "session-1",
            status: "analyzed",
            raw_input: "DRW quantitative research",
            intent_cards: [],
            track_guidance: {
              status: "clustered_uncertainty",
              recommendation: "Closest tracks: Quant Finance, Software Engineering. Check the definitions and do your own research before deciding whether this is a new path.",
              nearest_tracks: [
                { slug: "quant_finance", label: "Quant Finance", score: 0.62 },
                { slug: "software_engineering", label: "Software Engineering", score: 0.38 },
              ],
              recurrence_count: 1,
              cluster_key: "quant_finance|software_engineering",
            },
            created_by: "counsellor",
            created_at: "2026-04-12T00:00:00Z",
            updated_at: "2026-04-12T00:00:00Z",
          }),
        } as Response
      }
      if (url.endsWith("/api/sessions/session-1/analyze")) {
        return {
          ok: true,
          json: async () => ({ session_id: "session-1", cards: [], already_covered: [], track_guidance: null }),
        } as Response
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })

    vi.stubGlobal("fetch", fetchMock)

    render(<SmartCanvas sessionId="session-1" onBack={vi.fn()} />)

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: /Clustered uncertainty/i })).toBeInTheDocument()
    )
    expect(screen.getByText("Quant Finance", { selector: "span.font-medium" })).toBeInTheDocument()
    expect(screen.getByText("Software Engineering", { selector: "span.font-medium" })).toBeInTheDocument()
    expect(screen.getByText(/Recurrence count: 1/i)).toBeInTheDocument()
  })

  it("shows stop controls while a session is analyzing", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith("/api/sessions/session-2")) {
        return {
          ok: true,
          json: async () => ({
            id: "session-2",
            status: "analyzing",
            raw_input: "Goldman Sachs update",
            intent_cards: [],
            created_by: "counsellor",
            created_at: "2026-04-12T00:00:00Z",
            updated_at: "2026-04-12T00:00:00Z",
            analysis_error: null,
          }),
        } as Response
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })

    vi.stubGlobal("fetch", fetchMock)

    render(<SmartCanvas sessionId="session-2" onBack={vi.fn()} />)

    await waitFor(() => expect(screen.getByRole("button", { name: /Stop analysis/i })).toBeInTheDocument())
    expect(screen.getByText(/Session: Analyzing/i)).toBeInTheDocument()
  })
})
