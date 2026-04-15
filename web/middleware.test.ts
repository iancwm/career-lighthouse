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

  it("requires the key when ADMIN_KEY is configured", () => {
    process.env.ADMIN_KEY = "demo2026"

    const response = middleware(new NextRequest("http://localhost/admin"))

    expect(response.status).toBe(401)
  })

  it("allows admin access when the key matches", () => {
    process.env.ADMIN_KEY = "demo2026"

    const response = middleware(new NextRequest("http://localhost/admin?key=demo2026"))

    expect(response.headers.get("x-middleware-next")).toBe("1")
  })
})
