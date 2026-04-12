import { render, screen, fireEvent } from "@testing-library/react"
import { vi } from "vitest"
import IntakeFlow from "../IntakeFlow"

describe("IntakeFlow", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        ({
          ok: true,
          json: async () => [
            { slug: "finance", label: "Finance / Banking" },
            { slug: "consulting", label: "Consulting" },
            { slug: "tech", label: "Tech / Product" },
            { slug: "public_sector", label: "Public Sector / GLCs" },
          ],
        }) as Response
      )
    )
    process.env.NEXT_PUBLIC_API_URL = "http://test"
  })

  afterEach(() => {
    vi.resetAllMocks()
  })

  it("renders background, region, and interest pill groups", () => {
    render(<IntakeFlow onComplete={() => {}} onBack={() => {}} />)
    expect(screen.getByText("Your background")).toBeInTheDocument()
    expect(screen.getByText("Where you're from")).toBeInTheDocument()
    expect(screen.getByText("What you're interested in")).toBeInTheDocument()
  })

  it("renders all interest pills", async () => {
    render(<IntakeFlow onComplete={() => {}} onBack={() => {}} />)
    expect(await screen.findByText("Finance / Banking")).toBeInTheDocument()
    expect(screen.getByText("Consulting")).toBeInTheDocument()
    expect(screen.getByText("Tech / Product")).toBeInTheDocument()
    expect(screen.getByText("Public Sector / GLCs")).toBeInTheDocument()
    expect(screen.getByText("Not sure yet")).toBeInTheDocument()
  })

  it("submit button is disabled until interest is selected", () => {
    render(<IntakeFlow onComplete={() => {}} onBack={() => {}} />)
    const btn = screen.getByRole("button", { name: /let's go/i })
    expect(btn).toBeDisabled()
  })

  it("submit button becomes enabled after selecting interest", async () => {
    render(<IntakeFlow onComplete={() => {}} onBack={() => {}} />)
    fireEvent.click(await screen.findByText("Finance / Banking"))
    const btn = screen.getByRole("button", { name: /let's go/i })
    expect(btn).not.toBeDisabled()
  })

  it("calls onComplete with selected interest when submitted", async () => {
    const onComplete = vi.fn()
    render(<IntakeFlow onComplete={onComplete} onBack={() => {}} />)
    fireEvent.click(await screen.findByText("Consulting"))
    fireEvent.click(screen.getByRole("button", { name: /let's go/i }))
    expect(onComplete).toHaveBeenCalledWith(
      expect.objectContaining({ interest: "consulting" })
    )
  })

  it("calls onComplete with background and region when all selected", async () => {
    const onComplete = vi.fn()
    render(<IntakeFlow onComplete={onComplete} onBack={() => {}} />)
    fireEvent.click(screen.getByText("Pre-exp Masters"))
    fireEvent.click(screen.getByText("South Asia"))
    fireEvent.click(await screen.findByText("Tech / Product"))
    fireEvent.click(screen.getByRole("button", { name: /let's go/i }))
    expect(onComplete).toHaveBeenCalledWith({
      background: "masters",
      region: "south_asia",
      interest: "tech",
    })
  })

  it("only one pill per group is selected at a time", async () => {
    const onComplete = vi.fn()
    render(<IntakeFlow onComplete={onComplete} onBack={() => {}} />)
    // Click Finance first, then Consulting — final submitted value should be consulting
    fireEvent.click(await screen.findByText("Finance / Banking"))
    fireEvent.click(screen.getByText("Consulting"))
    fireEvent.click(screen.getByRole("button", { name: /let's go/i }))
    expect(onComplete).toHaveBeenCalledWith(expect.objectContaining({ interest: "consulting" }))
  })

  it("calls onBack when back button is clicked", () => {
    const onBack = vi.fn()
    render(<IntakeFlow onComplete={() => {}} onBack={onBack} />)
    fireEvent.click(screen.getByRole("button", { name: /← back/i }))
    expect(onBack).toHaveBeenCalledTimes(1)
  })
})
