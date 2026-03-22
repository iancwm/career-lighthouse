import { render, screen } from "@testing-library/react"
import RedundancyPanel from "../RedundancyPanel"

describe("RedundancyPanel", () => {
  it("renders no-overlap state when pairs is empty", () => {
    render(<RedundancyPanel pairs={[]} />)
    expect(screen.getByText(/no overlapping documents/i)).toBeInTheDocument()
  })

  it("renders doc_a and doc_b", () => {
    render(
      <RedundancyPanel
        pairs={[{ doc_a: "resume.pdf", doc_b: "cv.pdf", overlap_pct: 0.72, recommendation: "Remove cv.pdf" }]}
      />
    )
    expect(screen.getByText("resume.pdf")).toBeInTheDocument()
    expect(screen.getByText("cv.pdf")).toBeInTheDocument()
  })

  it("renders overlap percentage", () => {
    render(
      <RedundancyPanel
        pairs={[{ doc_a: "a.pdf", doc_b: "b.pdf", overlap_pct: 0.72, recommendation: "Remove b.pdf" }]}
      />
    )
    expect(screen.getByText("72% overlap")).toBeInTheDocument()
  })

  it("renders recommendation text", () => {
    render(
      <RedundancyPanel
        pairs={[{ doc_a: "a.pdf", doc_b: "b.pdf", overlap_pct: 0.5, recommendation: "Consolidate these docs" }]}
      />
    )
    expect(screen.getByText("Consolidate these docs")).toBeInTheDocument()
  })

  it("renders multiple pairs", () => {
    render(
      <RedundancyPanel
        pairs={[
          { doc_a: "a.pdf", doc_b: "b.pdf", overlap_pct: 0.9, recommendation: "Remove b" },
          { doc_a: "c.pdf", doc_b: "d.pdf", overlap_pct: 0.6, recommendation: "Remove d" },
        ]}
      />
    )
    expect(screen.getByText("a.pdf")).toBeInTheDocument()
    expect(screen.getByText("c.pdf")).toBeInTheDocument()
    expect(screen.getByText("90% overlap")).toBeInTheDocument()
    expect(screen.getByText("60% overlap")).toBeInTheDocument()
  })
})
