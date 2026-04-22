import { render, screen, fireEvent } from "@testing-library/react"
import CitationBadge from "../CitationBadge"

describe("CitationBadge", () => {
  it("renders a readable source label and expands to show footnote details", () => {
    render(
      <CitationBadge
        filename="gic-guide.txt"
        excerpt="GIC recruits from SMU"
        sourceName="GIC Guide"
        updatedAt="2026-04-22T00:00:00Z"
      />
    )

    const button = screen.getByRole("button", { name: /gic guide/i })
    expect(button).toBeInTheDocument()
    fireEvent.click(button)
    expect(screen.getByText(/updated/i)).toBeInTheDocument()
    expect(screen.getByText(/gic recruits from smu/i)).toBeInTheDocument()
  })

  it("supports keyboard activation for mobile-style disclosure", () => {
    render(<CitationBadge filename="guide.txt" excerpt="some excerpt" />)

    const button = screen.getByRole("button", { name: /guide/i })
    button.focus()
    fireEvent.keyDown(button, { key: "Enter" })

    expect(screen.getByText(/some excerpt/i)).toBeInTheDocument()
  })
})
