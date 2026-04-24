import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { vi } from "vitest"
import SessionInbox from "../SessionInbox"

function response(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
    text: async () => JSON.stringify(payload),
  } as Response
}

describe("SessionInbox", () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it("shows the alumni redirect popup and stores the note in session storage", async () => {
    const onSelectSession = vi.fn()
    const onOpenTraces = vi.fn()
    const onOpenAlumni = vi.fn()
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const method = (init?.method ?? "GET").toUpperCase()

      if (url.endsWith("/api/admin/api/sessions") && method === "GET") {
        return response([])
      }

      if (url.endsWith("/api/kb/alumni/extract-preview") && method === "POST") {
        return response({
          summary_bullets: ["The note mentions an alumnus at Stripe Singapore."],
          company_links: [
            {
              company_name: "Stripe Singapore",
              company_slug: "stripe_singapore",
              relationship: "Mentor contact",
              notes: "Can refer compliance students",
            },
          ],
          facts: [
            {
              slug: "aditya_mehta",
              type: "alumni",
              confidence: 92,
              data: { name: "Aditya Mehta" },
            },
          ],
        })
      }

      throw new Error(`Unexpected fetch: ${method} ${url}`)
    })

    vi.stubGlobal("fetch", fetchMock)

    render(<SessionInbox onSelectSession={onSelectSession} onOpenTraces={onOpenTraces} onOpenAlumni={onOpenAlumni} />)

    await waitFor(() => expect(screen.getByRole("button", { name: /Create Session/i })).toBeInTheDocument())

    fireEvent.change(screen.getByPlaceholderText(/Met with Goldman Sachs/i), {
      target: { value: "Met Aditya Mehta from Stripe Singapore to discuss referrals." },
    })
    fireEvent.click(screen.getByRole("button", { name: /Create Session/i }))

    await waitFor(() => expect(screen.getByRole("heading", { name: /This meeting note mentions alumni/i })).toBeInTheDocument())

    fireEvent.click(screen.getByRole("button", { name: /Open Alumni Records/i }))

    expect(sessionStorage.getItem("alumni_note_draft")).toBe("Met Aditya Mehta from Stripe Singapore to discuss referrals.")
    expect(onOpenAlumni).toHaveBeenCalledOnce()
    expect(onSelectSession).not.toHaveBeenCalled()
    expect(onOpenTraces).not.toHaveBeenCalled()
  })
})
