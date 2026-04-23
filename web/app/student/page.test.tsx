import { render, screen } from "@testing-library/react"
import StudentPage from "./page"

describe("StudentPage", () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  it("shows the resume upload section before the guided entry prompt", () => {
    render(<StudentPage />)

    const resumeHeading = screen.getByRole("heading", { name: /Start with your resume/i })
    const guidedHeading = screen.getByRole("heading", { name: /Where would you like to start\?/i })

    expect(resumeHeading.compareDocumentPosition(guidedHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })
})
