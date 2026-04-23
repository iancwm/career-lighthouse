import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { vi } from "vitest"
import FactsDashboardTab from "../FactsDashboardTab"
import { adminFetch } from "@/lib/admin-api"

vi.mock("@/lib/admin-api", () => ({
  adminFetch: vi.fn(),
}))

vi.mock("@/components/admin/forms/FactCard", () => ({
  default: ({ fact }: { fact: { slug: string; type: string } }) => (
    <div>
      <span>{fact.slug}</span>
      <span>{fact.type}</span>
    </div>
  ),
}))

function mockResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
  } as Response
}

describe("FactsDashboardTab", () => {
  const adminFetchMock = vi.mocked(adminFetch)

  beforeEach(() => {
    adminFetchMock.mockReset()
  })

  it("loads grouped facts and shows summary counts", async () => {
    adminFetchMock
      .mockResolvedValueOnce(
        mockResponse({
          facts: [
            {
              slug: "stripe-sg-aditya",
              type: "alumni",
              data: { name: "Aditya Mehta" },
              confidence: 95,
              source: "direct_from_alumni",
              timestamp: "2026-04-22T00:00:00Z",
            },
            {
              slug: "stripe-sg-timeline",
              type: "timeline_phase",
              data: { phase_name: "Summer internship window" },
              confidence: 90,
              source: "inferred",
              timestamp: "2026-04-21T00:00:00Z",
            },
          ],
          total: 2,
          filters_applied: { include_deleted: false },
        })
      )
      .mockResolvedValueOnce(
        mockResponse({
          by: "employer",
          groups: {
            stripe_singapore: [
              {
                slug: "stripe-sg-aditya",
                type: "alumni",
                data: { name: "Aditya Mehta" },
                confidence: 95,
                source: "direct_from_alumni",
                timestamp: "2026-04-22T00:00:00Z",
              },
            ],
          },
          total: 2,
          filters_applied: { include_deleted: false },
        })
      )

    render(<FactsDashboardTab />)

    await waitFor(() => expect(screen.getByRole("heading", { name: /Facts Dashboard/i })).toBeInTheDocument())
    const totalFactsCard = screen.getByText("Total facts").closest("div")
    const activeFactsCard = screen.getByText("Active facts").closest("div")

    expect(totalFactsCard).not.toBeNull()
    expect(activeFactsCard).not.toBeNull()
    expect(within(totalFactsCard as HTMLElement).getByText("2")).toBeInTheDocument()
    expect(within(activeFactsCard as HTMLElement).getByText("2")).toBeInTheDocument()
    expect(screen.getByText(/stripe_singapore/i)).toBeInTheDocument()
    expect(screen.getAllByText(/stripe-sg-aditya/i)).toHaveLength(2)
    expect(screen.getByText(/stripe-sg-timeline/i)).toBeInTheDocument()
  })

  it("serializes filters into the facts requests", async () => {
    adminFetchMock
      .mockResolvedValueOnce(mockResponse({ facts: [], total: 0, filters_applied: { include_deleted: false } }))
      .mockResolvedValueOnce(
        mockResponse({
          by: "type",
          groups: {},
          total: 0,
          filters_applied: { include_deleted: false },
        })
      )

    render(<FactsDashboardTab />)

    fireEvent.change(screen.getByLabelText(/Type/i), { target: { value: " alumni " } })
    fireEvent.change(screen.getByLabelText(/Employer/i), { target: { value: " stripe " } })
    fireEvent.change(screen.getByLabelText(/School/i), { target: { value: " NUS " } })
    fireEvent.change(screen.getByLabelText(/Source/i), { target: { value: " direct_from_alumni " } })
    fireEvent.change(screen.getByLabelText(/Min confidence/i), { target: { value: "90" } })
    fireEvent.click(screen.getByLabelText(/Include deleted facts/i))
    fireEvent.change(screen.getByLabelText(/Group by/i), { target: { value: "type" } })
    fireEvent.click(screen.getByRole("button", { name: /Refresh facts/i }))

    await waitFor(() => expect(adminFetchMock).toHaveBeenCalledTimes(4))

    const secondRoundFactsUrl = adminFetchMock.mock.calls[2][0] as string
    const secondRoundGroupedUrl = adminFetchMock.mock.calls[3][0] as string

    expect(secondRoundFactsUrl).toContain("/api/kb/facts?")
    expect(secondRoundFactsUrl).toContain("type=alumni")
    expect(secondRoundFactsUrl).toContain("employer=stripe")
    expect(secondRoundFactsUrl).toContain("school=NUS")
    expect(secondRoundFactsUrl).toContain("source=direct_from_alumni")
    expect(secondRoundFactsUrl).toContain("confidence__gte=90")
    expect(secondRoundFactsUrl).toContain("include_deleted=true")

    expect(secondRoundGroupedUrl).toContain("/api/kb/facts/grouped?")
    expect(secondRoundGroupedUrl).toContain("by=type")
    expect(secondRoundGroupedUrl).toContain("type=alumni")
  })
})
