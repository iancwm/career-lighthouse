import { expect, test } from "@playwright/test"

test.describe("Admin workspace IA", () => {
  test("lands on Career Wire with Staging Area by default", async ({ page }) => {
    await page.goto("/admin")

    await page.waitForURL(/\/admin\?view=sessions/)
    await expect(page.getByRole("button", { name: /Career Wire.*Current lane/i })).toBeVisible()
    await expect(page.getByRole("button", { name: /Smart Counsellor.*Switch lane/i })).toBeVisible()
    await expect(page.getByRole("button", { name: /Admin Room.*Switch lane/i })).toBeVisible()
    await expect(page.getByRole("button", { name: /Staging Area/i })).toBeVisible()
  })

  test("keeps legacy careers URLs compatible", async ({ page }) => {
    await page.goto("/admin?view=careers&trackSlug=consulting")

    await expect(page).toHaveURL(/view=careers/)
    await expect(page.getByRole("heading", { name: "Track Builder" })).toBeVisible()
  })

  test("keeps trace explorer reachable as a legacy deep link", async ({ page }) => {
    await page.goto("/admin?view=traces&sessionId=session-123")

    await expect(page).toHaveURL(/view=traces/)
    await expect(page.getByRole("region", { name: "Trace explorer" })).toBeVisible()
  })
})
