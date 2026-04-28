/**
 * Admin API client for same-origin proxy routes.
 *
 * Authentication is handled transparently:
 * - On first access the middleware accepts `?key=...`, sets an HttpOnly session
 *   cookie, and redirects to the clean URL so the key is never visible in the
 *   address bar or browser history after the initial redirect.
 * - The `/api/admin/*` proxy reads the session cookie server-side and forwards
 *   it as `X-Admin-Key` to the Python backend.  No key handling is needed here.
 */

/**
 * Make an authenticated fetch to the admin API.
 */
export async function adminFetch(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  return fetch(`/api/admin${path}`, {
    ...options,
    // Credentials: "same-origin" ensures the session cookie is sent automatically.
    credentials: "same-origin",
  })
}
