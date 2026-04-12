import { render, screen, waitFor } from "@testing-library/react"
import { vi } from "vitest"
import TrackBuilderTab from "../TrackBuilderTab"

describe("TrackBuilderTab", () => {
  beforeEach(() => {
    process.env.NEXT_PUBLIC_API_URL = "http://test"
  })

  afterEach(() => {
    vi.resetAllMocks()
  })

  it("shows the published reference summary and archived working copy banner", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith("/api/kb/draft-tracks")) {
        return {
          ok: true,
          json: async () => [
            {
              slug: "data_science",
              track_name: "Data Science",
              status: "published",
              match_description: "Draft working copy",
              match_keywords: ["data science"],
              ep_sponsorship: "",
              compass_score_typical: "",
              top_employers_smu: [],
              recruiting_timeline: "",
              international_realistic: true,
              entry_paths: [],
              salary_range_2024: "",
              typical_background: "",
              counselor_contact: null,
              notes: "",
              source_refs: [],
              last_updated: "2026-04-12",
              archived_at: "2026-04-12",
            },
          ],
        }
      }
      if (url.endsWith("/api/kb/tracks")) {
        return {
          ok: true,
          json: async () => [{ slug: "data_science", label: "Data Science", status: "active", last_published: "20260412-120000" }],
        }
      }
      if (url.endsWith("/api/kb/tracks/data_science")) {
        return {
          ok: true,
          json: async () => ({
            slug: "data_science",
            label: "Data Science",
            status: "active",
            last_published: "20260412-120000",
            track_name: "Data Science",
            match_description: "Students interested in analytics, Python, and experimentation.",
            match_keywords: ["data science", "analytics"],
            ep_sponsorship: "Common in larger firms.",
            compass_score_typical: "45-60",
            top_employers_smu: ["Grab", "DBS"],
            recruiting_timeline: "Internships open in September.",
            international_realistic: true,
            entry_paths: ["Internship to return offer"],
            salary_range_2024: "S$70K-S$110K",
            typical_background: "Stats, CS, IS.",
            counselor_contact: "Henry",
            notes: "Published reference notes.",
          }),
        }
      }
      if (url.endsWith("/api/kb/tracks/data_science/history")) {
        return {
          ok: true,
          json: async () => [{ version: "20260412-120000", published_at: "20260412-120000", filename: "20260412-120000.yaml" }],
        }
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })

    vi.stubGlobal("fetch", fetchMock)

    render(<TrackBuilderTab selectedSlug="data_science" />)

    await waitFor(() =>
      expect(screen.getByText(/archived working copy/i)).toBeInTheDocument()
    )
    expect(screen.getByText(/Published reference summary/i)).toBeInTheDocument()
    expect(screen.getByText(/Students interested in analytics, Python, and experimentation\./i)).toBeInTheDocument()
    expect(screen.getByText(/Last published version: 20260412-120000/i)).toBeInTheDocument()
    expect(screen.getByText(/Internship to return offer/i)).toBeInTheDocument()
  })
})
