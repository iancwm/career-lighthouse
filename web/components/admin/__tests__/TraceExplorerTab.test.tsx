import { render, screen, waitFor } from "@testing-library/react"
import { vi } from "vitest"
import TraceExplorerTab from "../TraceExplorerTab"

describe("TraceExplorerTab", () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("loads workflow summaries and opens workflow detail", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [
          {
            workflow_id: "workflow-1",
            workflow_name: "session_card_analysis",
            status: "ok",
            session_id: "session-1",
            started_at: "2026-05-03T12:00:00Z",
            ended_at: "2026-05-03T12:00:02Z",
            duration_ms: 1200,
            prompt: {
              prompt_name: "generate_session_intents",
              prompt_source: "repo",
              prompt_label: "repo",
              prompt_version: 3,
            },
            repair_applied: true,
            card_counts: {
              committed: 2,
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
          started_at: "2026-05-03T12:00:00Z",
          ended_at: "2026-05-03T12:00:02Z",
          duration_ms: 1200,
          prompt: {
            prompt_name: "generate_session_intents",
            prompt_source: "repo",
            prompt_label: "repo",
            prompt_version: 3,
          },
          model: "gpt-5",
          summary: "2 cards are ready to review.",
          likely_cause: "The extraction, validation, and append path completed successfully.",
          recommended_action: "Review the pending cards in the staging area.",
          drop_point: "session.intent_cards",
          alumni_path: "skipped_not_alumni_heavy",
          prompt_provenance_unavailable: false,
          context_pack_summary: { existing_track_count: 4 },
          raw_output_summary: {},
          repair_summary: { applied: true, attempts: 1 },
          parsed_payload_summary: {},
          validation_summary: { result: "accepted" },
          append_summary: { result: "written" },
          card_counts: { committed: 2 },
          scores: [
            {
              key: "card_presence",
              value: true,
              label: "Card presence",
              rationale: "At least one card survived the extraction path.",
            },
          ],
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

    render(<TraceExplorerTab initialSessionId="session-1" />)

    await waitFor(() => expect(screen.getByRole("heading", { name: /Debug Workflow/i })).toBeInTheDocument())
    expect(await screen.findByText(/Session session-1/i)).toBeInTheDocument()
    expect(screen.getByText(/Repair applied/i)).toBeInTheDocument()
    expect(screen.getByText(/2 cards are ready to review\./i)).toBeInTheDocument()
    expect(screen.getByText(/Intent extraction/i)).toBeInTheDocument()
    expect(screen.getByText(/Card presence/i)).toBeInTheDocument()
  })
})
