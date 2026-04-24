import { expect, test, type Page } from "@playwright/test"
import { ADMIN_VIEWS } from "@/components/admin/adminNavManifest"
import {
  ALUMNI_FIXTURE,
  ALUMNI_PREVIEW,
  EMPLOYER_FIXTURE,
  EMPLOYER_FIXTURE_2,
} from "@/e2e/fixtures/admin-workspace.fixtures"

async function expectCounselorNoteAboveSelectedProfile(page: Page) {
  const counselorNote = page.getByLabel("Counselor note")
  const fullNameField = page.getByLabel("Full name")

  await expect(counselorNote).toBeVisible()
  await expect(fullNameField).toBeVisible()

  const counselorNoteBox = await counselorNote.boundingBox()
  const fullNameBox = await fullNameField.boundingBox()

  expect(counselorNoteBox, "Counselor note should be rendered before the selected profile editor").not.toBeNull()
  expect(fullNameBox, "Selected profile editor should be rendered").not.toBeNull()
  expect(counselorNoteBox!.y).toBeLessThan(fullNameBox!.y)
}

const SMOKE_VIEWS = Object.values(ADMIN_VIEWS).filter(
  (view) => view.showInPrimaryNav || view.isLegacyAlias || view.id === "traces"
)

async function expectAdminViewToLoad(page: Page, viewId: string, label: string) {
  await page.goto(`/admin?view=${viewId}&key=test-admin-key`)
  await expect(page.getByRole("heading", { name: "Career Lighthouse" })).toBeVisible()
  await expect(page.locator("header").getByText(label, { exact: true }).first()).toBeVisible()
}

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

  test("opens stale source guidance from the observability summary", async ({ page }) => {
    await page.route("**/api/kb/health", async (route) => {
      await route.fulfill({
        json: {
          total_docs: 3,
          total_chunks: 42,
          avg_match_score: 0.67,
          retrieval_diversity_score: 2.1,
          low_confidence_queries: [],
          doc_coverage: [],
          high_overlap_pairs: [],
          source_state: {
            active_sources: 2,
            superseded_sources: 1,
            stale_sources: 1,
            active_hits: 5,
            superseded_hits: 2,
            last_refreshed_at: "2026-04-22T08:05:00Z",
            stale_source_evidence: [
              {
                filename: "old-guide.pdf",
                reason: "superseded source still appears in recent retrieval results",
                chunk_count: 3,
                last_seen_at: "2026-04-21T08:00:00Z",
              },
            ],
          },
        },
      })
    })
    await page.route("**/api/kb/llm-traces?limit=25", async (route) => {
      await route.fulfill({ json: [] })
    })

    await page.goto("/admin?view=observability&key=test-admin-key")

    await expect(page.getByRole("button", { name: /Explain stale sources/i })).toBeVisible()
    await page.getByRole("button", { name: /Explain stale sources/i }).click()
    await expect(page.getByRole("dialog", { name: /Stale sources guidance/i })).toBeVisible()
    await expect(page.getByText(/Re-ingest or delete the old indexed chunks/i)).toBeVisible()
  })

  test("smokes every admin tab route", async ({ page }) => {
    await page.route("**/api/kb/facts**", async (route) => {
      const request = route.request()
      const url = new URL(request.url())
      if (url.pathname.endsWith("/api/kb/facts/grouped")) {
        await route.fulfill({
          json: {
            by: "employer",
            groups: {},
            total: 0,
            filters_applied: { include_deleted: false },
          },
        })
        return
      }
      if (url.pathname.endsWith("/api/kb/facts")) {
        await route.fulfill({
          json: {
            facts: [],
            total: 0,
            filters_applied: { include_deleted: false },
          },
        })
        return
      }
      await route.fallback()
    })

    for (const view of SMOKE_VIEWS) {
      await expectAdminViewToLoad(page, view.id, view.label)
    }
  })

  test("supports the alumni records workflow", async ({ page }) => {
    let alumni = [...ALUMNI_FIXTURE]

    await page.route("**/api/kb/alumni**", async (route) => {
      const request = route.request()
      const url = new URL(request.url())
      const method = request.method()

      if (method === "GET" && url.pathname.endsWith("/api/kb/alumni")) {
        await route.fulfill({ json: alumni })
        return
      }

      if (method === "POST" && url.pathname.endsWith("/api/kb/alumni")) {
        const body = request.postDataJSON() as Record<string, unknown>
        const saved = {
          ...body,
          slug: String(body.slug ?? "new_alumni"),
          last_updated: String(body.last_updated ?? new Date().toISOString()),
        }
        alumni = [...alumni, saved as never]
        await route.fulfill({ json: saved })
        return
      }

      if (method === "PUT" && /\/api\/kb\/alumni\/[^/]+$/.test(url.pathname)) {
        const slug = url.pathname.split("/").pop() ?? "unknown"
        const body = request.postDataJSON() as Record<string, unknown>
        const saved = {
          ...body,
          slug,
          last_updated: String(body.last_updated ?? new Date().toISOString()),
        }
        alumni = alumni.map((item) => (item.slug === slug ? (saved as never) : item))
        await route.fulfill({ json: saved })
        return
      }

      if (method === "POST" && url.pathname.endsWith("/api/kb/alumni/extract-preview")) {
        await route.fulfill({ json: ALUMNI_PREVIEW })
        return
      }

      await route.fallback()
    })

    await page.goto("/admin?view=alumni&key=test-admin-key")

    await expect(page.getByRole("heading", { name: "Alumni Records" })).toBeVisible()
    await expectCounselorNoteAboveSelectedProfile(page)
    await expect(page.getByLabel("Full name")).toHaveValue("Aditya Mehta")

    await page.getByRole("button", { name: "New Alumni" }).click()
    await page.getByLabel("Full name").fill("Maya Lim")
    await page.getByLabel("Current company").fill("Grab")
    await page.getByLabel("Current title").fill("Product Lead")
    await page.getByLabel("School").fill("SMU")
    await page.getByLabel("Degree").fill("BSc Economics")
    await page.getByLabel("Graduation year").fill("2021")
    await page.getByLabel("Available for mentoring").check()
    await page.getByRole("button", { name: "Add company link" }).click()
    await page.getByLabel("Company name").fill("Grab")
    await page.getByLabel("Company slug").fill("grab")
    await page.getByLabel("Relationship").fill("Mentor contact")
    await page.getByLabel("Company notes").fill("Can refer product students")
    await page.getByRole("button", { name: "Create alumni" }).click()

    await expect(page.getByText("Alumni profile created.")).toBeVisible()
    await expect(page.getByLabel("Full name")).toHaveValue("Maya Lim")

    await page.getByRole("button", { name: /Aditya Mehta/i }).click()
    await expect(page.getByLabel("Full name")).toHaveValue("Aditya Mehta")
    await expectCounselorNoteAboveSelectedProfile(page)

    await page.getByLabel("Counselor note").fill("Maya can mentor product students at Grab.")
    await page.getByRole("button", { name: "Preview extraction" }).click()

    await expect(page.getByText("The alumnus helps with compliance and risk referrals.")).toBeVisible()
    await expect(page.getByText("Suggested profile changes")).toBeVisible()
    await expect(page.getByText("Suggested company links")).toBeVisible()
  })

  test("keeps employer saves visible and blocks switching while edits are unsaved", async ({ page }) => {
    await page.route("**/api/kb/employers**", async (route) => {
      const request = route.request()
      const url = new URL(request.url())
      const method = request.method()

      if (method === "GET" && url.pathname.endsWith("/api/kb/employers")) {
        await route.fulfill({ json: [EMPLOYER_FIXTURE, EMPLOYER_FIXTURE_2] })
        return
      }

      if (method === "GET" && url.pathname.endsWith("/api/kb/career-profiles")) {
        await route.fulfill({
          json: [
            { slug: "investment_banking", career_type: "Investment Banking" },
          ],
        })
        return
      }

      await route.fallback()
    })

    await page.goto("/admin?view=employers&key=test-admin-key")

    await expect(page.getByRole("heading", { name: "Employer Fact Library" })).toBeVisible()
    await page.getByText("Goldman Sachs", { exact: true }).first().click()
    await page.getByRole("button", { name: /^Facts/i }).click()

    const saveButton = page.getByRole("button", { name: /Save employer updates/i })
    await expect(saveButton).toBeVisible()

    const rightScrollArea = page.locator("div.overflow-y-auto").last()
    await rightScrollArea.evaluate((el) => {
      const node = el as HTMLElement
      node.scrollTop = node.scrollHeight
    })
    await expect(saveButton).toBeVisible()

    await page.getByRole("button", { name: /\+ New fact/i }).click()
    const factNameInput = page.getByPlaceholder("e.g., Aditya Mehta")
    await expect(factNameInput).toBeVisible()
    await factNameInput.fill("Ariana Tan")
    await page.getByRole("button", { name: /Add fact/i }).click()

    await page.getByText("Morgan Stanley", { exact: true }).first().click()

    await expect(page.getByText(/Save or discard before opening Morgan Stanley/i)).toBeVisible()
    await expect(page.getByRole("heading", { name: "Goldman Sachs" })).toBeVisible()
    await expect(page.getByRole("heading", { name: "Morgan Stanley" })).toHaveCount(0)
  })
})
