import { render, screen, waitFor } from "@testing-library/react"
import DocList from "../DocList"

const mockDocs = [
  { doc_id: "smu-alumni-paths.txt", filename: "smu-alumni-paths.txt", chunk_count: 4, uploaded_at: "2026-01-01" },
  { doc_id: "gic-guide.txt", filename: "gic-guide.txt", chunk_count: 2, uploaded_at: "2026-01-02" },
]

beforeEach(() => {
  global.fetch = vi.fn().mockResolvedValue({
    json: () => Promise.resolve(mockDocs),
  } as any)
})

afterEach(() => vi.resetAllMocks())

describe("DocList", () => {
  it("shows empty state when no docs", async () => {
    global.fetch = vi.fn().mockResolvedValue({ json: () => Promise.resolve([]) } as any)
    render(<DocList refreshKey={0} />)
    await waitFor(() => expect(screen.getByText(/No source documents uploaded yet/i)).toBeInTheDocument())
  })

  it("renders document list with filenames and chunk counts", async () => {
    render(<DocList refreshKey={0} />)
    await waitFor(() => expect(screen.getByText("smu-alumni-paths.txt")).toBeInTheDocument())
    expect(screen.getByText("gic-guide.txt")).toBeInTheDocument()
    expect(screen.getByText("4 chunks")).toBeInTheDocument()
  })
})
