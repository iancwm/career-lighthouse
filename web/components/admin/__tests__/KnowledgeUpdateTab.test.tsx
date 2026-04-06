import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { vi } from "vitest"
import KnowledgeUpdateTab from "../KnowledgeUpdateTab"

const ANALYSIS_RESULT = {
  interpretation_bullets: ["Goldman raised COMPASS threshold to 50+"],
  profile_updates: {
    investment_banking: {
      ep_sponsorship: { old: "High at BBs", new: "50+ COMPASS required at Goldman from 2026" },
    },
  },
  new_chunks: [
    {
      text: "Goldman now requires COMPASS 50+",
      source_type: "note",
      source_label: "counsellor_note",
      career_type: "investment_banking",
      chunk_id: "abc-123",
    },
  ],
  already_covered: [],
}

describe("KnowledgeUpdateTab", () => {
  afterEach(() => vi.resetAllMocks())

  it("renders idle state with disabled Analyse button", () => {
    render(<KnowledgeUpdateTab />)
    const btn = screen.getByRole("button", { name: /Review proposed changes/i })
    expect(btn).toBeDisabled()
    expect(screen.getByText(/Your review summary will appear here/i)).toBeInTheDocument()
  })

  it("enables Analyse button when text is entered", () => {
    render(<KnowledgeUpdateTab />)
    const textarea = screen.getByPlaceholderText(/Goldman changed their EP sponsorship threshold/i)
    fireEvent.change(textarea, { target: { value: "Goldman changed their EP policy" } })
    expect(screen.getByRole("button", { name: /Review proposed changes/i })).not.toBeDisabled()
  })

  it("shows diff after successful analysis", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ANALYSIS_RESULT,
    }))
    render(<KnowledgeUpdateTab />)
    fireEvent.change(screen.getByPlaceholderText(/Goldman changed their EP sponsorship threshold/i), {
      target: { value: "Goldman changed their EP policy" },
    })
    fireEvent.click(screen.getByRole("button", { name: /Review proposed changes/i }))
    await waitFor(() =>
      expect(screen.getByText(/Career Profile Updates/i)).toBeInTheDocument()
    )
    expect(screen.getByText(/New Searchable Notes/i)).toBeInTheDocument()
    expect(screen.getByText(/Goldman raised COMPASS threshold to 50\+/i)).toBeInTheDocument()
  })

  it("shows error state when analysis API returns non-ok", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 422 }))
    render(<KnowledgeUpdateTab />)
    fireEvent.change(screen.getByPlaceholderText(/Goldman changed their EP sponsorship threshold/i), {
      target: { value: "some note" },
    })
    fireEvent.click(screen.getByRole("button", { name: /Review proposed changes/i }))
    await waitFor(() =>
      expect(screen.getByText(/could not prepare the review/i)).toBeInTheDocument()
    )
  })

  it("shows success message after commit and resets to idle", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce({ ok: true, json: async () => ANALYSIS_RESULT })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ status: "ok", chunks_added: 1, profiles_updated: ["investment_banking"] }),
        })
    )
    render(<KnowledgeUpdateTab />)
    fireEvent.change(screen.getByPlaceholderText(/Goldman changed their EP sponsorship threshold/i), {
      target: { value: "Goldman changed their EP policy" },
    })
    fireEvent.click(screen.getByRole("button", { name: /Review proposed changes/i }))
    await waitFor(() => screen.getByText(/Save reviewed changes/i))
    fireEvent.click(screen.getByRole("button", { name: /^Save reviewed changes$/i }))
    await waitFor(() =>
      expect(screen.getByText(/Saved/i)).toBeInTheDocument()
    )
  })

  it("Discard resets to idle state", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ANALYSIS_RESULT,
    }))
    render(<KnowledgeUpdateTab />)
    fireEvent.change(screen.getByPlaceholderText(/Goldman changed their EP sponsorship threshold/i), {
      target: { value: "Goldman changed their EP policy" },
    })
    fireEvent.click(screen.getByRole("button", { name: /Review proposed changes/i }))
    await waitFor(() => screen.getByText(/Save reviewed changes/i))
    fireEvent.click(screen.getByRole("button", { name: /Discard/i }))
    expect(screen.getByText(/Your review summary will appear here/i)).toBeInTheDocument()
  })

  it("calls onCommitted callback after successful commit", async () => {
    const onCommitted = vi.fn()
    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce({ ok: true, json: async () => ANALYSIS_RESULT })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ status: "ok", chunks_added: 1, profiles_updated: [] }),
        })
    )
    render(<KnowledgeUpdateTab onCommitted={onCommitted} />)
    fireEvent.change(screen.getByPlaceholderText(/Goldman changed their EP sponsorship threshold/i), {
      target: { value: "Goldman changed EP policy" },
    })
    fireEvent.click(screen.getByRole("button", { name: /Review proposed changes/i }))
    await waitFor(() => screen.getByText(/Save reviewed changes/i))
    fireEvent.click(screen.getByRole("button", { name: /^Save reviewed changes$/i }))
    await waitFor(() => expect(onCommitted).toHaveBeenCalledOnce())
  })
})
