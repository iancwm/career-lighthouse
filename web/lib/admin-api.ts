/**
 * Admin API client — attaches the admin key header to all requests.
 *
 * The admin key is read from the URL query parameter (`?key=...`) and
 * forwarded to the backend as the `X-Admin-Key` header. This keeps the
 * key out of server-side logs (query params appear in access logs) while
 * still allowing the browser to authenticate with the API.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

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

  return fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  })
}
