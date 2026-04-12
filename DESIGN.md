# Design System — Career Lighthouse

## Product Context
- **What this is:** An AI-powered career advising product for universities. Counselors review and publish institutional knowledge, and students get locally grounded career answers that read clearly.
- **Who it's for:** University career offices, counselors, and students using the advising experience from different sides of the same system.
- **Space/industry:** Career advising, university services, internal knowledge workflow software.
- **Project type:** Web app with a task-heavy admin workspace and a student-facing conversational interface.

## Aesthetic Direction
- **Direction:** Editorial utilitarian
- **Decoration level:** Intentional
- **Mood:** Calm, credible, and language-first. The product should feel like an advising desk with judgment, not a generic dashboard and not a cheerful edtech portal.
- **Reference sites:** Category research pointed at the usual institutional-career-tool baseline. The design intentionally avoids the default blue portal look those products converge on.

## Typography
- **Display/Hero:** `Fraunces` — gives the product an authored, thoughtful voice and creates stronger hierarchy for student and counselor entry points.
- **Body:** `Instrument Sans` — handles long reading sessions and dense admin surfaces without feeling clinical or overused.
- **UI/Labels:** `Instrument Sans` — keeps controls, helper copy, and panels consistent with the body face.
- **Data/Tables:** `IBM Plex Mono` — use for timestamps, version history, statuses, diffs, and metadata. Prefer tabular numerals.
- **Code:** `IBM Plex Mono`
- **Loading:** Google Fonts or self-host the same families later if deployment policy requires it. No paid font licensing assumed.
- **Scale:**
  - `display-xl`: 72px / 0.96 / `Fraunces`
  - `display-lg`: 52px / 0.98 / `Fraunces`
  - `display-md`: 36px / 1.0 / `Fraunces`
  - `title-lg`: 28px / 1.1 / `Fraunces`
  - `title-md`: 22px / 1.15 / `Instrument Sans`
  - `body-lg`: 18px / 1.6 / `Instrument Sans`
  - `body-md`: 16px / 1.55 / `Instrument Sans`
  - `body-sm`: 14px / 1.5 / `Instrument Sans`
  - `meta`: 12px / 1.4 / `IBM Plex Mono`

## Color
- **Approach:** Restrained
- **Primary:** `#0F766E` — primary action color, selected states, active highlights, and trusted forward motion.
- **Secondary:** `#B45309` — editorial warmth, lifecycle emphasis, and occasional supporting accents.
- **Neutrals:** Warm neutrals, not cold grayscale
  - `canvas`: `#F6F1E8`
  - `surface`: `#FFFDFC`
  - `surface-2`: `#F0E7DB`
  - `line`: `#D8D0C4`
  - `ink`: `#1F2937`
  - `muted`: `#5F6B76`
- **Semantic:**
  - success: `#2F6B4F`
  - warning: `#A16207`
  - error: `#B42318`
  - info: `#0F766E`
- **Dark mode:** Rebuild surfaces rather than inverting them. Use charcoal surfaces, keep warm text, reduce accent saturation slightly, and preserve the teal as the main action color without neon intensity.

## Spacing
- **Base unit:** 8px
- **Density:** Comfortable
- **Scale:** `2xs(4) xs(8) sm(12) md(16) lg(24) xl(32) 2xl(48) 3xl(64)`

## Layout
- **Approach:** Hybrid
- **Grid:** 12 columns on desktop app shells, 8 columns on tablet, 4 columns on mobile
- **Max content width:** `1260px` for admin, `760px` for student reading surfaces
- **Border radius:**
  - `sm`: 8px
  - `md`: 14px
  - `lg`: 22px
  - `pill`: 9999px

## Motion
- **Approach:** Minimal-functional
- **Easing:** enter(`ease-out`) exit(`ease-in`) move(`ease-in-out`)
- **Duration:** micro(`80ms`) short(`160ms`) medium(`260ms`) long(`420ms`)

## Component Rules
- Build the admin side around a primary workspace, not a grid of equal-weight cards.
- Use cards only when the card is the interaction. Do not wrap every section in decorative boxes out of habit.
- Page headings should state the job to be done, not the internal module name.
- Student answers should look authored: generous line-height, visible markdown hierarchy, and citations that feel attached but not noisy.
- Track lifecycle states must be obvious at a glance. Use banners and reference summaries, not tiny badges.
- Keep chrome quiet. Typography and spacing should do more work than borders and fills.

## Responsive & Accessibility
- Preserve the session-first hierarchy on mobile. Do not hide the main work behind an information-scent-free hamburger as the first move.
- Keep all primary actions at least 44px high.
- Use visible focus states on every interactive element.
- Maintain WCAG AA contrast for text, helper copy, and status treatments.
- On narrow screens, stack SmartCanvas and Track Builder intentionally. The selected work should stay visible before secondary context.
- Links in student markdown should open safely in a new tab and remain visually obvious.

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-12 | Replaced the old Tailwind snapshot with a fresh design system | The product is moving to a session-first, reading-heavy UX and needed a stronger visual point of view |
| 2026-04-12 | Chose `Fraunces`, `Instrument Sans`, and `IBM Plex Mono` | Free fonts, stronger identity, and better fit for editorial guidance plus workflow precision |
| 2026-04-12 | Chose warm neutrals with teal as the primary action color | Keeps trust and clarity while avoiding the generic institutional blue portal look |
