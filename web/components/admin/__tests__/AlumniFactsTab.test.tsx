import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { vi } from "vitest"
import AlumniFactsTab from "../AlumniFactsTab"

const ADMIN_KEY = "test-admin-key"
const ALUMNI_NOTE_STORAGE_KEY = "alumni_note_draft"

const ALUMNI_FIXTURE = [
  {
    slug: "aditya_mehta",
    name: "Aditya Mehta",
    degree: "LLM",
    school: "NUS",
    graduation_year: "2018",
    current_company: "Stripe Singapore",
    current_title: "Head of Compliance",
    available_for_mentoring: true,
    notes: "Trusted for compliance and referrals.",
    company_links: [
      {
        company_slug: "stripe_singapore",
        company_name: "Stripe Singapore",
        relationship: "Mentor contact",
        notes: "Can speak to compliance and risk roles",
      },
    ],
    last_updated: "2026-04-22T00:00:00Z",
  },
]

const PREVIEW_RESULT = {
  interpretation_bullets: [
    "The alumnus helps with compliance and risk referrals.",
    "The note mentions Stripe Singapore and mentoring.",
  ],
  profile_updates: {
    current_title: {
      old: "Head of Compliance",
      new: "Head of Compliance Program APAC",
    },
  },
  company_links: [
    {
      company_slug: "stripe_singapore",
      company_name: "Stripe Singapore",
      relationship: "Mentor contact",
      notes: "Can refer into compliance",
    },
  ],
  facts: [
    {
      slug: "aditya_mehta",
      type: "alumni",
      confidence: 92,
      source: "direct_from_alumni",
      data: {
        name: "Aditya Mehta",
        current_company: "Stripe Singapore",
      },
    },
  ],
}

function response(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
  } as Response
}

function setupFetch(initialAlumni = ALUMNI_FIXTURE) {
  let alumni = initialAlumni.map((item) => ({ ...item }))
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    const method = (init?.method ?? "GET").toUpperCase()

    if (url.endsWith("/api/kb/alumni") && method === "GET") {
      return response(alumni)
    }

    if (url.endsWith("/api/kb/alumni") && method === "POST") {
      const body = JSON.parse(String(init?.body ?? "{}"))
      const saved = {
        ...body,
        slug: body.slug,
        last_updated: body.last_updated ?? new Date().toISOString(),
      }
      alumni = [...alumni, saved]
      return response(saved)
    }

    if (/\/api\/kb\/alumni\/[^/]+$/.test(url) && method === "PUT") {
      const slug = url.split("/").pop() as string
      const body = JSON.parse(String(init?.body ?? "{}"))
      const saved = {
        ...body,
        slug,
        last_updated: body.last_updated ?? new Date().toISOString(),
      }
      alumni = alumni.map((item) => (item.slug === slug ? saved : item))
      return response(saved)
    }

    if (url.endsWith("/api/kb/alumni/extract-preview") && method === "POST") {
      return response(PREVIEW_RESULT)
    }

    throw new Error(`Unexpected fetch: ${method} ${url}`)
  })

  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}

function setAdminKeyInUrl() {
  window.history.replaceState({}, "", `/admin?key=${ADMIN_KEY}`)
}

function expectAllRequestsAuthenticated(fetchMock: any) {
  expect(
    fetchMock.mock.calls.every(([, init]) => (init?.headers as Record<string, string> | undefined)?.["X-Admin-Key"] === ADMIN_KEY)
  ).toBe(true)
}

function expectNodeBefore(left: HTMLElement, right: HTMLElement) {
  expect(left.compareDocumentPosition(right) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
}

describe("AlumniFactsTab", () => {
  beforeEach(() => {
    vi.resetAllMocks()
    setAdminKeyInUrl()
  })

  it("renders the roster and loads the selected alumni profile", async () => {
    const fetchMock = setupFetch()

    render(<AlumniFactsTab />)

    await waitFor(() => expect(screen.getByDisplayValue("Aditya Mehta")).toBeInTheDocument())
    expectAllRequestsAuthenticated(fetchMock)
    expect(screen.getByDisplayValue("Aditya Mehta")).toBeInTheDocument()
    expect(screen.getByLabelText(/^Current company$/i)).toHaveValue("Stripe Singapore")
    expect(screen.getByLabelText(/^Company name$/i)).toHaveValue("Stripe Singapore")
    expect(screen.getByText(/1 company link/i)).toBeInTheDocument()
  })

  it("updates an alumni profile and saves the change", async () => {
    const fetchMock = setupFetch()

    render(<AlumniFactsTab />)

    await waitFor(() => expect(screen.getByDisplayValue("Aditya Mehta")).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText(/Current title/i), {
      target: { value: "Head of Compliance Program APAC" },
    })
    fireEvent.click(screen.getByRole("button", { name: /Save alumni/i }))

    await waitFor(() => expect(screen.getByText(/Alumni profile saved/i)).toBeInTheDocument())
    expect(screen.getByDisplayValue("Head of Compliance Program APAC")).toBeInTheDocument()
    expectAllRequestsAuthenticated(fetchMock)
  })

  it("creates a new alumni profile with company links", async () => {
    const fetchMock = setupFetch()

    render(<AlumniFactsTab />)

    await waitFor(() => expect(screen.getByDisplayValue("Aditya Mehta")).toBeInTheDocument())
    fireEvent.click(screen.getByRole("button", { name: /New Alumni/i }))

    fireEvent.change(screen.getByLabelText(/Full name/i), { target: { value: "Maya Lim" } })
    fireEvent.change(screen.getByLabelText(/Current company/i), { target: { value: "Grab" } })
    fireEvent.change(screen.getByLabelText(/Current title/i), { target: { value: "Product Lead" } })
    fireEvent.change(screen.getByLabelText(/^School$/i), { target: { value: "SMU" } })
    fireEvent.change(screen.getByLabelText(/Degree/i), { target: { value: "BSc Economics" } })
    fireEvent.change(screen.getByLabelText(/Graduation year/i), { target: { value: "2021" } })
    fireEvent.click(screen.getByLabelText(/Available for mentoring/i))
    fireEvent.click(screen.getByRole("button", { name: /Add company link/i }))

    fireEvent.change(screen.getByLabelText(/Company name/i), { target: { value: "Grab" } })
    fireEvent.change(screen.getByLabelText(/Company slug/i), { target: { value: "grab" } })
    fireEvent.change(screen.getByLabelText(/Relationship/i), { target: { value: "Mentor contact" } })
    fireEvent.change(screen.getByLabelText(/Company notes/i), { target: { value: "Can refer product students" } })

    fireEvent.click(screen.getByRole("button", { name: /Create alumni/i }))

    await waitFor(() => expect(screen.getByText(/Alumni profile created/i)).toBeInTheDocument())
    expect(screen.getByDisplayValue("Maya Lim")).toBeInTheDocument()
    expect(screen.getByLabelText(/^Current company$/i)).toHaveValue("Grab")
    expect(screen.getByLabelText(/^Company name$/i)).toHaveValue("Grab")
    expectAllRequestsAuthenticated(fetchMock)
  })

  it("shows an extraction preview from meeting notes", async () => {
    const fetchMock = setupFetch()

    render(<AlumniFactsTab />)

    await waitFor(() => expect(screen.getByDisplayValue("Aditya Mehta")).toBeInTheDocument())

    const counselorNotesField = screen.queryByLabelText(/Counselor note/i)
    if (counselorNotesField) {
      fireEvent.change(counselorNotesField, {
        target: { value: "Counselor notes should not drive extraction." },
      })
    }

    fireEvent.change(screen.getByLabelText(/Counselor note/i), {
      target: { value: "Aditya can mentor students for compliance roles at Stripe Singapore." },
    })

    const counselorNoteField = screen.getByLabelText(/Counselor note/i)
    const noteExtractionHeading = screen.getByRole("heading", { name: /Paste the counselor note once/i })
    const selectedProfileHeading = screen.getByText(/Selected profile/i, { selector: "p" })
    const companyLinksHeading = screen.getByRole("heading", { name: /Trusted companies and referral context/i })

    expectNodeBefore(counselorNoteField, selectedProfileHeading)
    expectNodeBefore(noteExtractionHeading, selectedProfileHeading)
    expectNodeBefore(selectedProfileHeading, companyLinksHeading)

    fireEvent.click(screen.getByRole("button", { name: /Preview extraction/i }))

    await waitFor(() => expect(screen.getByText(/The alumnus helps with compliance/i)).toBeInTheDocument())

    const previewCall = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/api/kb/alumni/extract-preview") && (init?.method ?? "GET").toUpperCase() === "POST"
    )
    expect(previewCall).toBeDefined()
    const [, previewInit] = previewCall as [RequestInfo | URL, RequestInit | undefined]
    const previewBody = JSON.parse(String(previewInit?.body ?? "{}")) as { text?: string; alumni_slug?: string }
    expect(previewBody.text).toBe("Aditya can mentor students for compliance roles at Stripe Singapore.")
    expect(previewBody.alumni_slug).toBe("aditya_mehta")

    expect(screen.getByText(/Suggested profile changes/i)).toBeInTheDocument()
    expect(screen.getByText(/Suggested company links/i)).toBeInTheDocument()
    expect(screen.getByText(/Raw extracted facts/i)).toBeInTheDocument()
    expectAllRequestsAuthenticated(fetchMock)
  })

  it("loads a staged meeting note from session storage into the alumni composer", async () => {
    sessionStorage.setItem(ALUMNI_NOTE_STORAGE_KEY, "Aditya Mehta from Stripe Singapore can mentor compliance students.")
    const fetchMock = setupFetch()

    render(<AlumniFactsTab />)

    await waitFor(() =>
      expect(screen.getByLabelText(/Counselor note/i)).toHaveValue(
        "Aditya Mehta from Stripe Singapore can mentor compliance students."
      )
    )

    expect(screen.getByText(/Meeting note loaded from the Staging Area/i)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Create alumni/i })).toBeInTheDocument()
    expect(sessionStorage.getItem(ALUMNI_NOTE_STORAGE_KEY)).toBeNull()
    expectAllRequestsAuthenticated(fetchMock)
  })
})
