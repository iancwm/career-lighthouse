import { render, screen, fireEvent } from "@testing-library/react"
import GuidedEntry from "../GuidedEntry"

describe("GuidedEntry", () => {
  it("renders all 4 entry option buttons", () => {
    render(<GuidedEntry onOptionSelected={() => {}} onSkip={() => {}} />)
    expect(screen.getByText("I don't know where to start")).toBeInTheDocument()
    expect(screen.getByText("Exploring a specific career")).toBeInTheDocument()
    expect(screen.getByText("Understanding Singapore")).toBeInTheDocument()
    expect(screen.getByText("I have an interview")).toBeInTheDocument()
  })

  it("renders the just chat skip link", () => {
    render(<GuidedEntry onOptionSelected={() => {}} onSkip={() => {}} />)
    expect(screen.getByText(/just chat/i)).toBeInTheDocument()
  })

  it("calls onOptionSelected with correct id when option clicked", () => {
    const onOptionSelected = vi.fn()
    render(<GuidedEntry onOptionSelected={onOptionSelected} onSkip={() => {}} />)
    fireEvent.click(screen.getByText("I don't know where to start"))
    expect(onOptionSelected).toHaveBeenCalledWith("explore")
  })

  it("calls onOptionSelected for each of the 4 options", () => {
    const onOptionSelected = vi.fn()
    render(<GuidedEntry onOptionSelected={onOptionSelected} onSkip={() => {}} />)
    fireEvent.click(screen.getByText("Exploring a specific career"))
    expect(onOptionSelected).toHaveBeenCalledWith("specific")
    fireEvent.click(screen.getByText("Understanding Singapore"))
    expect(onOptionSelected).toHaveBeenCalledWith("market")
    fireEvent.click(screen.getByText("I have an interview"))
    expect(onOptionSelected).toHaveBeenCalledWith("interview")
  })

  it("calls onSkip when just chat is clicked", () => {
    const onSkip = vi.fn()
    render(<GuidedEntry onOptionSelected={() => {}} onSkip={onSkip} />)
    fireEvent.click(screen.getByText(/just chat/i))
    expect(onSkip).toHaveBeenCalledTimes(1)
  })
})
