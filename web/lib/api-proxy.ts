import { NextRequest, NextResponse } from "next/server"

export type ProxyRouteContext = {
  params: {
    path?: string[]
  }
}

export function backendBaseUrl() {
  return (
    process.env.ADMIN_API_URL ||
    process.env.API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8000"
  )
}

export function buildTargetUrl(request: NextRequest, pathSegments: string[] | undefined) {
  const baseUrl = backendBaseUrl()
  const base = baseUrl.endsWith("/") ? baseUrl : `${baseUrl}/`
  const path = pathSegments?.join("/") ?? ""
  const target = new URL(path, base)
  target.search = new URL(request.url).search
  return target
}

export function forwardHeaders(request: NextRequest, includeAdminKey = false) {
  const headers = new Headers(request.headers)
  headers.delete("connection")
  headers.delete("content-length")
  headers.delete("host")
  headers.delete("x-admin-key")

  if (includeAdminKey) {
    // Prefer the session cookie set by middleware (key is no longer in the URL).
    // Fall back to the explicit header (legacy) and then to the server env var (dev mode).
    // Optional chain guards against plain Request objects used in unit tests.
    const cookieKey = request.cookies?.get?.("admin-session-key")?.value
    const adminKey = cookieKey || request.headers.get("x-admin-key") || process.env.ADMIN_KEY
    if (adminKey) {
      headers.set("x-admin-key", adminKey)
    }
  }

  return headers
}

export async function proxyRequest(
  request: NextRequest,
  pathSegments: string[] | undefined,
  includeAdminKey = false
) {
  const method = request.method.toUpperCase()
  const init: RequestInit = {
    method,
    headers: forwardHeaders(request, includeAdminKey),
  }

  if (method !== "GET" && method !== "HEAD") {
    const body = await request.arrayBuffer()
    if (body.byteLength > 0) {
      init.body = body
    }
  }

  const response = await fetch(buildTargetUrl(request, pathSegments), init)
  const headers = new Headers(response.headers)
  headers.delete("connection")
  headers.delete("content-length")
  headers.delete("transfer-encoding")

  return new NextResponse(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  })
}
