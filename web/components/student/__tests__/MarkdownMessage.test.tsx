import { render, screen } from "@testing-library/react"
import MarkdownMessage from "../MarkdownMessage"

describe("MarkdownMessage", () => {
  it("renders a safe markdown subset", () => {
    render(
      <MarkdownMessage
        content={`# Heading

- first item
- second item

> quoted line
> second line

**Bold** text with *italics* and \`code\` and [docs](https://example.com)

<script>alert("xss")</script>`}
      />
    )

    expect(screen.getByRole("heading", { name: "Heading", level: 1 })).toBeInTheDocument()
    expect(screen.getByText("first item")).toBeInTheDocument()
    expect(screen.getByText("second item")).toBeInTheDocument()
    expect(screen.getByText("Bold")).toBeInTheDocument()
    expect(screen.getByText("italics").tagName).toBe("EM")
    expect(screen.getByText("code")).toBeInTheDocument()
    expect(screen.getByText(/quoted line\s+second line/i)).toBeInTheDocument()

    const link = screen.getByRole("link", { name: "docs" })
    expect(link).toHaveAttribute("href", "https://example.com")
    expect(link).toHaveAttribute("target", "_blank")
    expect(link).toHaveAttribute("rel", expect.stringContaining("noreferrer"))
    expect(screen.queryByText(/alert\("xss"\)/)).toBeInTheDocument()
    expect(document.querySelector("script")).toBeNull()
  })
})
