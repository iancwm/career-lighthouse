import { render, screen } from "@testing-library/react"
import StatCards from "../StatCards"

describe("StatCards", () => {
  const baseProps = {
    totalDocs: 5,
    totalChunks: 120,
    lowConfidenceCount: 2,
    avgMatchScore: 0.72,
    diversityScore: 3.5,
  }

  it("renders all five stat values", () => {
    render(<StatCards {...baseProps} />)
    expect(screen.getByText("5")).toBeInTheDocument()
    expect(screen.getByText("120")).toBeInTheDocument()
    expect(screen.getByText("2")).toBeInTheDocument()
    expect(screen.getByText("0.72")).toBeInTheDocument()
    expect(screen.getByText("3.5")).toBeInTheDocument()
  })

  it("renders — for null scores", () => {
    render(<StatCards {...baseProps} avgMatchScore={null} diversityScore={null} />)
    const dashes = screen.getAllByText("—")
    expect(dashes.length).toBe(2)
  })

  it("weakQueryCount > 5 applies red class", () => {
    const { container } = render(<StatCards {...baseProps} lowConfidenceCount={6} />)
    const redCell = container.querySelector(".text-red-600")
    expect(redCell).not.toBeNull()
    expect(redCell?.textContent).toBe("6")
  })

  it("weakQueryCount <= 5 does not apply red", () => {
    render(<StatCards {...baseProps} lowConfidenceCount={3} />)
    // The count cell should not be red
    expect(screen.getByText("3").className).not.toContain("text-red")
  })

  it("low avgMatchScore applies amber class", () => {
    const { container } = render(<StatCards {...baseProps} avgMatchScore={0.40} />)
    const amberCell = container.querySelector(".text-amber-600")
    expect(amberCell).not.toBeNull()
    expect(amberCell?.textContent).toBe("0.40")
  })

  it("low diversity score applies red class", () => {
    const { container } = render(<StatCards {...baseProps} diversityScore={1.2} />)
    const reds = container.querySelectorAll(".text-red-600")
    const values = Array.from(reds).map((el) => el.textContent)
    expect(values).toContain("1.2")
  })
})
