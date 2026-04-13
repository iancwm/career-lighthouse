// web/middleware.ts
import { NextRequest, NextResponse } from "next/server"

export function middleware(request: NextRequest) {
  if (request.nextUrl.pathname.startsWith("/admin")) {
    const adminKey = process.env.ADMIN_KEY
    if (!adminKey) {
      // ADMIN_KEY not configured — block all access to prevent open exposure
      return new NextResponse("Unauthorized: ADMIN_KEY not configured", { status: 401 })
    }
    const key = request.nextUrl.searchParams.get("key")
    if (key !== adminKey) {
      return new NextResponse("Unauthorized", { status: 401 })
    }
  }
  return NextResponse.next()
}

export const config = { matcher: ["/admin/:path*"] }
