import { fireEvent, render, screen } from "@testing-library/react"
import FactCard from "../forms/FactCard"

describe("FactCard", () => {
  it("shows lifecycle and provenance details", () => {
    render(
      <FactCard
        fact={{
          slug: "goldman-sachs-ep",
          type: "compensation",
          data: { role_level: "Analyst", currency: "SGD" },
          confidence: 92,
          source: "counselor",
          timestamp: "2026-04-21T00:00:00Z",
          lifecycle: "superseded",
          last_updated: "2026-04-22T00:00:00Z",
          source_timestamp: "2026-04-21T00:00:00Z",
          superseded_by: "goldman-sachs-ep-2026",
        }}
        historyHref="/api/kb/employers/goldman_sachs/history"
      />
    )

    expect(screen.getByText(/Superseded/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: /Provenance/i }))
    expect(screen.getByText(/^Source$/i)).toBeInTheDocument()
    expect(screen.getByText(/Counselor/i)).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /Audit link/i })).toHaveAttribute(
      "href",
      "/api/kb/employers/goldman_sachs/history"
    )
  })
})
