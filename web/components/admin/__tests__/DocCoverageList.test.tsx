import { render, screen } from "@testing-library/react"
import DocCoverageList from "../DocCoverageList"

describe("DocCoverageList", () => {
  it("renders empty state when no docs", () => {
    render(<DocCoverageList docs={[]} />)
    expect(screen.getByText(/no documents uploaded/i)).toBeInTheDocument()
  })

  it("renders filename and chunk count", () => {
    render(
      <DocCoverageList
        docs={[{ filename: "resume.pdf", chunk_count: 12, coverage_status: "good", has_overlap_warning: false }]}
      />
    )
    expect(screen.getByText("resume.pdf")).toBeInTheDocument()
    expect(screen.getByText("12 chunks")).toBeInTheDocument()
  })

  it("shows green badge for good coverage", () => {
    const { container } = render(
      <DocCoverageList
        docs={[{ filename: "a.pdf", chunk_count: 10, coverage_status: "good", has_overlap_warning: false }]}
      />
    )
    const badge = container.querySelector(".bg-green-100")
    expect(badge).not.toBeNull()
    expect(badge?.textContent).toBe("good")
  })

  it("shows amber badge for thin coverage", () => {
    const { container } = render(
      <DocCoverageList
        docs={[{ filename: "b.pdf", chunk_count: 2, coverage_status: "thin", has_overlap_warning: false }]}
      />
    )
    const badge = container.querySelector(".bg-amber-100")
    expect(badge).not.toBeNull()
    expect(badge?.textContent).toContain("thin")
  })

  it("shows overlap warning badge when has_overlap_warning is true", () => {
    render(
      <DocCoverageList
        docs={[{ filename: "c.pdf", chunk_count: 5, coverage_status: "good", has_overlap_warning: true }]}
      />
    )
    expect(screen.getByText("overlap")).toBeInTheDocument()
  })

  it("does not show overlap badge when has_overlap_warning is false", () => {
    render(
      <DocCoverageList
        docs={[{ filename: "d.pdf", chunk_count: 5, coverage_status: "good", has_overlap_warning: false }]}
      />
    )
    expect(screen.queryByText("overlap")).not.toBeInTheDocument()
  })

  it("renders multiple docs", () => {
    render(
      <DocCoverageList
        docs={[
          { filename: "a.pdf", chunk_count: 10, coverage_status: "good", has_overlap_warning: false },
          { filename: "b.pdf", chunk_count: 2, coverage_status: "thin", has_overlap_warning: true },
        ]}
      />
    )
    expect(screen.getByText("a.pdf")).toBeInTheDocument()
    expect(screen.getByText("b.pdf")).toBeInTheDocument()
  })
})
