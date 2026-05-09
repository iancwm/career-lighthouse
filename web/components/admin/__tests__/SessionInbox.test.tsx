import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { vi } from "vitest"
import SessionInbox from "../SessionInbox"

function response(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
    text: async () => JSON.stringify(payload),
  } as Response
}

describe("SessionInbox", () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it("keeps alumni-heavy notes in staging and creates the session with alumni cards", async () => {
    const onSelectSession = vi.fn()
    const onOpenTraces = vi.fn()
    const onOpenAlumni = vi.fn()
    const sessionId = "session-alumni"
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const method = (init?.method ?? "GET").toUpperCase()

      if (url.endsWith("/api/admin/api/sessions") && method === "GET") {
        return response([])
      }

      if (url.endsWith("/api/kb/alumni/extract-preview") && method === "POST") {
        return response({
          summary_bullets: ["The note mentions an alumnus at Stripe Singapore."],
          company_links: [
            {
              company_name: "Stripe Singapore",
              company_slug: "stripe_singapore",
              relationship: "Mentor contact",
              notes: "Can refer compliance students",
            },
          ],
          facts: [
            {
              slug: "aditya_mehta",
              type: "alumni",
              confidence: 92,
              data: { name: "Aditya Mehta" },
            },
          ],
        })
      }

      if (url.endsWith("/api/admin/api/sessions") && method === "POST") {
        return response({
          id: sessionId,
          status: "pending",
          raw_input: "Met Aditya Mehta from Stripe Singapore to discuss referrals.",
          intent_cards: [],
          created_by: "counsellor",
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }, 201)
      }

      throw new Error(`Unexpected fetch: ${method} ${url}`)
    })

    vi.stubGlobal("fetch", fetchMock)

    render(<SessionInbox onSelectSession={onSelectSession} onOpenTraces={onOpenTraces} onOpenAlumni={onOpenAlumni} />)

    await waitFor(() => expect(screen.getByRole("button", { name: /Add Session Notes/i })).toBeInTheDocument())

    fireEvent.change(screen.getByPlaceholderText(/Met with Goldman Sachs/i), {
      target: { value: "Met Aditya Mehta from Stripe Singapore to discuss referrals." },
    })
    fireEvent.click(screen.getByRole("button", { name: /Add Session Notes/i }))

    await waitFor(() => expect(screen.getByRole("heading", { name: /This meeting note mentions alumni/i })).toBeInTheDocument())

    fireEvent.click(screen.getByRole("button", { name: /Create Session With Alumni Cards/i }))

    await waitFor(() => expect(onSelectSession).toHaveBeenCalledWith(sessionId))
    expect(sessionStorage.getItem("alumni_note_draft")).toBeNull()
    expect(onOpenAlumni).not.toHaveBeenCalled()
    expect(onOpenTraces).not.toHaveBeenCalled()
  })

  it("lets the user keep editing the note instead of leaving staging", async () => {
    const onSelectSession = vi.fn()
    const onOpenTraces = vi.fn()
    const onOpenAlumni = vi.fn()
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const method = (init?.method ?? "GET").toUpperCase()

      if (url.endsWith("/api/admin/api/sessions") && method === "GET") {
        return response([])
      }

      if (url.endsWith("/api/kb/alumni/extract-preview") && method === "POST") {
        return response({
          summary_bullets: ["The note mentions an alumnus at Stripe Singapore."],
        })
      }

      throw new Error(`Unexpected fetch: ${method} ${url}`)
    })

    vi.stubGlobal("fetch", fetchMock)

    render(<SessionInbox onSelectSession={onSelectSession} onOpenTraces={onOpenTraces} onOpenAlumni={onOpenAlumni} />)

    await waitFor(() => expect(screen.getByRole("button", { name: /Add Session Notes/i })).toBeInTheDocument())

    fireEvent.change(screen.getByPlaceholderText(/Met with Goldman Sachs/i), {
      target: { value: "Met Aditya Mehta from Stripe Singapore to discuss referrals." },
    })
    fireEvent.click(screen.getByRole("button", { name: /Add Session Notes/i }))

    await waitFor(() => expect(screen.getByRole("heading", { name: /This meeting note mentions alumni/i })).toBeInTheDocument())

    fireEvent.click(screen.getByRole("button", { name: /Keep Editing Note/i }))

    await waitFor(() => expect(screen.queryByRole("heading", { name: /This meeting note mentions alumni/i })).not.toBeInTheDocument())
    expect(screen.getByDisplayValue("Met Aditya Mehta from Stripe Singapore to discuss referrals.")).toBeInTheDocument()
    expect(onSelectSession).not.toHaveBeenCalled()
    expect(onOpenAlumni).not.toHaveBeenCalled()
    expect(onOpenTraces).not.toHaveBeenCalled()
  })

  it("scrolls a session into view when it is promoted from analyzing to analyzed", async () => {
    const onSelectSession = vi.fn()
    const onOpenTraces = vi.fn()
    const onOpenAlumni = vi.fn()
    const sessionId = "session-promoted"
    const scrollIntoView = vi.fn()
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView

    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView,
    })

    let sessionGetCount = 0
    let resolveAnalyze: ((value: Response) => void) | null = null

    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const method = (init?.method ?? "GET").toUpperCase()

      if (url.endsWith("/api/admin/api/sessions") && method === "GET") {
        sessionGetCount += 1
        if (sessionGetCount === 1) {
          return Promise.resolve(response([]))
        }
        if (sessionGetCount === 2) {
          return Promise.resolve(
            response([
              {
                id: sessionId,
                status: "in-progress",
                raw_input: "Fresh counsellor memo",
                intent_cards: [],
                created_by: "counsellor",
                created_at: "2026-05-06T00:00:00Z",
                updated_at: "2026-05-06T00:00:00Z",
              },
            ])
          )
        }
        return Promise.resolve(
          response([
            {
              id: sessionId,
              status: "analyzed",
              raw_input: "Fresh counsellor memo",
              intent_cards: [
                {
                  card_id: "card-1",
                  domain: "employer",
                  summary: "Update employer details",
                  status: "pending",
                },
              ],
              created_by: "counsellor",
              created_at: "2026-05-06T00:00:00Z",
              updated_at: "2026-05-06T00:00:00Z",
            },
          ])
        )
      }

      if (url.endsWith("/api/admin/api/sessions") && method === "POST") {
        return Promise.resolve(
          response(
            {
              id: sessionId,
              status: "pending",
              raw_input: "Fresh counsellor memo",
              intent_cards: [],
              created_by: "counsellor",
              created_at: "2026-05-06T00:00:00Z",
              updated_at: "2026-05-06T00:00:00Z",
            },
            201
          )
        )
      }

      if (url.endsWith(`/api/admin/api/sessions/${sessionId}/analyze`) && method === "POST") {
        return new Promise<Response>((resolve) => {
          resolveAnalyze = resolve
        })
      }

      throw new Error(`Unexpected fetch: ${method} ${url}`)
    })

    vi.stubGlobal("fetch", fetchMock)

    render(<SessionInbox onSelectSession={onSelectSession} onOpenTraces={onOpenTraces} onOpenAlumni={onOpenAlumni} />)

    await waitFor(() => expect(screen.getByRole("button", { name: /Add Session Notes/i })).toBeInTheDocument())
    fireEvent.change(screen.getByPlaceholderText(/Met with Goldman Sachs/i), {
      target: { value: "Fresh counsellor memo" },
    })
    fireEvent.click(screen.getByRole("button", { name: /Add Session Notes/i }))

    await waitFor(() => expect(screen.getByTestId(`session-row-${sessionId}`)).toBeInTheDocument())

    await waitFor(() => expect(screen.getByText("Processing your notes…")).toBeInTheDocument())

    await act(async () => {
      resolveAnalyze?.({
        ok: true,
        json: async () => ({ session_id: sessionId, cards: [] }),
      } as Response)
    })

    try {
      await waitFor(() => expect(scrollIntoView).toHaveBeenCalled())
      expect(onSelectSession).toHaveBeenCalledWith(sessionId)
      expect(onOpenTraces).not.toHaveBeenCalled()
      expect(onOpenAlumni).not.toHaveBeenCalled()
    } finally {
      if (originalScrollIntoView) {
        Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
          configurable: true,
          value: originalScrollIntoView,
        })
      } else {
        // jsdom may not define it in this environment.
        // Remove the override so later tests keep a clean prototype.
        // eslint-disable-next-line @typescript-eslint/no-dynamic-delete
        delete (HTMLElement.prototype as typeof HTMLElement.prototype & { scrollIntoView?: unknown }).scrollIntoView
      }
    }
  })

  // --- New tests ---

  it("optimistic card appears immediately before loadSessions resolves", async () => {
    const onSelectSession = vi.fn()
    const sessionId = "session-optimistic"

    let resolveGetSessions: ((value: Response) => void) | null = null
    let getCallCount = 0

    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const method = (init?.method ?? "GET").toUpperCase()

      if (url.endsWith("/api/admin/api/sessions") && method === "GET") {
        getCallCount += 1
        if (getCallCount === 1) {
          // initial load — empty
          return Promise.resolve(response([]))
        }
        // subsequent loads — delay to prove optimistic card appears first
        return new Promise<Response>((resolve) => { resolveGetSessions = resolve })
      }

      if (url.endsWith("/api/kb/alumni/extract-preview") && method === "POST") {
        return Promise.resolve(response({ summary_bullets: [] }))
      }

      if (url.endsWith("/api/admin/api/sessions") && method === "POST") {
        return Promise.resolve(response({
          id: sessionId,
          status: "pending",
          raw_input: "Optimistic test note",
          intent_cards: [],
          created_by: "counsellor",
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }, 201))
      }

      if (url.includes(`/analyze`) && method === "POST") {
        return Promise.resolve(response({ ok: true }))
      }

      throw new Error(`Unexpected fetch: ${method} ${url}`)
    })

    vi.stubGlobal("fetch", fetchMock)
    render(<SessionInbox onSelectSession={onSelectSession} onOpenTraces={vi.fn()} onOpenAlumni={vi.fn()} />)

    await waitFor(() => expect(screen.getByRole("button", { name: /Add Session Notes/i })).toBeInTheDocument())

    fireEvent.change(screen.getByPlaceholderText(/Met with Goldman Sachs/i), {
      target: { value: "Optimistic test note" },
    })
    fireEvent.click(screen.getByRole("button", { name: /Add Session Notes/i }))

    // Card should appear before the delayed GET resolves
    await waitFor(() => expect(screen.getByTestId(`session-row-${sessionId}`)).toBeInTheDocument())

    // Unblock the pending GET so the test can clean up
    resolveGetSessions?.(response([{
      id: sessionId,
      status: "pending",
      raw_input: "Optimistic test note",
      intent_cards: [],
      created_by: "counsellor",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }]))
  })

  it("shows 'Processing your notes…' notice after creating a session", async () => {
    const onSelectSession = vi.fn()
    const sessionId = "session-notice"

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const method = (init?.method ?? "GET").toUpperCase()

      if (url.endsWith("/api/admin/api/sessions") && method === "GET") {
        return response([])
      }
      if (url.endsWith("/api/kb/alumni/extract-preview") && method === "POST") {
        return response({ summary_bullets: [] })
      }
      if (url.endsWith("/api/admin/api/sessions") && method === "POST") {
        return response({
          id: sessionId,
          status: "pending",
          raw_input: "Note text",
          intent_cards: [],
          created_by: "counsellor",
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }, 201)
      }
      if (url.includes("/analyze") && method === "POST") {
        return response({ ok: true })
      }
      throw new Error(`Unexpected fetch: ${method} ${url}`)
    })

    vi.stubGlobal("fetch", fetchMock)
    render(<SessionInbox onSelectSession={onSelectSession} onOpenTraces={vi.fn()} onOpenAlumni={vi.fn()} />)

    await waitFor(() => expect(screen.getByRole("button", { name: /Add Session Notes/i })).toBeInTheDocument())
    fireEvent.change(screen.getByPlaceholderText(/Met with Goldman Sachs/i), {
      target: { value: "Note text" },
    })
    fireEvent.click(screen.getByRole("button", { name: /Add Session Notes/i }))

    await waitFor(() => expect(screen.getByText("Processing your notes…")).toBeInTheDocument())
  })

  it("history toggle shows completed sessions", async () => {
    const completedSession = {
      id: "session-done",
      status: "completed",
      raw_input: "A completed counsellor note",
      intent_cards: [],
      created_by: "counsellor",
      created_at: "2026-05-01T10:00:00Z",
      updated_at: "2026-05-01T10:00:00Z",
    }

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const method = (init?.method ?? "GET").toUpperCase()
      if (url.endsWith("/api/admin/api/sessions") && method === "GET") {
        return response([completedSession])
      }
      throw new Error(`Unexpected fetch: ${method} ${url}`)
    })

    vi.stubGlobal("fetch", fetchMock)
    render(<SessionInbox onSelectSession={vi.fn()} onOpenTraces={vi.fn()} onOpenAlumni={vi.fn()} />)

    // History toggle is present and collapsed by default
    await waitFor(() => expect(screen.getByRole("button", { name: /Show history \(1\)/i })).toBeInTheDocument())
    // Completed session not yet visible
    expect(screen.queryByText(/A completed counsellor note/i)).not.toBeInTheDocument()

    // Expand history
    fireEvent.click(screen.getByRole("button", { name: /Show history \(1\)/i }))
    await waitFor(() => expect(screen.getByText(/A completed counsellor note/i)).toBeInTheDocument())
  })

  it("history toggle collapses on second click", async () => {
    const completedSession = {
      id: "session-done-2",
      status: "completed",
      raw_input: "Another completed note",
      intent_cards: [],
      created_by: "counsellor",
      created_at: "2026-05-01T10:00:00Z",
      updated_at: "2026-05-01T10:00:00Z",
    }

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const method = (init?.method ?? "GET").toUpperCase()
      if (url.endsWith("/api/admin/api/sessions") && method === "GET") {
        return response([completedSession])
      }
      throw new Error(`Unexpected fetch: ${method} ${url}`)
    })

    vi.stubGlobal("fetch", fetchMock)
    render(<SessionInbox onSelectSession={vi.fn()} onOpenTraces={vi.fn()} onOpenAlumni={vi.fn()} />)

    await waitFor(() => expect(screen.getByRole("button", { name: /Show history \(1\)/i })).toBeInTheDocument())
    fireEvent.click(screen.getByRole("button", { name: /Show history \(1\)/i }))
    await waitFor(() => expect(screen.getByText(/Another completed note/i)).toBeInTheDocument())

    fireEvent.click(screen.getByRole("button", { name: /Hide history/i }))
    await waitFor(() => expect(screen.queryByText(/Another completed note/i)).not.toBeInTheDocument())
  })

  it("shows 'No history yet.' when history is expanded but empty", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const method = (init?.method ?? "GET").toUpperCase()
      if (url.endsWith("/api/admin/api/sessions") && method === "GET") {
        return response([{
          id: "session-active",
          status: "analyzed",
          raw_input: "Some active session",
          intent_cards: [],
          created_by: "counsellor",
          created_at: "2026-05-01T10:00:00Z",
          updated_at: "2026-05-01T10:00:00Z",
        }])
      }
      throw new Error(`Unexpected fetch: ${method} ${url}`)
    })

    vi.stubGlobal("fetch", fetchMock)
    render(<SessionInbox onSelectSession={vi.fn()} onOpenTraces={vi.fn()} onOpenAlumni={vi.fn()} />)

    await waitFor(() => expect(screen.getByRole("button", { name: /Show history \(0\)/i })).toBeInTheDocument())
    fireEvent.click(screen.getByRole("button", { name: /Show history \(0\)/i }))
    await waitFor(() => expect(screen.getByText("No history yet.")).toBeInTheDocument())
  })

  it("shows 'All caught up!' when inbox is empty but history exists", async () => {
    const completedSession = {
      id: "session-complete-only",
      status: "completed",
      raw_input: "Completed session note",
      intent_cards: [],
      created_by: "counsellor",
      created_at: "2026-05-01T10:00:00Z",
      updated_at: "2026-05-01T10:00:00Z",
    }

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const method = (init?.method ?? "GET").toUpperCase()
      if (url.endsWith("/api/admin/api/sessions") && method === "GET") {
        return response([completedSession])
      }
      throw new Error(`Unexpected fetch: ${method} ${url}`)
    })

    vi.stubGlobal("fetch", fetchMock)
    render(<SessionInbox onSelectSession={vi.fn()} onOpenTraces={vi.fn()} onOpenAlumni={vi.fn()} />)

    await waitFor(() => expect(screen.getByText("All caught up!")).toBeInTheDocument())
  })

  it("status label copy maps correctly", async () => {
    const sessions = [
      { id: "s1", status: "analyzed", raw_input: "Ready session", intent_cards: [], created_by: "c", created_at: "2026-05-01T00:00:00Z", updated_at: "2026-05-01T00:00:00Z" },
      { id: "s2", status: "failed", raw_input: "Failed session", intent_cards: [], created_by: "c", created_at: "2026-05-01T00:00:00Z", updated_at: "2026-05-01T00:00:00Z" },
    ]

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const method = (init?.method ?? "GET").toUpperCase()
      if (url.endsWith("/api/admin/api/sessions") && method === "GET") {
        return response(sessions)
      }
      throw new Error(`Unexpected fetch: ${method} ${url}`)
    })

    vi.stubGlobal("fetch", fetchMock)
    render(<SessionInbox onSelectSession={vi.fn()} onOpenTraces={vi.fn()} onOpenAlumni={vi.fn()} />)

    await waitFor(() => expect(screen.getAllByText("Ready to review").length).toBeGreaterThan(0))
    expect(screen.getAllByText("Something went wrong").length).toBeGreaterThan(0)
  })
})
