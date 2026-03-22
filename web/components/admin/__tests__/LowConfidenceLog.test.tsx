import { render, screen } from "@testing-library/react"
import LowConfidenceLog from "../LowConfidenceLog"

describe("LowConfidenceLog", () => {
  const baseQuery = {
    ts: "2026-03-20T10:00:00Z",
    query_text: "How do I get an internship?",
    max_score: 0.28,
    doc_matched: "internship_guide.pdf",
  }

  it("renders no-data state when avgMatchScore is null", () => {
    render(<LowConfidenceLog avgMatchScore={null} queries={[]} />)
    expect(screen.getByText(/no data yet/i)).toBeInTheDocument()
  })

  it("renders empty state when avgMatchScore is set but no weak queries", () => {
    render(<LowConfidenceLog avgMatchScore={0.6} queries={[]} />)
    expect(screen.getByText(/no weak matches/i)).toBeInTheDocument()
  })

  it("renders query text", () => {
    render(<LowConfidenceLog avgMatchScore={0.4} queries={[baseQuery]} />)
    expect(screen.getByText("How do I get an internship?")).toBeInTheDocument()
  })

  it("renders score badge", () => {
    render(<LowConfidenceLog avgMatchScore={0.4} queries={[baseQuery]} />)
    expect(screen.getByText("0.280")).toBeInTheDocument()
  })

  it("renders doc_matched when present", () => {
    render(<LowConfidenceLog avgMatchScore={0.4} queries={[baseQuery]} />)
    expect(screen.getByText(/internship_guide\.pdf/)).toBeInTheDocument()
  })

  it("does not show doc_matched when null", () => {
    const q = { ...baseQuery, doc_matched: null }
    render(<LowConfidenceLog avgMatchScore={0.4} queries={[q]} />)
    expect(screen.queryByText(/internship_guide/)).not.toBeInTheDocument()
  })

  it("renders multiple queries", () => {
    const queries = [
      { ...baseQuery, query_text: "Query one" },
      { ...baseQuery, query_text: "Query two" },
    ]
    render(<LowConfidenceLog avgMatchScore={0.4} queries={queries} />)
    expect(screen.getByText("Query one")).toBeInTheDocument()
    expect(screen.getByText("Query two")).toBeInTheDocument()
  })
})
