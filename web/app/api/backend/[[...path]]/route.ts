import { NextRequest } from "next/server"
import { proxyRequest, type ProxyRouteContext } from "@/lib/api-proxy"

async function proxy(request: NextRequest, context: ProxyRouteContext) {
  return proxyRequest(request, context.params.path, false)
}

export async function GET(request: NextRequest, context: ProxyRouteContext) {
  return proxy(request, context)
}

export async function HEAD(request: NextRequest, context: ProxyRouteContext) {
  return proxy(request, context)
}

export async function OPTIONS(request: NextRequest, context: ProxyRouteContext) {
  return proxy(request, context)
}

export async function POST(request: NextRequest, context: ProxyRouteContext) {
  return proxy(request, context)
}

export async function PUT(request: NextRequest, context: ProxyRouteContext) {
  return proxy(request, context)
}

export async function PATCH(request: NextRequest, context: ProxyRouteContext) {
  return proxy(request, context)
}

export async function DELETE(request: NextRequest, context: ProxyRouteContext) {
  return proxy(request, context)
}
