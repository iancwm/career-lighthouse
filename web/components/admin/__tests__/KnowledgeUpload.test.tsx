import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { vi } from "vitest"
import KnowledgeUpload from "../KnowledgeUpload"

describe("KnowledgeUpload", () => {
  afterEach(() => vi.resetAllMocks())

  it("shows success message after upload", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ chunk_count: 5 }),
    }))
    render(<KnowledgeUpload onUploaded={() => {}} />)
    const input = document.getElementById("file-input") as HTMLInputElement
    const file = new File(["content"], "guide.pdf", { type: "application/pdf" })
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() =>
      expect(screen.getByText(/✓ guide.pdf \(5 chunks\)/)).toBeInTheDocument()
    )
  })

  it("shows error message when upload returns non-ok status", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
    }))
    render(<KnowledgeUpload onUploaded={() => {}} />)
    const input = document.getElementById("file-input") as HTMLInputElement
    const file = new File(["content"], "bad.pdf", { type: "application/pdf" })
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() =>
      expect(screen.getByText(/✗ bad.pdf: upload failed \(500\)/)).toBeInTheDocument()
    )
  })

  it("shows amber warning banner when similarity_warning is returned", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        chunk_count: 3,
        similarity_warning: "80% similar to existing-doc.pdf",
      }),
    }))
    render(<KnowledgeUpload onUploaded={() => {}} />)
    const input = document.getElementById("file-input") as HTMLInputElement
    const file = new File(["content"], "dup.pdf", { type: "application/pdf" })
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() =>
      expect(screen.getByText(/80% similar to existing-doc\.pdf/)).toBeInTheDocument()
    )
  })

  it("calls onUploaded after successful upload", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ chunk_count: 2 }),
    }))
    const onUploaded = vi.fn()
    render(<KnowledgeUpload onUploaded={onUploaded} />)
    const input = document.getElementById("file-input") as HTMLInputElement
    const file = new File(["content"], "doc.txt", { type: "text/plain" })
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() => expect(onUploaded).toHaveBeenCalled())
  })

  it("calls onUploaded even when upload fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
    }))
    const onUploaded = vi.fn()
    render(<KnowledgeUpload onUploaded={onUploaded} />)
    const input = document.getElementById("file-input") as HTMLInputElement
    const file = new File(["content"], "doc.txt", { type: "text/plain" })
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() => expect(onUploaded).toHaveBeenCalled())
  })
})
