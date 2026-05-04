import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { vi } from "vitest"
import LLMObservabilityTab from "../LLMObservabilityTab"

describe("LLMObservabilityTab", () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("renders source-state health plus workflow summaries and detail", async () => {
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
            workflow_id: "workflow-1",
            workflow_name: "session_card_analysis",
            status: "ok",
            model: "gpt-5",
            session_id: "session-1",
            started_at: "2026-04-22T09:00:00Z",
            ended_at: "2026-04-22T09:00:01Z",
            duration_ms: 842,
            prompt: {
              prompt_name: "generate_session_intents",
              prompt_version: 3,
              prompt_source: "repo",
              prompt_label: "repo",
            },
            drop_point: "session.intent_cards",
            failure_summary: null,
            repair_applied: true,
            card_counts: {
              committed: 3,
            },
            alumni_path: "skipped_not_alumni_heavy",
            is_partial: false,
          },
        ],
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          workflow_id: "workflow-1",
          workflow_name: "session_card_analysis",
          status: "ok",
          session_id: "session-1",
          trace_ids: ["trace-1"],
          started_at: "2026-04-22T09:00:00Z",
          ended_at: "2026-04-22T09:00:01Z",
          duration_ms: 842,
          prompt: {
            prompt_name: "generate_session_intents",
            prompt_version: 3,
            prompt_source: "repo",
            prompt_label: "repo",
          },
          model: "gpt-5",
          summary: "3 cards are ready to review.",
          likely_cause: "The extraction, validation, and append path completed successfully.",
          recommended_action: "Review the pending cards in the staging area.",
          drop_point: "session.intent_cards",
          alumni_path: "skipped_not_alumni_heavy",
          prompt_provenance_unavailable: false,
          context_pack_summary: {},
          raw_output_summary: {},
          repair_summary: { applied: true },
          parsed_payload_summary: {},
          validation_summary: {},
          append_summary: {},
          card_counts: { committed: 3 },
          scores: [],
          steps: [
            {
              step_id: "step-1",
              label: "Intent extraction",
              status: "ok",
            },
          ],
          limitations: [],
        }),
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
    expect(screen.getByText(/Repair applied/i)).toBeInTheDocument()
    expect(screen.getByText("gpt-5")).toBeInTheDocument()
    expect(screen.getByText(/3 cards are ready to review\./i)).toBeInTheDocument()
  })
})
