# Career Lighthouse — Design System

Inferred from existing components (Sprint 1 + Sprint 2). Documented 2026-03-24.

## Palette

| Token | Tailwind | Usage |
|-------|----------|-------|
| Primary | `bg-blue-600 text-white` | Action buttons, selected states, user chat bubbles |
| Primary hover | `hover:bg-blue-700` | Hover state on primary buttons |
| Primary light | `bg-blue-50 text-blue-700 border-blue-200` | Citation badges, hover on cards |
| Selected pill | `bg-blue-600 text-white border-blue-600` | Active pill in pill selectors |
| Focus ring | `focus:outline-none focus:ring-2 focus:ring-blue-400` | All interactive elements |
| Muted text | `text-gray-500` | Subtitles, descriptions, helper text |
| Placeholder text | `text-gray-400` | Empty state text, disabled labels |
| Label text | `text-gray-700` | Form field labels |
| Body text | `text-gray-800` | Button labels, card titles |
| Border | `border-gray-200` | Card borders |
| Border (inputs) | `border-gray-300` | Form inputs, pill borders |
| Success | `text-green-700 bg-green-50 border-green-200` | Resume loaded state |
| Error | inline assistant message | Chat fetch errors |

## Typography

- Page title: `text-2xl font-bold`
- Section label: `text-sm font-medium text-gray-700`
- Body / button: `text-sm`
- Caption / meta: `text-xs`

## Spacing & Layout

- Page container: `max-w-2xl mx-auto p-6` (student), `max-w-6xl mx-auto p-6` (admin)
- Card padding: `p-4`
- Section spacing: `space-y-6` (forms), `gap-3` (card grids)

## Shape

- Cards / buttons: `rounded-xl`
- Pill buttons: `rounded-full`
- Small badges / inputs: `rounded` or `rounded-lg`
- Chat bubbles: `rounded-2xl`

## Interactive Elements

**Touch targets:** Minimum 44px height on all tappable elements.
- Primary buttons: `py-3`
- Pill buttons: `py-2.5`
- Skip / back text links: `py-2 px-2`

**Focus:** All interactive elements use `focus:outline-none focus:ring-2 focus:ring-blue-400`.

**Disabled state:** `disabled:opacity-40` on buttons with `disabled` prop.

## Component Vocabulary

| Component | Usage |
|-----------|-------|
| Card button | GuidedEntry options — `p-4 border rounded-xl hover:border-blue-400 hover:bg-blue-50` |
| Pill selector | Single-select groups in IntakeFlow — `rounded-full text-sm border` |
| Primary CTA | Full-width form submit — `w-full py-3 bg-blue-600 rounded-xl` |
| Career badge | Active track indicator — `rounded-full text-xs bg-blue-100 text-blue-700` |
| Citation badge | KB source reference — `rounded text-xs bg-blue-50 border-blue-200` |
| Chat bubble (user) | `bg-blue-600 text-white rounded-2xl` |
| Chat bubble (AI) | `bg-white border rounded-2xl` |

## Responsive Rules

- Student page is `max-w-2xl` — narrower than admin, mobile-first feel
- GuidedEntry card grid: `grid-cols-1 sm:grid-cols-2` (single column on small phones)
- IntakeFlow pill groups: `flex flex-wrap` — wraps naturally
- Page header hides after guided_entry state to maximize vertical space for interaction
