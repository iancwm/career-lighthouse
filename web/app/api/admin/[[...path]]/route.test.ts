import { vi } from "vitest"
import { GET, POST } from "./route"

describe("admin proxy route", () => {
  const originalFetch = globalThis.fetch

  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn())
    process.env.ADMIN_KEY = "admin-secret"
    process.env.ADMIN_API_URL = "http://backend:8000"
  })

  afterEach(() => {
    vi.restoreAllMocks()
    globalThis.fetch = originalFetch
    delete process.env.ADMIN_KEY
    delete process.env.ADMIN_API_URL
  })

  it("forwards GET requests and injects the admin key", async () => {
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ ok: true }), { status: 200 }))

    const response = await GET(
      new Request("http://localhost/api/admin/api/kb/health?verbose=1") as never,
      { params: { path: ["api", "kb", "health"] } }
    )

    const [url, init] = fetchMock.mock.calls[0] as [URL, RequestInit]
    expect(url.href).toBe("http://backend:8000/api/kb/health?verbose=1")
    expect(init.method).toBe("GET")

    const headers = init.headers as Headers
    expect(headers.get("x-admin-key")).toBe("admin-secret")
    expect(await response.json()).toEqual({ ok: true })
  })

  it("forwards request bodies on POST", async () => {
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ created: true }), { status: 201 }))

    const response = await POST(
      new Request("http://localhost/api/admin/api/brief", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ resume_text: "hello" }),
      }) as never,
      { params: { path: ["api", "brief"] } }
    )

    const [url, init] = fetchMock.mock.calls[0] as [URL, RequestInit]
    expect(url.href).toBe("http://backend:8000/api/brief")
    expect(init.method).toBe("POST")
    expect(init.body).toBeInstanceOf(ArrayBuffer)
    expect((init.headers as Headers).get("x-admin-key")).toBe("admin-secret")
    expect(await response.json()).toEqual({ created: true })
  })
})
