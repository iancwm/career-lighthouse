import { render, screen } from "@testing-library/react"
import CitationBadge from "../CitationBadge"

describe("CitationBadge", () => {
  it("renders filename", () => {
    render(<CitationBadge filename="gic-guide.txt" excerpt="GIC recruits from SMU" />)
    expect(screen.getByText("gic-guide.txt")).toBeInTheDocument()
  })

  it("shows excerpt as title tooltip", () => {
    render(<CitationBadge filename="guide.txt" excerpt="some excerpt" />)
    expect(screen.getByTitle("some excerpt")).toBeInTheDocument()
  })
})
