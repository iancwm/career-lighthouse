// web/middleware.ts
import { NextRequest, NextResponse } from "next/server"

export function middleware(request: NextRequest) {
  if (request.nextUrl.pathname.startsWith("/admin")) {
    const adminKey = process.env.ADMIN_KEY
    if (!adminKey) {
      // Dev mode: if ADMIN_KEY is unset, let the dashboard open without a key.
      return NextResponse.next()
    }
    const key = request.nextUrl.searchParams.get("key")
    if (key !== adminKey) {
      return new NextResponse("Unauthorized", { status: 401 })
    }
  }
  return NextResponse.next()
}

export const config = { matcher: ["/admin/:path*"] }
