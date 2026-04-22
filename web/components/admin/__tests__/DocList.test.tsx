import { render, screen, waitFor } from "@testing-library/react"
import { vi } from "vitest"
import DocList from "../DocList"

const mockDocs = [
  { doc_id: "smu-alumni-paths.txt", filename: "smu-alumni-paths.txt", chunk_count: 4, uploaded_at: "2026-01-01" },
  { doc_id: "gic-guide.txt", filename: "gic-guide.txt", chunk_count: 2, uploaded_at: "2026-01-02" },
]

beforeEach(() => {
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(mockDocs),
  } as any)
})

afterEach(() => vi.resetAllMocks())

describe("DocList", () => {
  afterEach(() => vi.resetAllMocks())

  it("shows empty state when no docs", async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve([]) } as any)
    render(<DocList refreshKey={0} />)
    await waitFor(() => expect(screen.getByText(/No source documents uploaded yet/i)).toBeInTheDocument())
  })

  it("renders document list with filenames and chunk counts", async () => {
    render(<DocList refreshKey={0} />)
    await waitFor(() => expect(screen.getByText("smu-alumni-paths.txt")).toBeInTheDocument())
    expect(screen.getByText("gic-guide.txt")).toBeInTheDocument()
    expect(screen.getByText((_, element) => element?.textContent === "4 chunks")).toBeInTheDocument()
  })

  it("marks a doc row archived and calls onDeleted after delete succeeds", async () => {
    const onDeleted = vi.fn()
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockDocs),
      } as any)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ status: "deleted" }),
      } as any)
    global.fetch = fetchMock

    render(<DocList refreshKey={0} onDeleted={onDeleted} />)

    await waitFor(() => expect(screen.getByText("smu-alumni-paths.txt")).toBeInTheDocument())
    screen.getAllByRole("button")[0].click()

    await waitFor(() => expect(onDeleted).toHaveBeenCalledOnce())
    expect(screen.getByText("smu-alumni-paths.txt")).toBeInTheDocument()
    expect(screen.getByLabelText(/Lifecycle state: Archived/i)).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/docs/smu-alumni-paths.txt"),
      expect.objectContaining({ method: "DELETE" })
    )
  })
})
