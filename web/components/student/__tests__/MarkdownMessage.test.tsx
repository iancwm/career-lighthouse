import { render, screen } from "@testing-library/react"
import MarkdownMessage from "../MarkdownMessage"

describe("MarkdownMessage", () => {
  it("renders a safe markdown subset", () => {
    render(
      <MarkdownMessage
        content={`# Heading

- first item
- second item

**Bold** text with \`code\` and [docs](https://example.com)

<script>alert("xss")</script>`}
      />
    )

    expect(screen.getByRole("heading", { name: "Heading", level: 1 })).toBeInTheDocument()
    expect(screen.getByText("first item")).toBeInTheDocument()
    expect(screen.getByText("second item")).toBeInTheDocument()
    expect(screen.getByText("Bold")).toBeInTheDocument()
    expect(screen.getByText("code")).toBeInTheDocument()

    const link = screen.getByRole("link", { name: "docs" })
    expect(link).toHaveAttribute("href", "https://example.com")
    expect(link).toHaveAttribute("target", "_blank")
    expect(link).toHaveAttribute("rel", expect.stringContaining("noreferrer"))
    expect(screen.queryByText(/alert\("xss"\)/)).toBeInTheDocument()
    expect(document.querySelector("script")).toBeNull()
  })
})
