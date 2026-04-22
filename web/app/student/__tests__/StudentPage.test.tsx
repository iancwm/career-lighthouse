import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { vi } from "vitest"
import StudentPage from "../page"

function createFetchMock() {
  const mock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      json: async () => [
        { slug: "finance", label: "Finance / Banking" },
        { slug: "consulting", label: "Consulting" },
        { slug: "tech", label: "Tech / Product" },
        { slug: "public_sector", label: "Public Sector / GLCs" },
        { slug: "not_sure", label: "Not sure yet" },
      ],
    } as Response)
    .mockResolvedValueOnce({
      ok: true,
      json: async () => [{ slug: "consulting", label: "Consulting" }],
    } as Response)
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        response: "First answer",
        citations: [],
        active_career_type: "consulting",
      }),
    } as Response)
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        response: "Second answer",
        citations: [],
        active_career_type: "consulting",
      }),
    } as Response)

  vi.stubGlobal("fetch", mock)
  return mock
}

describe("StudentPage", () => {
  beforeEach(() => {
    process.env.NEXT_PUBLIC_API_URL = "http://test"
    sessionStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it("walks guided entry, intake, chat, reset, and clean restart", async () => {
    const fetchMock = createFetchMock()

    render(<StudentPage />)

    fireEvent.click(screen.getByRole("button", { name: /i don't know where to start/i }))
    fireEvent.click(await screen.findByRole("button", { name: "Consulting" }))
    fireEvent.click(screen.getByRole("button", { name: /let's go/i }))

    fireEvent.change(screen.getByPlaceholderText(/ask about career paths/i), {
      target: { value: "What should I do?" },
    })
    fireEvent.click(screen.getByRole("button", { name: /send/i }))

    await waitFor(() => expect(screen.getByText("First answer")).toBeInTheDocument())

    fireEvent.click(screen.getByRole("button", { name: /context:/i }))
    fireEvent.click(screen.getByRole("button", { name: /reset chat/i }))

    await waitFor(() => expect(screen.queryByText("First answer")).not.toBeInTheDocument())

    fireEvent.change(screen.getByPlaceholderText(/ask about career paths/i), {
      target: { value: "What now?" },
    })
    fireEvent.click(screen.getByRole("button", { name: /send/i }))

    await waitFor(() => expect(screen.getByText("Second answer")).toBeInTheDocument())

    const secondChatCall = JSON.parse(fetchMock.mock.calls[3][1].body)
    expect(secondChatCall.intake_context).toEqual({
      background: null,
      region: null,
      interest: "consulting",
    })
    expect(secondChatCall.active_career_type).toBeUndefined()
  })
})
