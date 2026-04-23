import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { vi } from "vitest"
import ResumeReviewTab from "../ResumeReviewTab"

describe("ResumeReviewTab", () => {
  afterEach(() => vi.resetAllMocks())

  it("extracts resume text from a txt upload and generates a brief", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ text: "Student resume text", filename: "resume.txt" }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ brief: "# Prep Brief\n\n- one" }),
        })
    )

    const { container } = render(<ResumeReviewTab />)

    const fileInput = container.querySelector('input[type="file"]')
    expect(fileInput).toBeTruthy()
    fireEvent.change(fileInput as HTMLInputElement, {
      target: {
        files: [new File(["student resume"], "resume.txt", { type: "text/plain" })],
      },
    })

    await waitFor(() => expect(screen.getByDisplayValue("Student resume text")).toBeInTheDocument())
    expect(screen.getByText(/Loaded from resume\.txt/i)).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: /generate brief/i }))
    await waitFor(() => expect(screen.getByRole("heading", { name: "Prep Brief", level: 3 })).toBeInTheDocument())
  })
})
