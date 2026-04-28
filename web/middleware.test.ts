// @vitest-environment node
import { NextRequest } from "next/server"
import { afterEach, describe, expect, it } from "vitest"
import { middleware } from "./middleware"

describe("middleware", () => {
  afterEach(() => {
    delete process.env.ADMIN_KEY
  })

  it("allows admin access without a key when ADMIN_KEY is unset", () => {
    delete process.env.ADMIN_KEY

    const response = middleware(new NextRequest("http://localhost/admin"))

    expect(response.headers.get("x-middleware-next")).toBe("1")
  })

  it("rejects requests with no key when ADMIN_KEY is configured", () => {
    process.env.ADMIN_KEY = "demo2026"

    const response = middleware(new NextRequest("http://localhost/admin"))

    expect(response.status).toBe(401)
  })

  it("redirects to clean URL and sets cookie when correct key is in query param", () => {
    process.env.ADMIN_KEY = "demo2026"

    const response = middleware(new NextRequest("http://localhost/admin?key=demo2026"))

    expect(response.status).toBe(307)
    expect(response.headers.get("location")).toBe("http://localhost/admin")
    expect(response.headers.get("set-cookie")).toContain("admin-session-key=demo2026")
  })

  it("rejects incorrect query param key", () => {
    process.env.ADMIN_KEY = "demo2026"

    const response = middleware(new NextRequest("http://localhost/admin?key=wrong"))

    expect(response.status).toBe(401)
  })

  it("allows access when valid session cookie is present", () => {
    process.env.ADMIN_KEY = "demo2026"

    const request = new NextRequest("http://localhost/admin", {
      headers: { cookie: "admin-session-key=demo2026" },
    })
    const response = middleware(request)

    expect(response.headers.get("x-middleware-next")).toBe("1")
  })

  it("rejects access when session cookie has wrong value", () => {
    process.env.ADMIN_KEY = "demo2026"

    const request = new NextRequest("http://localhost/admin", {
      headers: { cookie: "admin-session-key=wrong" },
    })
    const response = middleware(request)

    expect(response.status).toBe(401)
  })
})
