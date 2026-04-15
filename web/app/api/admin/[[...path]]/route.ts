import { NextRequest, NextResponse } from "next/server"

type RouteContext = {
  params: {
    path?: string[]
  }
}

function backendBaseUrl() {
  return (
    process.env.ADMIN_API_URL ||
    process.env.API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8000"
  )
}

function buildTargetUrl(request: NextRequest, pathSegments: string[] | undefined) {
  const baseUrl = backendBaseUrl()
  const base = baseUrl.endsWith("/") ? baseUrl : `${baseUrl}/`
  const path = pathSegments?.join("/") ?? ""
  const target = new URL(path, base)
  target.search = new URL(request.url).search
  return target
}

function forwardHeaders(request: NextRequest) {
  const headers = new Headers(request.headers)
  headers.delete("connection")
  headers.delete("content-length")
  headers.delete("host")
  headers.delete("x-admin-key")

  const adminKey = process.env.ADMIN_KEY
  if (adminKey) {
    headers.set("x-admin-key", adminKey)
  }

  return headers
}

async function proxy(request: NextRequest, context: RouteContext) {
  const method = request.method.toUpperCase()
  const init: RequestInit = {
    method,
    headers: forwardHeaders(request),
  }

  if (method !== "GET" && method !== "HEAD") {
    const body = await request.arrayBuffer()
    if (body.byteLength > 0) {
      init.body = body
    }
  }

  const response = await fetch(buildTargetUrl(request, context.params.path), init)
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

export async function GET(request: NextRequest, context: RouteContext) {
  return proxy(request, context)
}

export async function HEAD(request: NextRequest, context: RouteContext) {
  return proxy(request, context)
}

export async function OPTIONS(request: NextRequest, context: RouteContext) {
  return proxy(request, context)
}

export async function POST(request: NextRequest, context: RouteContext) {
  return proxy(request, context)
}

export async function PUT(request: NextRequest, context: RouteContext) {
  return proxy(request, context)
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  return proxy(request, context)
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  return proxy(request, context)
}
