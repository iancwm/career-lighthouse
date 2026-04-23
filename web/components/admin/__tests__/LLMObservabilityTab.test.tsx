import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { vi } from "vitest"
import LLMObservabilityTab from "../LLMObservabilityTab"

describe("LLMObservabilityTab", () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("renders the source-state summary, evidence, and trace table", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          total_docs: 3,
          total_chunks: 42,
          avg_match_score: 0.67,
          retrieval_diversity_score: 2.1,
          low_confidence_queries: [
            {
              ts: "2026-04-22T08:00:00Z",
              query_text: "What internships fit me?",
              max_score: 0.31,
              doc_matched: "internship-guide.pdf",
            },
          ],
          doc_coverage: [
            {
              filename: "internship-guide.pdf",
              chunk_count: 10,
              coverage_status: "good",
              has_overlap_warning: false,
            },
          ],
          high_overlap_pairs: [],
          source_state: {
            active_sources: 2,
            superseded_sources: 1,
            stale_sources: 1,
            active_hits: 5,
            superseded_hits: 2,
            last_refreshed_at: "2026-04-22T08:05:00Z",
            stale_source_evidence: [
              {
                filename: "old-guide.pdf",
                reason: "superseded by a newer upload",
                chunk_count: 3,
                last_seen_at: "2026-04-21T08:00:00Z",
              },
            ],
          },
        }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [
          {
            trace_id: "trace-1",
            ts: "2026-04-22T09:00:00Z",
            operation: "chat.answer",
            status: "ok",
            model: "gpt-5",
            session_id: "session-1",
            phase: "reply",
            chunk_index: 1,
            chunk_count: 2,
            timeout_seconds: 12,
            max_tokens: 512,
            latency_ms: 842,
            input_chars: 240,
            output_chars: 420,
            input_preview: "Student asks about internships.",
            output_preview: "Answer with current sources.",
            error: null,
          },
        ],
      } as Response)

    vi.stubGlobal("fetch", fetchMock)

    render(<LLMObservabilityTab />)

    await waitFor(() => expect(screen.getByRole("heading", { name: /Trace every call/i })).toBeInTheDocument())
    expect(screen.getByText("Current source truth")).toBeInTheDocument()
    expect(screen.getByLabelText(/Active sources: 2/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/Superseded sources: 1/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/Stale sources: 1/i)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Explain stale sources/i })).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: /Explain stale sources/i }))

    const dialog = await screen.findByRole("dialog", { name: /Stale sources guidance/i })
    expect(dialog).toBeInTheDocument()
    expect(screen.getByText(/Why this is red, and how to fix it/i)).toBeInTheDocument()
    expect(within(dialog).getByText("old-guide.pdf")).toBeInTheDocument()
    expect(within(dialog).getByText(/Re-ingest or delete the old indexed chunks/i)).toBeInTheDocument()
    expect(screen.getByText("What internships fit me?")).toBeInTheDocument()
    expect(screen.getByText("Completed")).toBeInTheDocument()
    expect(screen.getByText("gpt-5")).toBeInTheDocument()
  })
})
