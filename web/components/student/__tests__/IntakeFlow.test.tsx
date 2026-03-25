import { render, screen, fireEvent } from "@testing-library/react"
import IntakeFlow from "../IntakeFlow"

describe("IntakeFlow", () => {
  it("renders background, region, and interest pill groups", () => {
    render(<IntakeFlow onComplete={() => {}} onBack={() => {}} />)
    expect(screen.getByText("Your background")).toBeInTheDocument()
    expect(screen.getByText("Where you're from")).toBeInTheDocument()
    expect(screen.getByText("What you're interested in")).toBeInTheDocument()
  })

  it("renders all interest pills", () => {
    render(<IntakeFlow onComplete={() => {}} onBack={() => {}} />)
    expect(screen.getByText("Finance / Banking")).toBeInTheDocument()
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

  it("submit button becomes enabled after selecting interest", () => {
    render(<IntakeFlow onComplete={() => {}} onBack={() => {}} />)
    fireEvent.click(screen.getByText("Finance / Banking"))
    const btn = screen.getByRole("button", { name: /let's go/i })
    expect(btn).not.toBeDisabled()
  })

  it("calls onComplete with selected interest when submitted", () => {
    const onComplete = vi.fn()
    render(<IntakeFlow onComplete={onComplete} onBack={() => {}} />)
    fireEvent.click(screen.getByText("Consulting"))
    fireEvent.click(screen.getByRole("button", { name: /let's go/i }))
    expect(onComplete).toHaveBeenCalledWith(
      expect.objectContaining({ interest: "consulting" })
    )
  })

  it("calls onComplete with background and region when all selected", () => {
    const onComplete = vi.fn()
    render(<IntakeFlow onComplete={onComplete} onBack={() => {}} />)
    fireEvent.click(screen.getByText("Pre-exp Masters"))
    fireEvent.click(screen.getByText("South Asia"))
    fireEvent.click(screen.getByText("Tech / Product"))
    fireEvent.click(screen.getByRole("button", { name: /let's go/i }))
    expect(onComplete).toHaveBeenCalledWith({
      background: "masters",
      region: "south_asia",
      interest: "tech",
    })
  })

  it("only one pill per group is selected at a time", () => {
    const onComplete = vi.fn()
    render(<IntakeFlow onComplete={onComplete} onBack={() => {}} />)
    // Click Finance first, then Consulting — final submitted value should be consulting
    fireEvent.click(screen.getByText("Finance / Banking"))
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
