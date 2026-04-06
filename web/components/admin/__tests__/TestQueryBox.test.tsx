import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { vi } from "vitest"
import TestQueryBox from "../TestQueryBox"

describe("TestQueryBox", () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it("renders input and search button", () => {
    render(<TestQueryBox apiUrl="http://localhost:8000" />)
    expect(screen.getByPlaceholderText(/DBS hiring requirements for internships/i)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /run test/i })).toBeInTheDocument()
  })

  it("does not show results before a search", () => {
    render(<TestQueryBox apiUrl="http://localhost:8000" />)
    expect(screen.queryByText(/no chunks matched/i)).not.toBeInTheDocument()
  })

  it("shows empty state when API returns no results", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [] }))
    render(<TestQueryBox apiUrl="http://localhost:8000" />)
    fireEvent.change(screen.getByPlaceholderText(/DBS hiring requirements for internships/i), {
      target: { value: "career advice" },
    })
    fireEvent.click(screen.getByRole("button", { name: /run test/i }))
    await waitFor(() =>
      expect(screen.getByText(/No matching excerpts found/i)).toBeInTheDocument()
    )
  })

  it("renders result rows on successful search", async () => {
    const results = [
      { source_filename: "resume.pdf", excerpt: "Tailor your resume.", score: 0.72 },
      { source_filename: "interview.pdf", excerpt: "Prepare for interviews.", score: 0.41 },
    ]
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => results }))
    render(<TestQueryBox apiUrl="http://localhost:8000" />)
    fireEvent.change(screen.getByPlaceholderText(/DBS hiring requirements for internships/i), {
      target: { value: "how to prepare" },
    })
    fireEvent.click(screen.getByRole("button", { name: /run test/i }))
    await waitFor(() => expect(screen.getByText("resume.pdf")).toBeInTheDocument())
    expect(screen.getByText("interview.pdf")).toBeInTheDocument()
    expect(screen.getByText("Tailor your resume.")).toBeInTheDocument()
  })

  it("score >= 0.5 applies green badge", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true, json: async () => [{ source_filename: "a.pdf", excerpt: "x", score: 0.72 }],
    }))
    const { container } = render(<TestQueryBox apiUrl="http://localhost:8000" />)
    fireEvent.change(screen.getByPlaceholderText(/DBS hiring requirements for internships/i), {
      target: { value: "q" },
    })
    fireEvent.click(screen.getByRole("button", { name: /run test/i }))
    await waitFor(() => expect(screen.getByText("0.720")).toBeInTheDocument())
    expect(container.querySelector(".bg-green-100")).not.toBeNull()
  })

  it("score < 0.35 applies red badge", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true, json: async () => [{ source_filename: "a.pdf", excerpt: "x", score: 0.20 }],
    }))
    const { container } = render(<TestQueryBox apiUrl="http://localhost:8000" />)
    fireEvent.change(screen.getByPlaceholderText(/DBS hiring requirements for internships/i), {
      target: { value: "q" },
    })
    fireEvent.click(screen.getByRole("button", { name: /run test/i }))
    await waitFor(() => expect(screen.getByText("0.200")).toBeInTheDocument())
    expect(container.querySelector(".bg-red-100")).not.toBeNull()
  })

  it("does not submit with empty query", async () => {
    const mockFetch = vi.fn()
    vi.stubGlobal("fetch", mockFetch)
    render(<TestQueryBox apiUrl="http://localhost:8000" />)
    fireEvent.click(screen.getByRole("button", { name: /run test/i }))
    expect(mockFetch).not.toHaveBeenCalled()
  })
})
