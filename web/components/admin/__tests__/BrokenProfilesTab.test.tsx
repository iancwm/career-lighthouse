import { act } from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { vi } from "vitest"
import BrokenProfilesTab from "../BrokenProfilesTab"

function response(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
  } as Response
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => {
    resolve = res
  })
  return { promise, resolve }
}

describe("BrokenProfilesTab", () => {
  afterEach(() => {
    vi.resetAllMocks()
    vi.unstubAllGlobals()
  })

  it("shows a neutral pending state before upgrading to success after the refresh completes", async () => {
    const initialBrokenProfiles = [
      {
        slug: "sample_profile",
        filename: "sample_profile.json",
        missing_fields: ["career_type"],
        has_career_type: true,
        existing_fields: ["slug", "name"],
      },
    ]
    const autoCompleteResponse = deferred<Response>()
    let refreshRequested = false

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const method = (init?.method ?? "GET").toUpperCase()

      if (url.endsWith("/api/kb/career-profiles/broken") && method === "GET") {
        return refreshRequested ? response([]) : response(initialBrokenProfiles)
      }

      if (url.endsWith("/api/kb/career-profiles/sample_profile/auto-complete") && method === "POST") {
        const result = await autoCompleteResponse.promise
        refreshRequested = true
        return result
      }

      throw new Error(`Unexpected fetch: ${method} ${url}`)
    })

    vi.stubGlobal("fetch", fetchMock)

    render(<BrokenProfilesTab />)

    await waitFor(() => expect(screen.getByText("sample_profile")).toBeInTheDocument())
    fireEvent.click(screen.getByRole("button", { name: /Auto-complete with AI/i }))

    expect(screen.getByRole("status")).toHaveTextContent(
      "AI is extracting the missing fields for sample_profile. This can take a moment."
    )
    expect(screen.queryByText(/Profile is now active/i)).not.toBeInTheDocument()

    await act(async () => {
      autoCompleteResponse.resolve(response({ completed_fields: ["career_type"] }))
      await Promise.resolve()
    })

    await waitFor(() =>
      expect(screen.getByText(/All profiles healthy/i)).toBeInTheDocument()
    )
  })
})
