import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { vi } from "vitest"
import ChatInterface from "../ChatInterface"

// Silence env var warning in tests
beforeEach(() => {
  process.env.NEXT_PUBLIC_API_URL = "http://test"
})

function makeFetchMock(...responses: object[]) {
  let mock = vi.fn()
  mock = mock.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve([]) } as Response)
  for (const resp of responses) {
    mock = mock.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(resp) } as Response)
  }
  global.fetch = mock
  return mock
}

function makeFetchErrorMock(status = 500) {
  const mock = vi.fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve([]) } as Response)
    .mockResolvedValueOnce({ ok: false, status } as Response)
  global.fetch = mock
  return mock
}

describe("ChatInterface — Sprint 2 career type state", () => {
  it("sends intake_context on the first message when provided", async () => {
    const fetchMock = makeFetchMock({ response: "Hello", citations: [], active_career_type: "consulting" })

    render(
      <ChatInterface
        resumeText=""
        intakeContext={{ background: "masters", region: "south_asia", interest: "consulting" }}
      />
    )

    fireEvent.change(screen.getByPlaceholderText(/ask about/i), { target: { value: "What should I do?" } })
    fireEvent.click(screen.getByRole("button", { name: /send/i }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))

    const body = JSON.parse(fetchMock.mock.calls[1][1].body)
    expect(body.intake_context).toEqual({ background: "masters", region: "south_asia", interest: "consulting" })
    expect(body.active_career_type).toBeUndefined()
  })

  it("stores active_career_type from response and sends it on next message", async () => {
    const fetchMock = makeFetchMock(
      { response: "First answer", citations: [], active_career_type: "consulting" },
      { response: "Second answer", citations: [], active_career_type: "consulting" },
    )

    render(
      <ChatInterface
        resumeText=""
        intakeContext={{ background: null, region: null, interest: "consulting" }}
      />
    )

    fireEvent.change(screen.getByPlaceholderText(/ask about/i), { target: { value: "Message 1" } })
    fireEvent.click(screen.getByRole("button", { name: /send/i }))
    await waitFor(() => screen.getByText("First answer"))

    fireEvent.change(screen.getByPlaceholderText(/ask about/i), { target: { value: "Message 2" } })
    fireEvent.click(screen.getByRole("button", { name: /send/i }))
    await waitFor(() => screen.getByText("Second answer"))

    const secondCallBody = JSON.parse(fetchMock.mock.calls[2][1].body)
    expect(secondCallBody.active_career_type).toBe("consulting")
  })

  it("does not resend intake_context on second message", async () => {
    const fetchMock = makeFetchMock(
      { response: "First answer", citations: [], active_career_type: "tech_product" },
      { response: "Second answer", citations: [], active_career_type: "tech_product" },
    )

    render(
      <ChatInterface
        resumeText=""
        intakeContext={{ background: null, region: null, interest: "tech" }}
      />
    )

    fireEvent.change(screen.getByPlaceholderText(/ask about/i), { target: { value: "First" } })
    fireEvent.click(screen.getByRole("button", { name: /send/i }))
    await waitFor(() => screen.getByText("First answer"))

    fireEvent.change(screen.getByPlaceholderText(/ask about/i), { target: { value: "Second" } })
    fireEvent.click(screen.getByRole("button", { name: /send/i }))
    await waitFor(() => screen.getByText("Second answer"))

    const secondCallBody = JSON.parse(fetchMock.mock.calls[2][1].body)
    expect(secondCallBody.intake_context).toBeUndefined()
  })

  it("shows profile badge when active_career_type is set", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve([{ slug: "investment_banking", label: "Investment Banking" }]),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ response: "Advice", citations: [], active_career_type: "investment_banking" }),
      } as Response)
    global.fetch = fetchMock

    render(
      <ChatInterface
        resumeText=""
        intakeContext={{ background: null, region: null, interest: "finance" }}
      />
    )

    fireEvent.change(screen.getByPlaceholderText(/ask about/i), { target: { value: "Hello" } })
    fireEvent.click(screen.getByRole("button", { name: /send/i }))

    await waitFor(() => {
      expect(screen.getByText("Investment Banking")).toBeInTheDocument()
    })
  })

  it("does not show profile badge when no active_career_type", async () => {
    makeFetchMock({ response: "Advice", citations: [], active_career_type: null })

    render(<ChatInterface resumeText="" />)

    fireEvent.change(screen.getByPlaceholderText(/ask about/i), { target: { value: "Hello" } })
    fireEvent.click(screen.getByRole("button", { name: /send/i }))

    await waitFor(() => screen.getByText(/Advice/i))
    expect(screen.queryByText("Advising on:")).not.toBeInTheDocument()
  })

  it("shows inline error message when fetch returns non-ok response", async () => {
    makeFetchErrorMock(500)

    render(<ChatInterface resumeText="" />)

    fireEvent.change(screen.getByPlaceholderText(/ask about/i), { target: { value: "Hello" } })
    fireEvent.click(screen.getByRole("button", { name: /send/i }))

    await waitFor(() => {
      expect(screen.getByText(/something went wrong/i)).toBeInTheDocument()
    })
  })

  it("re-sends intake_context on retry after a fetch failure", async () => {
    // First call fails; second call succeeds. intake_context must appear in BOTH.
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve([]) } as Response)
      .mockResolvedValueOnce({ ok: false, status: 500 } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ response: "Retry success", citations: [], active_career_type: "consulting" }),
      } as Response)
    global.fetch = fetchMock

    render(
      <ChatInterface
        resumeText=""
        intakeContext={{ background: null, region: null, interest: "consulting" }}
      />
    )

    // First attempt — fails
    fireEvent.change(screen.getByPlaceholderText(/ask about/i), { target: { value: "My question" } })
    fireEvent.click(screen.getByRole("button", { name: /send/i }))
    await waitFor(() => screen.getByText(/something went wrong/i))

    // Retry — intake_context must still be present
    fireEvent.change(screen.getByPlaceholderText(/ask about/i), { target: { value: "My question again" } })
    fireEvent.click(screen.getByRole("button", { name: /send/i }))
    await waitFor(() => screen.getByText("Retry success"))

    const retryBody = JSON.parse(fetchMock.mock.calls[2][1].body)
    expect(retryBody.intake_context).toEqual({ background: null, region: null, interest: "consulting" })
  })

  it("renders markdown assistant responses with safe links", async () => {
    makeFetchMock({
      response: "## Title\n\n- one\n- two\n\n[Docs](https://example.com)",
      citations: [],
      active_career_type: null,
    })

    render(<ChatInterface resumeText="" />)

    fireEvent.change(screen.getByPlaceholderText(/ask about/i), { target: { value: "Hello" } })
    fireEvent.click(screen.getByRole("button", { name: /send/i }))

    await waitFor(() => screen.getByRole("heading", { name: "Title", level: 2 }))
    const link = screen.getByRole("link", { name: "Docs" })
    expect(link).toHaveAttribute("href", "https://example.com")
    expect(link).toHaveAttribute("target", "_blank")
  })
})
