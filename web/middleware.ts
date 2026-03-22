// web/middleware.ts
import { NextRequest, NextResponse } from "next/server"

export function middleware(request: NextRequest) {
  if (request.nextUrl.pathname.startsWith("/admin")) {
    const key = request.nextUrl.searchParams.get("key")
    if (key !== "demo2026") {
      return new NextResponse("Unauthorized", { status: 401 })
    }
  }
  return NextResponse.next()
}

export const config = { matcher: ["/admin/:path*"] }
