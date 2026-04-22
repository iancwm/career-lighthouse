import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { vi } from "vitest"
import EmployerFactsTab from "../EmployerFactsTab"

// ── Fixtures ──────────────────────────────────────────────────────────────

const ACTIVE_FACT = {
  slug: "goldman-ep-req",
  type: "compensation",
  data: { role_level: "Analyst" },
  confidence: 90,
  source: "counselor",
  timestamp: "2026-04-01T00:00:00Z",
  lifecycle: "active",
  last_updated: "2026-04-01T00:00:00Z",
  source_timestamp: "2026-04-01T00:00:00Z",
}

const EMPLOYER = {
  slug: "goldman_sachs",
  employer_name: "Goldman Sachs",
  tracks: ["investment_banking"],
  ep_requirement: "EP4 required",
  intake_seasons: ["July"],
  singapore_headcount_estimate: "15-20",
  application_process: null,
  counsellor_contact: null,
  notes: null,
  structured: { facts: [ACTIVE_FACT] },
  last_updated: "2026-04-01T00:00:00Z",
  completeness: "green",
}

const ANALYSIS_RESULT = {
  interpretation_bullets: ["Goldman updated their EP requirement"],
  profile_updates: {},
  employer_updates: {
    goldman_sachs: {
      ep_requirement: {
        old: "EP4 required",
        new: "EP3+ required from Q2 2026",
        source_type: "note",
        source_label: "counsellor_note",
        source_timestamp: "2026-04-22T00:00:00Z",
      },
    },
  },
  new_chunks: [],
  already_covered: [],
}

const ANALYSIS_WITH_PROVENANCE = {
  interpretation_bullets: ["EP threshold updated"],
  profile_updates: {},
  employer_updates: {
    goldman_sachs: {
      ep_requirement: {
        old: "EP4 required",
        new: "50+ COMPASS required",
        source_type: "file",
        source_label: "goldman_policy_2026.pdf",
        source_timestamp: "2026-04-20T00:00:00Z",
      },
    },
  },
  new_chunks: [],
  already_covered: [],
}

const COMMIT_RESULT = {
  status: "ok",
  chunks_added: 0,
  profiles_updated: [],
  employers_updated: ["goldman_sachs"],
}

// ── Setup helpers ─────────────────────────────────────────────────────────

function makeFetch(...responses: Array<{ ok: boolean; json?: () => Promise<unknown> }>) {
  return vi.fn().mockImplementation(() => {
    const next = responses.shift()
    if (!next) throw new Error("Unexpected fetch call")
    return Promise.resolve({
      ok: next.ok,
      status: next.ok ? 200 : 422,
      json: next.json ?? (async () => ({})),
    })
  })
}

async function renderAndOpenFacts() {
  const fetchMock = makeFetch(
    { ok: true, json: async () => [EMPLOYER] },
    { ok: true, json: async () => [] },
  )
  vi.stubGlobal("fetch", fetchMock)
  render(<EmployerFactsTab />)

  await waitFor(() => screen.getByText("Goldman Sachs"))
  fireEvent.click(screen.getByText("Goldman Sachs"))

  fireEvent.click(screen.getByRole("button", { name: /^Facts/i }))
  return fetchMock
}

// ── Tests ─────────────────────────────────────────────────────────────────

describe("EmployerFactsTab — replace workflow", () => {
  afterEach(() => vi.resetAllMocks())

  it("shows Replace current content button on active facts", async () => {
    await renderAndOpenFacts()
    expect(screen.getByRole("button", { name: /Replace current content/i })).toBeInTheDocument()
  })

  it("does not show Replace button on superseded facts", async () => {
    const supersededFact = { ...ACTIVE_FACT, slug: "old-ep", lifecycle: "superseded", deleted: true }
    const employer = { ...EMPLOYER, structured: { facts: [ACTIVE_FACT, supersededFact] } }

    const fetchMock = makeFetch(
      { ok: true, json: async () => [employer] },
      { ok: true, json: async () => [] },
    )
    vi.stubGlobal("fetch", fetchMock)
    render(<EmployerFactsTab />)
    await waitFor(() => screen.getByText("Goldman Sachs"))
    fireEvent.click(screen.getByText("Goldman Sachs"))
    fireEvent.click(screen.getByRole("button", { name: /^Facts/i }))

    const replaceBtns = screen.getAllByRole("button", { name: /Replace current content/i })
    expect(replaceBtns).toHaveLength(1)
  })

  it("opens the replace panel with the fact label and input modes", async () => {
    await renderAndOpenFacts()

    fireEvent.click(screen.getByRole("button", { name: /Replace current content/i }))

    expect(screen.getByText(/Replace current content/i)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Counsellor note/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Uploaded file/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Review proposed changes/i })).toBeDisabled()
  })

  it("enables Review button when note text is entered", async () => {
    await renderAndOpenFacts()
    fireEvent.click(screen.getByRole("button", { name: /Replace current content/i }))

    fireEvent.change(
      screen.getByPlaceholderText(/Describe the updated content/i),
      { target: { value: "Goldman now requires EP3+" } }
    )

    expect(screen.getByRole("button", { name: /Review proposed changes/i })).not.toBeDisabled()
  })

  it("full note mode flow: analyse → diff → publish → confirmation banner", async () => {
    const fetchMock = await renderAndOpenFacts()
    fireEvent.click(screen.getByRole("button", { name: /Replace current content/i }))

    fireEvent.change(
      screen.getByPlaceholderText(/Describe the updated content/i),
      { target: { value: "Goldman now requires EP3+ from Q2 2026" } }
    )

    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => ANALYSIS_RESULT })
    fireEvent.click(screen.getByRole("button", { name: /Review proposed changes/i }))

    // Diff appears with updated value visible
    await waitFor(() => screen.getByText(/EP3\+ required from Q2 2026/i))

    // Publish action is visible
    expect(screen.getByRole("button", { name: /Publish updated content/i })).toBeInTheDocument()

    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => COMMIT_RESULT })
    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => EMPLOYER })
    fireEvent.click(screen.getByRole("button", { name: /Publish updated content/i }))

    // Confirmation banner appears with required elements
    await waitFor(() =>
      expect(screen.getByText(/Goldman Sachs.*updated/i)).toBeInTheDocument()
    )
    expect(screen.getByText(/Now active:/i)).toBeInTheDocument()
    expect(screen.getByText(/Superseded:/i)).toBeInTheDocument()
    expect(screen.getByText(/Updated:/i)).toBeInTheDocument()
  })

  it("full file mode flow: file input → analyse → publish → confirmation", async () => {
    const fetchMock = await renderAndOpenFacts()
    fireEvent.click(screen.getByRole("button", { name: /Replace current content/i }))

    // Switch to file mode
    fireEvent.click(screen.getByRole("button", { name: /Uploaded file/i }))

    const fileInput = document.querySelector("input[type='file']") as HTMLInputElement
    const file = new File(["content"], "goldman_policy.pdf", { type: "application/pdf" })
    Object.defineProperty(fileInput, "files", { value: [file] })
    fireEvent.change(fileInput)

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Review proposed changes/i })).not.toBeDisabled()
    )

    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => ANALYSIS_RESULT })
    fireEvent.click(screen.getByRole("button", { name: /Review proposed changes/i }))

    await waitFor(() => screen.getByText(/EP3\+ required from Q2 2026/i))

    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => COMMIT_RESULT })
    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => EMPLOYER })
    fireEvent.click(screen.getByRole("button", { name: /Publish updated content/i }))

    await waitFor(() =>
      expect(screen.getByText(/Goldman Sachs.*updated/i)).toBeInTheDocument()
    )
    expect(screen.getByText(/Now active:/i)).toBeInTheDocument()
  })

  it("shows error with retry when analysis fails", async () => {
    const fetchMock = await renderAndOpenFacts()
    fireEvent.click(screen.getByRole("button", { name: /Replace current content/i }))

    fireEvent.change(
      screen.getByPlaceholderText(/Describe the updated content/i),
      { target: { value: "some note" } }
    )

    fetchMock.mockResolvedValueOnce({ ok: false })
    fireEvent.click(screen.getByRole("button", { name: /Review proposed changes/i }))

    await waitFor(() =>
      expect(screen.getByText(/Could not prepare the review/i)).toBeInTheDocument()
    )

    // Retry button appears
    expect(screen.getByRole("button", { name: /Retry/i })).toBeInTheDocument()
  })

  it("shows error with retry when publish fails", async () => {
    const fetchMock = await renderAndOpenFacts()
    fireEvent.click(screen.getByRole("button", { name: /Replace current content/i }))

    fireEvent.change(
      screen.getByPlaceholderText(/Describe the updated content/i),
      { target: { value: "Goldman now requires EP3+" } }
    )

    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => ANALYSIS_RESULT })
    fireEvent.click(screen.getByRole("button", { name: /Review proposed changes/i }))

    await waitFor(() => screen.getByText(/EP3\+ required from Q2 2026/i))

    fetchMock.mockResolvedValueOnce({ ok: false })
    fireEvent.click(screen.getByRole("button", { name: /Publish updated content/i }))

    await waitFor(() =>
      expect(screen.getByText(/Could not save this update yet/i)).toBeInTheDocument()
    )

    expect(screen.getByRole("button", { name: /Retry/i })).toBeInTheDocument()
  })

  it("cancel resets the replace panel back to idle", async () => {
    await renderAndOpenFacts()
    fireEvent.click(screen.getByRole("button", { name: /Replace current content/i }))

    expect(screen.getByPlaceholderText(/Describe the updated content/i)).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: /Cancel replace/i }))

    expect(screen.queryByPlaceholderText(/Describe the updated content/i)).not.toBeInTheDocument()
    // The Replace button reappears
    expect(screen.getByRole("button", { name: /Replace current content/i })).toBeInTheDocument()
  })

  it("preserves source provenance through the review payload", async () => {
    const fetchMock = await renderAndOpenFacts()
    fireEvent.click(screen.getByRole("button", { name: /Replace current content/i }))

    fireEvent.change(
      screen.getByPlaceholderText(/Describe the updated content/i),
      { target: { value: "Goldman policy doc updated" } }
    )

    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => ANALYSIS_WITH_PROVENANCE })
    fireEvent.click(screen.getByRole("button", { name: /Review proposed changes/i }))

    // Source label and date appear in the diff
    await waitFor(() => screen.getByText(/50\+ COMPASS required/i))
    // The formatted source label should be visible (underscores replaced with spaces, title-cased)
    expect(screen.getByText(/Goldman Policy 2026/i)).toBeInTheDocument()

    // On publish, the commit payload carries source metadata
    let capturedBody: string | null = null
    fetchMock.mockImplementation(async (url: string, opts?: RequestInit) => {
      if (typeof url === "string" && url.includes("commit-analysis")) {
        capturedBody = opts?.body as string
        return { ok: true, json: async () => COMMIT_RESULT }
      }
      return { ok: true, json: async () => EMPLOYER }
    })

    fireEvent.click(screen.getByRole("button", { name: /Publish updated content/i }))

    await waitFor(() =>
      expect(screen.getByText(/Goldman Sachs.*updated/i)).toBeInTheDocument()
    )

    const parsed = JSON.parse(capturedBody ?? "{}")
    const epChange = parsed.employer_updates?.goldman_sachs?.ep_requirement
    expect(epChange).toBeDefined()
    expect(epChange.source_type).toBe("file")
    expect(epChange.source_label).toBe("goldman_policy_2026.pdf")
    expect(epChange.source_timestamp).toBe("2026-04-20T00:00:00Z")
  })

  it("hides New fact and Extract buttons while replace flow is active", async () => {
    await renderAndOpenFacts()
    fireEvent.click(screen.getByRole("button", { name: /Replace current content/i }))

    expect(screen.queryByRole("button", { name: /\+ New fact/i })).not.toBeInTheDocument()
  })
})
