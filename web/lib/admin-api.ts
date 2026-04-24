/**
 * Admin API client for same-origin proxy routes.
 *
 * The browser still reads `?key=...` and forwards it as `X-Admin-Key`,
 * but the request now stays on the app origin and is proxied by
 * `/api/admin/*`. That keeps the browser bundle free of backend origin
 * configuration.
 */

/**
 * Extract the admin key from the current URL's query parameters.
 */
function getAdminKey(): string | null {
  if (typeof window === "undefined") return null
  return new URLSearchParams(window.location.search).get("key")
}

/**
 * Make an authenticated fetch to the admin API.
 */
export async function adminFetch(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const key = getAdminKey()
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> | undefined),
  }
  if (key) {
    headers["X-Admin-Key"] = key
  }

  return fetch(`/api/admin${path}`, {
    ...options,
    headers,
  })
}
