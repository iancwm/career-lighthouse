/**
 * Backend API client for student-facing same-origin proxy routes.
 */

export async function backendFetch(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  return fetch(`/api/backend${path}`, options)
}
