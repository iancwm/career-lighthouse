import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { vi } from "vitest"
import StudentInsightsTab from "../StudentInsightsTab"
import { adminFetch } from "@/lib/admin-api"

vi.mock("@/lib/admin-api", () => ({
  adminFetch: vi.fn(),
}))

function mockResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
  } as Response
}

describe("StudentInsightsTab", () => {
  const adminFetchMock = vi.mocked(adminFetch)

  beforeEach(() => {
    adminFetchMock.mockReset()
  })

  it("renders idle state before search", () => {
    render(<StudentInsightsTab />)

    expect(screen.getByText(/Enter a query to find semantically related student questions/i)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Search student questions/i })).toBeDisabled()
  })

  it("renders loading state while search is in progress", async () => {
    let resolveRequest: ((response: Response) => void) | null = null
    adminFetchMock.mockReturnValueOnce(
      new Promise<Response>((resolve) => {
        resolveRequest = resolve
      })
    )

    render(<StudentInsightsTab />)

    fireEvent.change(screen.getByLabelText(/Search query/i), { target: { value: "interview anxiety" } })
    fireEvent.click(screen.getByRole("button", { name: /Search student questions/i }))

    expect(screen.getByText(/Searching student questions/i)).toBeInTheDocument()

    resolveRequest?.(mockResponse({ results: [] }))
    await waitFor(() => expect(screen.getByText(/No student questions matched your search/i)).toBeInTheDocument())
  })

  it("renders result cards with provenance and chips", async () => {
    adminFetchMock.mockResolvedValueOnce(
      mockResponse({
        results: [
          {
            message_id: "msg-1",
            text: "How should I prepare for product interviews?",
            timestamp: "2026-04-20T09:15:00Z",
            active_career_type: "product_management",
            background: "business",
            region: "southeast_asia",
            score: 0.8722,
          },
        ],
      })
    )

    render(<StudentInsightsTab />)

    fireEvent.change(screen.getByLabelText(/Search query/i), { target: { value: "product interview prep" } })
    fireEvent.click(screen.getByRole("button", { name: /Search student questions/i }))

    await waitFor(() =>
      expect(screen.getByText("How should I prepare for product interviews?")).toBeInTheDocument()
    )
    expect(screen.getByText(/Track: product_management/i)).toBeInTheDocument()
    expect(screen.getByText(/Background: business/i)).toBeInTheDocument()
    expect(screen.getByText(/Region: southeast_asia/i)).toBeInTheDocument()
    expect(screen.getByText(/Score: 0.872/i)).toBeInTheDocument()
    expect(screen.getByText(/Source: Student chat/i)).toBeInTheDocument()
  })

  it("renders error state when the request fails", async () => {
    adminFetchMock.mockResolvedValueOnce(mockResponse({}, 500))

    render(<StudentInsightsTab />)

    fireEvent.change(screen.getByLabelText(/Search query/i), { target: { value: "visa concerns" } })
    fireEvent.click(screen.getByRole("button", { name: /Search student questions/i }))

    await waitFor(() => expect(screen.getByText(/Search failed. Try again./i)).toBeInTheDocument())
  })

  it("renders dedicated disabled state when backend reports feature disabled", async () => {
    adminFetchMock.mockResolvedValueOnce(
      mockResponse({
        insights_enabled: false,
        results: [],
      })
    )

    render(<StudentInsightsTab />)

    fireEvent.change(screen.getByLabelText(/Search query/i), { target: { value: "international hiring concerns" } })
    fireEvent.click(screen.getByRole("button", { name: /Search student questions/i }))

    await waitFor(() =>
      expect(screen.getByText(/Student insights search is currently disabled in this environment./i)).toBeInTheDocument()
    )
  })

  it("disables unsupported background and region filters based on capability flags", async () => {
    adminFetchMock.mockResolvedValueOnce(
      mockResponse({
        supports_background_filter: false,
        supports_region_filter: false,
        results: [],
      })
    )

    render(<StudentInsightsTab />)

    fireEvent.change(screen.getByLabelText(/Search query/i), { target: { value: "interview prep" } })
    fireEvent.click(screen.getByRole("button", { name: /Search student questions/i }))

    await waitFor(() => expect(screen.getByLabelText(/Background/i)).toBeDisabled())
    expect(screen.getByLabelText(/Region/i)).toBeDisabled()
    expect(screen.getByText(/Background filter unavailable in current backend config./i)).toBeInTheDocument()
    expect(screen.getByText(/Region filter unavailable in current backend config./i)).toBeInTheDocument()
  })

  it("serializes optional filters into the request body", async () => {
    adminFetchMock.mockResolvedValueOnce(mockResponse({ results: [] }))

    render(<StudentInsightsTab />)

    fireEvent.change(screen.getByLabelText(/Search query/i), { target: { value: "  interview prep  " } })
    fireEvent.change(screen.getByLabelText(/Date from/i), { target: { value: "2026-04-01" } })
    fireEvent.change(screen.getByLabelText(/Date to/i), { target: { value: "2026-04-30" } })
    fireEvent.change(screen.getByLabelText(/Career type/i), { target: { value: " software_engineering " } })
    fireEvent.change(screen.getByLabelText(/Background/i), { target: { value: "  computing " } })
    fireEvent.change(screen.getByLabelText(/Region/i), { target: { value: " singapore " } })

    fireEvent.click(screen.getByRole("button", { name: /Search student questions/i }))

    await waitFor(() =>
      expect(adminFetchMock).toHaveBeenCalledWith(
        "/api/insights/student-questions/search",
        expect.objectContaining({ method: "POST" })
      )
    )

    const [, init] = adminFetchMock.mock.calls[0]
    const payload = JSON.parse(String(init?.body))

    expect(payload).toEqual({
      query: "interview prep",
      date_from: "2026-04-01",
      date_to: "2026-04-30",
      career_type: "software_engineering",
      background: "computing",
      region: "singapore",
    })
  })
})
