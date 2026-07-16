import { act, render, screen, waitFor } from "@testing-library/react"
import { vi } from "vitest"
import SmartCanvas from "../SmartCanvas"

function expectNodeBefore(left: HTMLElement, right: HTMLElement) {
  expect(left.compareDocumentPosition(right) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
}

describe("SmartCanvas", () => {
  afterEach(() => {
    vi.resetAllMocks()
  })

  it("shows clustered track guidance after analysis", async () => {
    let sessionGetCount = 0
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith("/api/admin/api/sessions/session-1") && (!init || init.method === undefined)) {
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
      if (url.endsWith("/api/admin/api/sessions/session-1/analyze")) {
        return {
          ok: true,
          json: async () => ({ session_id: "session-1", cards: [], already_covered: [], track_guidance: null }),
        } as Response
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })

    vi.stubGlobal("fetch", fetchMock)

    render(<SmartCanvas sessionId="session-1" onBack={vi.fn()} onOpenTraces={vi.fn()} />)

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
      if (url.endsWith("/api/admin/api/sessions/session-2")) {
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

    render(<SmartCanvas sessionId="session-2" onBack={vi.fn()} onOpenTraces={vi.fn()} />)

    await waitFor(() => expect(screen.getByRole("button", { name: /Stop analysis/i })).toBeInTheDocument())
    expect(screen.getByText(/Session: Analyzing/i)).toBeInTheDocument()
  })

  it("shows the analyzing status during the initial analysis flow before refresh", async () => {
    let resolveAnalyze: ((value: Response) => void) | null = null

    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith("/api/admin/api/sessions/session-5") && (!init || init.method === undefined)) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: "session-5",
            status: "in-progress",
            raw_input: "Fresh counsellor note",
            intent_cards: [],
            created_by: "counsellor",
            created_at: "2026-04-12T00:00:00Z",
            updated_at: "2026-04-12T00:00:00Z",
          }),
        } as Response)
      }
      if (url.endsWith("/api/admin/api/sessions/session-5/analyze")) {
        return new Promise<Response>((resolve) => {
          resolveAnalyze = resolve
        })
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })

    vi.stubGlobal("fetch", fetchMock)

    render(<SmartCanvas sessionId="session-5" onBack={vi.fn()} onOpenTraces={vi.fn()} />)

    await waitFor(() => expect(screen.getByText(/Analyzing/i)).toBeInTheDocument())

    await act(async () => {
      resolveAnalyze?.({
        ok: true,
        json: async () => ({ session_id: "session-5", cards: [], already_covered: [], track_guidance: null }),
      } as Response)
    })
  })

  it("renders nested follow-up data as readable json", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith("/api/admin/api/sessions/session-3")) {
        return {
          ok: true,
          json: async () => ({
            id: "session-3",
            status: "analyzed",
            raw_input: "Follow-up actions from B Labs memo",
            intent_cards: [
              {
                card_id: "card-1",
                domain: "employer",
                summary: "Record follow-up actions for B Labs",
                diff: {
                  slug: "b_labs_singapore",
                  follow_up_actions: [
                    {
                      action: "Review EP evidence",
                      description: "Check whether the Singapore EP evidence is ready",
                      owner: "counsellor",
                      status: "open",
                      target_date: "2026-05-01",
                    },
                  ],
                },
                raw_input_ref: "Follow up with B Labs",
                status: "pending",
              },
            ],
            created_by: "counsellor",
            created_at: "2026-04-12T00:00:00Z",
            updated_at: "2026-04-12T00:00:00Z",
          }),
        } as Response
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })

    vi.stubGlobal("fetch", fetchMock)

    render(<SmartCanvas sessionId="session-3" onBack={vi.fn()} onOpenTraces={vi.fn()} />)

    await waitFor(() => expect(screen.getAllByRole("textbox").length).toBeGreaterThanOrEqual(2))

    const followUpField = screen.getByDisplayValue(/Review EP evidence/) as HTMLTextAreaElement
    expect(followUpField.value).toContain('"action": "Review EP evidence"')
    expect(followUpField.value).not.toContain("[object Object]")
  })

  it("renders the alumni card variant with update metadata and chronological company history", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith("/api/admin/api/sessions/session-4")) {
        return {
          ok: true,
          json: async () => ({
            id: "session-4",
            status: "analyzed",
            raw_input: "Aditya Mehta moved from Morgan Stanley to Goldman Sachs and now mentors students.",
            intent_cards: [
              {
                card_id: "card-alumni-1",
                domain: "alumni",
                summary: "Update Aditya Mehta's alumni profile",
                raw_input_ref: "Aditya Mehta is now Managing Director at Goldman Sachs after earlier roles at Morgan Stanley.",
                status: "pending",
                is_update: true,
                matched_slug: "aditya_mehta",
                proposals: {
                  current_title: {
                    confidence: 94,
                    evidence: ["now Managing Director at Goldman Sachs"],
                    rationale: "Title is stated directly in the note.",
                  },
                  current_company: {
                    confidence: 96,
                    evidence: ["at Goldman Sachs"],
                  },
                  career_trajectory_summary: {
                    confidence: 89,
                    evidence: ["earlier roles at Morgan Stanley"],
                    rationale: "The note includes a before-and-after career path.",
                  },
                },
                diff: {
                  slug: "aditya_mehta",
                  full_name: "Aditya Mehta",
                  current_title: "Managing Director",
                  current_company: "Goldman Sachs",
                  career_trajectory_summary: "Started in markets at Morgan Stanley before moving into leadership at Goldman Sachs, and now mentors students exploring finance careers.",
                  company_links: [
                    {
                      company_name: "Goldman Sachs",
                      company_slug: "goldman_sachs",
                      title: "Managing Director",
                      relationship: "Current employer",
                      start_year: "2023",
                      is_current: true,
                      notes: "Mentors students on finance hiring.",
                    },
                    {
                      company_name: "Morgan Stanley",
                      company_slug: "morgan_stanley",
                      title: "Vice President",
                      relationship: "Previous employer",
                      start_year: "2018",
                      end_year: "2022",
                    },
                  ],
                },
              },
            ],
            created_by: "counsellor",
            created_at: "2026-04-12T00:00:00Z",
            updated_at: "2026-04-12T00:00:00Z",
          }),
        } as Response
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })

    vi.stubGlobal("fetch", fetchMock)

    render(<SmartCanvas sessionId="session-4" onBack={vi.fn()} onOpenTraces={vi.fn()} />)

    await waitFor(() => expect(screen.getByRole("heading", { name: "Aditya Mehta" })).toBeInTheDocument())

    expect(screen.getAllByText("Alumni").length).toBeGreaterThan(0)
    expect(screen.getByText(/Managing Director @ Goldman Sachs/i)).toBeInTheDocument()
    expect(screen.getByText(/Updating existing Aditya Mehta/i)).toBeInTheDocument()
    expect(screen.getByText("Confidence 94%")).toBeInTheDocument()
    expect(screen.getByText("Confidence 89%")).toBeInTheDocument()
    expect(screen.getByText("now Managing Director at Goldman Sachs", { selector: "li" })).toBeInTheDocument()
    expect(screen.getByText(/The note includes a before-and-after career path/i)).toBeInTheDocument()
    expect(screen.getByText(/Started in markets at Morgan Stanley/i, { selector: "p" })).toBeInTheDocument()
    expect(screen.getByText("Chronological")).toBeInTheDocument()

    const morganStanley = screen.getByText("Morgan Stanley", { selector: "p" })
    const goldmanSachs = screen.getByText("Goldman Sachs", { selector: "p" })
    expectNodeBefore(morganStanley, goldmanSachs)
  })

  it("keeps commit controls sticky at the bottom of the review pane", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith("/api/admin/api/sessions/session-sticky")) {
        return {
          ok: true,
          json: async () => ({
            id: "session-sticky",
            status: "analyzed",
            raw_input: "Update employer hiring process",
            intent_cards: [
              {
                card_id: "card-sticky-1",
                domain: "employer",
                summary: "Update hiring process details",
                diff: {
                  slug: "example_employer",
                  hiring_process: "Two rounds plus case interview",
                },
                raw_input_ref: "Two rounds and a case interview.",
                status: "pending",
              },
            ],
            created_by: "counsellor",
            created_at: "2026-04-12T00:00:00Z",
            updated_at: "2026-04-12T00:00:00Z",
          }),
        } as Response
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })

    vi.stubGlobal("fetch", fetchMock)

    render(<SmartCanvas sessionId="session-sticky" onBack={vi.fn()} onOpenTraces={vi.fn()} />)

    await waitFor(() => expect(screen.getByRole("heading", { name: "Update hiring process details" })).toBeInTheDocument())

    const actionBar = screen.getByTestId("smart-canvas-action-bar")
    expect(actionBar.className).toContain("sticky")
    expect(actionBar.className).toContain("bottom-0")
  })

  function claimIntentCard(overrides: Record<string, unknown> = {}) {
    return {
      card_id: "card-claim-1",
      domain: "claim",
      summary: "application_window claim for Goldman Sachs",
      raw_input_ref: "employer:goldman_sachs:notes",
      status: "pending",
      diff: {
        claim_type: "application_window",
        subject_entity_id: "entity-goldman-sachs",
        subject_mention_text: "Goldman Sachs",
        object_entity_id: null,
        object_mention_text: null,
        payload: {
          claim_type: "application_window",
          programme_id: null,
          opens_on: "2026-08-01",
          closes_on: "2026-09-30",
          date_precision: "exact_date",
          intake_year: 2027,
        },
        scope: {
          geography: "Singapore",
          organization_unit_id: null,
          programme_id: null,
          role_id: null,
          seniority: null,
          candidate_segment: null,
          academic_year: null,
        },
        assertion_status: "inferred",
        confidence: {
          extraction: 0.82,
          evidence_strength: 0.82,
          source_reliability: 0.5,
        },
        evidence_ids: ["evidence-1"],
        evidence_excerpts: ["Applications open August 1 and close September 30 for the 2027 intake."],
        source_id: "employer:goldman_sachs:notes",
      },
      ...overrides,
    }
  }

  it("renders the claim card variant with a dedicated summary instead of the generic diff editor", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith("/api/admin/api/sessions/session-claim")) {
        return {
          ok: true,
          json: async () => ({
            id: "session-claim",
            status: "analyzed",
            raw_input: "Goldman Sachs application window notes",
            intent_cards: [claimIntentCard()],
            created_by: "counsellor",
            created_at: "2026-04-12T00:00:00Z",
            updated_at: "2026-04-12T00:00:00Z",
          }),
        } as Response
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })

    vi.stubGlobal("fetch", fetchMock)

    const { container } = render(<SmartCanvas sessionId="session-claim" onBack={vi.fn()} onOpenTraces={vi.fn()} />)

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "application_window claim for Goldman Sachs" })).toBeInTheDocument()
    )

    // Dedicated claim summary line, not the generic textarea-per-key editor.
    expect(screen.getByText(/Opens 2026-08-01, closes 2026-09-30 \(intake 2027\)/)).toBeInTheDocument()
    expect(
      screen.getByText("Applications open August 1 and close September 30 for the 2027 intake.")
    ).toBeInTheDocument()
    expect(screen.getAllByText("Claim").length).toBeGreaterThan(0)
    // The generic diff-fields loop renders one <textarea> per top-level diff
    // key (see e.g. the "renders nested follow-up data" test above); claim
    // cards must skip that loop entirely in favor of the dedicated block.
    expect(container.querySelectorAll("textarea").length).toBe(0)
  })

  it("shows an unresolved-entity warning and commits claim cards to the dedicated claim-commit endpoint", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith("/api/admin/api/sessions/session-claim-2") && (!init || init.method === undefined)) {
        return {
          ok: true,
          json: async () => ({
            id: "session-claim-2",
            status: "analyzed",
            raw_input: "Goldman Sachs application window notes",
            intent_cards: [
              claimIntentCard({
                card_id: "card-claim-2",
                diff: {
                  ...claimIntentCard().diff,
                  subject_entity_id: null,
                },
              }),
            ],
            created_by: "counsellor",
            created_at: "2026-04-12T00:00:00Z",
            updated_at: "2026-04-12T00:00:00Z",
          }),
        } as Response
      }
      if (url.endsWith("/api/admin/api/kb/session/session-claim-2/claims/card-claim-2/commit") && init?.method === "POST") {
        return {
          ok: true,
          json: async () => ({
            card_id: "card-claim-2",
            domain: "claim",
            status: "committed",
            claim_id: "claim-abc123",
            message: "Created claim 'claim-abc123'",
          }),
        } as Response
      }
      throw new Error(`Unexpected fetch: ${url} ${init?.method ?? ""}`)
    })

    vi.stubGlobal("fetch", fetchMock)

    render(<SmartCanvas sessionId="session-claim-2" onBack={vi.fn()} onOpenTraces={vi.fn()} />)

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "application_window claim for Goldman Sachs" })).toBeInTheDocument()
    )

    expect(screen.getByText(/Entity not yet resolved — cannot commit until created/i)).toBeInTheDocument()

    const commitButton = screen.getByRole("button", { name: /^Commit$/i })
    await act(async () => {
      commitButton.click()
    })

    await waitFor(() => expect(screen.getByText("Card committed.")).toBeInTheDocument())

    const commitCall = fetchMock.mock.calls.find(([reqUrl]) =>
      String(reqUrl).endsWith("/api/admin/api/kb/session/session-claim-2/claims/card-claim-2/commit")
    )
    expect(commitCall).toBeTruthy()
    expect((commitCall?.[1] as RequestInit | undefined)?.method).toBe("POST")

    // Regression check: the generic session-router commit URL must never be hit for a claim card.
    const genericCommitCall = fetchMock.mock.calls.find(([reqUrl]) =>
      String(reqUrl).includes("/api/admin/api/sessions/session-claim-2/cards/")
    )
    expect(genericCommitCall).toBeUndefined()
  })

  it("discards claim cards through the existing generic discard endpoint, unmodified", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith("/api/admin/api/sessions/session-claim-3") && (!init || init.method === undefined)) {
        return {
          ok: true,
          json: async () => ({
            id: "session-claim-3",
            status: "analyzed",
            raw_input: "Goldman Sachs application window notes",
            intent_cards: [claimIntentCard({ card_id: "card-claim-3" })],
            created_by: "counsellor",
            created_at: "2026-04-12T00:00:00Z",
            updated_at: "2026-04-12T00:00:00Z",
          }),
        } as Response
      }
      if (url.endsWith("/api/admin/api/sessions/session-claim-3/cards/card-claim-3/discard") && init?.method === "POST") {
        return {
          ok: true,
          json: async () => ({}),
        } as Response
      }
      throw new Error(`Unexpected fetch: ${url} ${init?.method ?? ""}`)
    })

    vi.stubGlobal("fetch", fetchMock)

    render(<SmartCanvas sessionId="session-claim-3" onBack={vi.fn()} onOpenTraces={vi.fn()} />)

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "application_window claim for Goldman Sachs" })).toBeInTheDocument()
    )

    const discardButton = screen.getByRole("button", { name: /^Discard$/i })
    await act(async () => {
      discardButton.click()
    })

    await waitFor(() => expect(screen.getByText("Card discarded.")).toBeInTheDocument())

    const discardCall = fetchMock.mock.calls.find(([reqUrl]) =>
      String(reqUrl).endsWith("/api/admin/api/sessions/session-claim-3/cards/card-claim-3/discard")
    )
    expect(discardCall).toBeTruthy()
  })
})
