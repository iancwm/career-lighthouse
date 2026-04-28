// web/middleware.ts
import { NextRequest, NextResponse } from "next/server"

const COOKIE_NAME = "admin-session-key"

/**
 * Read a cookie value from the request, preferring the Next.js native
 * cookies API and falling back to raw Cookie-header parsing for
 * environments (e.g. vitest/happy-dom) that don't populate `request.cookies`.
 */
function getCookieValue(request: NextRequest, name: string): string | undefined {
  const nativeCookie = request.cookies.get(name)
  if (nativeCookie?.value !== undefined) return nativeCookie.value
  const cookieHeader = request.headers.get("cookie") || ""
  for (const part of cookieHeader.split(";")) {
    const [k, v] = part.trim().split("=")
    if (k?.trim() === name && v !== undefined) return v.trim()
  }
  return undefined
}

export function middleware(request: NextRequest) {
  if (request.nextUrl.pathname.startsWith("/admin")) {
    const adminKey = process.env.ADMIN_KEY
    if (!adminKey) {
      // Dev mode: if ADMIN_KEY is unset, let the dashboard open without a key.
      return NextResponse.next()
    }

    // Happy path: session cookie already set and valid.
    const cookieKey = getCookieValue(request, COOKIE_NAME)
    if (cookieKey === adminKey) {
      return NextResponse.next()
    }

    // Initial access: key provided via query param.
    // Accept it, redirect to the clean URL, and set a session cookie so the
    // key is no longer visible in the address bar or browser history.
    const paramKey = request.nextUrl.searchParams.get("key")
    if (paramKey === adminKey) {
      const cleanUrl = request.nextUrl.clone()
      cleanUrl.searchParams.delete("key")
      const response = NextResponse.redirect(cleanUrl)
      response.cookies.set(COOKIE_NAME, adminKey, {
        httpOnly: true,
        sameSite: "strict",
        path: "/",
        // No maxAge = session cookie: cleared when browser tab closes.
      })
      return response
    }

    return new NextResponse("Unauthorized", { status: 401 })
  }
  return NextResponse.next()
}

export const config = { matcher: ["/admin/:path*"] }
