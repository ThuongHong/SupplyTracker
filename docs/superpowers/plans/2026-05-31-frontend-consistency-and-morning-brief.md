# Frontend Consistency + Real Morning Brief Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify the whole SupplyTracker frontend onto the editorial design system and replace the hardcoded "Morning Brief" hero with a real, LLM-generated decision brief.

**Architecture:** Add reusable editorial component classes to `index.css` (built from existing CSS tokens), rewrite the shared UI + chart + chatbot components to use them (deleting all `dark:` variants since tokens auto-invert via `[data-theme]`), restyle the two detail views to "ruled sections, no boxes". Separately, add a `GET /api/v1/brief` endpoint that calls the existing `get_decision_brief()`, a frontend `fetchBrief()` client, and rewire the Overview hero to skeleton-then-swap the real markdown brief with a templated fallback. Drop the broken `AlertsRail`.

**Tech Stack:** React 18 + TypeScript + Vite + Tailwind 3 (frontend, vitest); FastAPI + SQLAlchemy + Redis + pytest (backend). Markdown via `react-markdown` + `remark-gfm` (already deps).

---

## Conventions used in this plan

- **Frontend dir:** all `npm` commands run from `frontend/`.
- **Backend tests:** run from repo root via `make test` (`docker compose exec -w /app/backend backend python -m pytest -q`) OR, if working outside Docker, `cd backend && python -m pytest -q`. This plan writes `cd backend && python -m pytest …` — adapt to `make test` if the stack is containerized.
- **Lint (frontend):** `cd frontend && npm run lint` (runs `tsc --noEmit`).
- **Visual check:** `make up`, then open `http://localhost:5173`.
- API prefix is `/api/v1` (set in `backend/app/main.py:38`).

## Token swap dictionary (THE reference for every restyle task)

Every "token swap" task replaces generic Tailwind with these exact equivalents and **deletes the `dark:` twin** (the CSS tokens already invert under `[data-theme="dark"]`). When a Tailwind color has no class form below, use the arbitrary-value form `text-[color:var(--token)]` / `bg-[color:var(--token)]` / `border-[color:var(--token)]`.

| Generic Tailwind | Editorial replacement |
|---|---|
| `bg-white` / `dark:bg-gray-800` | `bg-[color:var(--card)]` |
| `bg-gray-50` / `dark:bg-gray-900` | `bg-[color:var(--paper)]` |
| `bg-gray-100` / `dark:bg-gray-700` (subtle fill) | `bg-[color:var(--paper-2)]` |
| `text-gray-900` / `dark:text-gray-100` | `text-[color:var(--ink)]` |
| `text-gray-700` / `dark:text-gray-300` | `text-[color:var(--ink-2)]` |
| `text-gray-500` / `dark:text-gray-400` | `text-[color:var(--ink-3)]` |
| `text-gray-400` / `dark:text-gray-500` | `text-[color:var(--ink-4)]` |
| `border-gray-200` / `dark:border-gray-700` | `border-[color:var(--rule-thin)]` |
| `border-gray-300` / `dark:border-gray-600` | `border-[color:var(--rule-thin)]` |
| `text-indigo-600` / `dark:text-indigo-400` | `text-[color:var(--accent)]` |
| `bg-indigo-500` / `border-indigo-500` | `bg-[color:var(--accent)]` / `border-[color:var(--accent)]` |
| `focus:ring-2 focus:ring-indigo-500` (+`focus:outline-none`) | `focus-ring` (new class, Task 1) |
| `text-amber-500` (star) | `text-[color:var(--caution)]` |
| `text-red-600` / `dark:text-red-400` | `text-[color:var(--negative)]` |
| `text-green-700` / `dark:text-green-400` | `text-[color:var(--positive)]` |
| `rounded-xl` / `rounded-lg` (panels) | (remove — editorial is square; keep `rounded-full` only for dots/pills) |
| `shadow-sm` | (remove) |
| literal chart hex `#6366f1` | `var(--accent)` |
| literal chart hex `#22c55e` | `var(--positive)` |

> Severity color map (used by Badge/pill): `low→--positive`, `moderate→--caution`, `elevated→--caution`, `high→--negative`, `critical→--negative`, `unknown→--ink-4`, `info→--accent`. This matches `StatusDot.tsx`, which is **already** token-based (no change needed there).

---

## Phase 1 — Design system

### Task 1: Add editorial component classes to `index.css`

**Files:**
- Modify: `frontend/src/index.css` (append inside the existing `@layer utilities { … }` block, before its closing brace at line ~246)

- [ ] **Step 1: Add the classes**

Insert the following just before the final `}` of `@layer utilities` (after the `.sidebar-width-collapsed` / media-query rules, around line 245):

```css
  /* ── Editorial component classes (migration target) ───────────────────── */

  .focus-ring:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  .card {
    background: var(--card);
    border: 1px solid var(--rule-thin);
  }

  .card--inside {
    background: transparent;
    border: 1px solid var(--rule-hair);
  }

  .card__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    padding: 0.75rem 0.9rem;
    border-bottom: 1px solid var(--rule-hair);
  }

  .card__title {
    font-family: var(--f-ui);
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0;
    color: var(--ink-3);
  }

  .tab {
    margin-bottom: -1px;
    border-bottom: 2px solid transparent;
    padding: 0.5rem 1rem;
    font-family: var(--f-ui);
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--ink-3);
    background: transparent;
    cursor: pointer;
  }

  .tab:hover {
    color: var(--ink);
  }

  .tab--active {
    border-bottom-color: var(--accent);
    color: var(--ink);
  }

  .seg {
    display: inline-flex;
    border: 1px solid var(--rule-thin);
    background: var(--card);
  }

  .seg__btn {
    padding: 0.35rem 0.75rem;
    font-family: var(--f-ui);
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--ink-3);
    background: transparent;
    cursor: pointer;
  }

  .seg__btn + .seg__btn {
    border-left: 1px solid var(--rule-thin);
  }

  .seg__btn--active {
    background: var(--ink);
    color: var(--paper);
  }

  .pill {
    display: inline-flex;
    align-items: center;
    padding: 0.1rem 0.5rem;
    font-family: var(--f-ui);
    font-size: 0.72rem;
    font-weight: 600;
    border-radius: 999px;
    white-space: nowrap;
  }

  .pill--low {
    color: var(--positive);
    background: color-mix(in srgb, var(--positive) 14%, transparent);
  }

  .pill--moderate,
  .pill--elevated {
    color: var(--caution);
    background: color-mix(in srgb, var(--caution) 16%, transparent);
  }

  .pill--high,
  .pill--critical {
    color: var(--negative);
    background: color-mix(in srgb, var(--negative) 14%, transparent);
  }

  .pill--info {
    color: var(--accent);
    background: color-mix(in srgb, var(--accent) 14%, transparent);
  }

  .pill--unknown,
  .pill--default {
    color: var(--ink-3);
    background: color-mix(in srgb, var(--ink-4) 16%, transparent);
  }

  .spinner {
    display: inline-block;
    border-radius: 999px;
    border: 2px solid var(--rule-thin);
    border-top-color: var(--accent);
    animation: spin 0.7s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
```

- [ ] **Step 2: Verify the build still compiles**

Run: `cd frontend && npm run lint`
Expected: PASS (no TS errors — CSS is not type-checked, this just confirms nothing else broke).

- [ ] **Step 3: Verify Tailwind processes the new CSS**

Run: `cd frontend && npm run build`
Expected: build succeeds, no PostCSS/Tailwind errors about the `@layer` block.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/index.css
git commit -m "feat(ui): add editorial component classes (card/tab/seg/pill/spinner)"
```

---

## Phase 2 — Shared UI components

> Each task rewrites one component's internals using Task 1 classes + the swap dictionary. Public props stay identical. After each, run `npm run lint` and `npm run test` to confirm no regression, since views import these.

### Task 2: Migrate `ui/Card`

**Files:**
- Modify: `frontend/src/components/ui/Card.tsx`

- [ ] **Step 1: Add an `inside` prop and rewrite the markup**

Replace the entire file with:

```tsx
import React from 'react'

interface CardProps {
  children: React.ReactNode
  className?: string
  /** Optional title rendered above content */
  title?: string
  /** Optional actions rendered in the top-right corner */
  actions?: React.ReactNode
  padding?: 'none' | 'sm' | 'md' | 'lg'
  /** Flatter "inside page" variant for detail pages (hair border, transparent bg) */
  inside?: boolean
}

const paddingClasses: Record<NonNullable<CardProps['padding']>, string> = {
  none: '',
  sm: 'p-3',
  md: 'p-4',
  lg: 'p-6',
}

export function Card({
  children,
  className = '',
  title,
  actions,
  padding = 'md',
  inside = false,
}: CardProps) {
  return (
    <div className={[inside ? 'card--inside' : 'card', className].join(' ')}>
      {(title || actions) && (
        <div className="card__head">
          {title && <h3 className="card__title">{title}</h3>}
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
      )}
      <div className={paddingClasses[padding]}>{children}</div>
    </div>
  )
}
```

- [ ] **Step 2: Lint + test**

Run: `cd frontend && npm run lint && npm run test`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ui/Card.tsx
git commit -m "refactor(ui): Card uses editorial .card classes + inside variant"
```

### Task 3: Migrate `ui/Badge` + `SeverityBadge`

**Files:**
- Modify: `frontend/src/components/ui/Badge.tsx`

- [ ] **Step 1: Replace the Tailwind variant map with pill classes**

Replace the entire file with:

```tsx
import React from 'react'

export type Severity = 'low' | 'moderate' | 'elevated' | 'high' | 'critical' | 'unknown'
export type BadgeVariant = Severity | 'default' | 'info'

interface BadgeProps {
  children: React.ReactNode
  variant?: BadgeVariant
  className?: string
}

const variantClass: Record<BadgeVariant, string> = {
  default: 'pill--default',
  info: 'pill--info',
  low: 'pill--low',
  elevated: 'pill--elevated',
  moderate: 'pill--moderate',
  high: 'pill--high',
  critical: 'pill--critical',
  unknown: 'pill--unknown',
}

export function Badge({ children, variant = 'default', className = '' }: BadgeProps) {
  return <span className={['pill', variantClass[variant], className].join(' ')}>{children}</span>
}

/** Convenience: render a severity value as a labeled badge */
export function normalizeSeverity(severity: string | null | undefined): Severity {
  if (severity === 'critical' || severity === 'high' || severity === 'moderate' || severity === 'elevated' || severity === 'low') {
    return severity
  }
  return 'unknown'
}

export function SeverityBadge({ severity }: { severity: string | null | undefined }) {
  const normalized = normalizeSeverity(severity)
  const labels: Record<Severity, string> = {
    low: 'Low',
    elevated: 'Elevated',
    moderate: 'Moderate',
    high: 'High',
    critical: 'Critical',
    unknown: 'Unknown',
  }
  return <Badge variant={normalized}>{labels[normalized]}</Badge>
}
```

- [ ] **Step 2: Lint + test**

Run: `cd frontend && npm run lint && npm run test`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ui/Badge.tsx
git commit -m "refactor(ui): Badge/SeverityBadge use .pill token classes"
```

### Task 4: Migrate `ui/Tabs`

**Files:**
- Modify: `frontend/src/components/ui/Tabs.tsx`

- [ ] **Step 1: Replace the `return` markup**

Replace the `return ( … )` block with:

```tsx
  return (
    <div role="tablist" className="flex gap-1 border-b border-[color:var(--rule-thin)]">
      {tabs.map((t) => {
        const selected = t.key === active
        return (
          <button
            key={t.key}
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(t.key)}
            className={['tab focus-ring', selected ? 'tab--active' : ''].join(' ')}
          >
            {t.label}
          </button>
        )
      })}
    </div>
  )
```

- [ ] **Step 2: Lint + test**

Run: `cd frontend && npm run lint && npm run test`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ui/Tabs.tsx
git commit -m "refactor(ui): Tabs use .tab token classes"
```

### Task 5: Migrate `ui/WindowPicker`

**Files:**
- Modify: `frontend/src/components/ui/WindowPicker.tsx`

- [ ] **Step 1: Replace the `return` markup**

Replace the `return ( … )` block with:

```tsx
  return (
    <div className="seg">
      {options.map((opt) => (
        <button
          key={opt}
          onClick={() => onChange(opt)}
          className={['seg__btn focus-ring', opt === value ? 'seg__btn--active' : ''].join(' ')}
        >
          {opt}
        </button>
      ))}
    </div>
  )
```

- [ ] **Step 2: Lint + test**

Run: `cd frontend && npm run lint && npm run test`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ui/WindowPicker.tsx
git commit -m "refactor(ui): WindowPicker uses .seg segmented control"
```

### Task 6: Migrate `ui/DataState`

**Files:**
- Modify: `frontend/src/components/ui/DataState.tsx`

- [ ] **Step 1: Replace the spinner**

In `LoadingSpinner`, replace the entire `<svg className="animate-spin …"> … </svg>` element with:

```tsx
      <span className="spinner h-8 w-8 mb-3" aria-hidden="true" />
```

- [ ] **Step 2: Swap remaining colors per the dictionary**

Apply these exact replacements in the file:
- "Loading…" `<p>` and `EmptyState` message `<p>`: `text-gray-500 dark:text-gray-400` → `text-[color:var(--ink-3)]`
- `ErrorState` wrapper `bg-red-50 dark:bg-red-900/30` → `bg-[color:var(--card)]`
- `ErrorState` icon `text-red-600 dark:text-red-400` → `text-[color:var(--negative)]`
- `ErrorState` heading `text-gray-900 dark:text-gray-100` → `text-[color:var(--ink)]`
- `ErrorState` message `text-gray-500 dark:text-gray-400` → `text-[color:var(--ink-3)]`
- `ErrorState` retry button `text-indigo-600 dark:text-indigo-400 hover:underline focus:outline-none focus:ring-2 focus:ring-indigo-500 rounded` → `text-[color:var(--accent)] hover:underline focus-ring`
- `EmptyState` wrapper `bg-gray-100 dark:bg-gray-700` → `bg-[color:var(--paper-2)]`
- `EmptyState` icon `text-gray-400 dark:text-gray-500` → `text-[color:var(--ink-4)]`

- [ ] **Step 3: Confirm no stragglers**

Run: `cd frontend && grep -nE "dark:|text-gray|bg-gray|indigo|red-50|red-900|red-600|red-400|animate-spin" src/components/ui/DataState.tsx`
Expected: no output.

- [ ] **Step 4: Lint + test**

Run: `cd frontend && npm run lint && npm run test`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/DataState.tsx
git commit -m "refactor(ui): DataState uses .spinner + editorial tokens"
```

### Task 7: Migrate remaining `ui/*` (RiskKpis, InsightRow, AreaChart, AskAIButton, InfoTooltip, MiniMap)

**Files:**
- Modify: `frontend/src/components/ui/RiskKpis.tsx`
- Modify: `frontend/src/components/ui/InsightRow.tsx`
- Modify: `frontend/src/components/ui/AreaChart.tsx`
- Modify: `frontend/src/components/ui/AskAIButton.tsx`
- Modify: `frontend/src/components/ui/InfoTooltip.tsx`
- Modify: `frontend/src/components/ui/MiniMap.tsx`

> `ui/StatusDot.tsx` is already token-based — do NOT touch it.

- [ ] **Step 1: Apply the swap dictionary to each file**

Replace every dictionary class, deleting `dark:` twins. Known hits:
- `RiskKpis.tsx` `KpiCard`: `rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4` → `card p-4`; label `text-gray-500 dark:text-gray-400` → `text-[color:var(--ink-3)]`; value `text-gray-900 dark:text-gray-100` → `text-[color:var(--ink)]`. In `DeltaBadge`, any `text-green-*` → `text-[color:var(--positive)]`, `text-red-*` → `text-[color:var(--negative)]`.
- `AreaChart.tsx`: axis/grid `stroke` literal grays → `var(--rule-hair)`; series `#6366f1` → `var(--accent)`; any tick/label gray text → `var(--ink-3)`.
- `AskAIButton.tsx`, `InfoTooltip.tsx`, `InsightRow.tsx`, `MiniMap.tsx`: straight dictionary swaps; `focus:outline-none focus:ring-2 focus:ring-indigo-500` → `focus-ring`.

- [ ] **Step 2: Confirm no stragglers**

Run: `cd frontend && grep -nE "dark:|text-gray|bg-gray|bg-white|indigo|ring-indigo|#6366f1" src/components/ui/RiskKpis.tsx src/components/ui/InsightRow.tsx src/components/ui/AreaChart.tsx src/components/ui/AskAIButton.tsx src/components/ui/InfoTooltip.tsx src/components/ui/MiniMap.tsx`
Expected: no output.

- [ ] **Step 3: Lint + test**

Run: `cd frontend && npm run lint && npm run test`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/
git commit -m "refactor(ui): migrate remaining shared UI to editorial tokens"
```

---

## Phase 3 — Charts, feature & chatbot components

### Task 8: Migrate chart components

**Files:**
- Modify: `frontend/src/components/charts/AnomalyCard.tsx`
- Modify: `frontend/src/components/charts/EntitySummary.tsx`
- Modify: `frontend/src/components/charts/IndicesPanel.tsx`
- Modify: `frontend/src/components/charts/VesselMixChart.tsx`
- Modify: `frontend/src/components/MacroSensitivity.tsx`

- [ ] **Step 1: Apply swap dictionary + chart hex swap to each**

Replace dictionary classes, delete `dark:` twins, and swap literal chart hex: `#6366f1`→`var(--accent)`, `#22c55e`→`var(--positive)`, any red hex→`var(--negative)`, any amber hex→`var(--caution)`.

- [ ] **Step 2: Confirm no stragglers**

Run: `cd frontend && grep -nE "dark:|text-gray|bg-gray|bg-white|indigo|#6366f1|#22c55e" src/components/charts/AnomalyCard.tsx src/components/charts/EntitySummary.tsx src/components/charts/IndicesPanel.tsx src/components/charts/VesselMixChart.tsx src/components/MacroSensitivity.tsx`
Expected: no output.

- [ ] **Step 3: Lint + test**

Run: `cd frontend && npm run lint && npm run test`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/charts/ frontend/src/components/MacroSensitivity.tsx
git commit -m "refactor(charts): migrate chart components to editorial tokens"
```

### Task 9: Migrate `EventLog` + `MarketBrief`

**Files:**
- Modify: `frontend/src/components/EventLog.tsx`
- Modify: `frontend/src/components/MarketBrief.tsx`

- [ ] **Step 1: Swap dictionary in both**

Apply the dictionary. In `MarketBrief.tsx` the trade-KPI card `rounded-lg border border-[color:var(--rule-thin)] bg-[color:var(--card)] px-4 py-3` → `card px-4 py-3`. Update AreaChart series colors `#6366f1`/`#22c55e` → `var(--accent)`/`var(--positive)`.

- [ ] **Step 2: Update the misleading doc comment in `MarketBrief.tsx`**

Replace the doc-comment block (lines ~26–30) with:

```tsx
/**
 * Growth & Market Insights, folded into the Overview page. Shows the market-desk
 * AI summary, trade-growth KPIs, the import/export trend, and the freight/bunker
 * panel. (The page's Morning Brief hero is a separate, dedicated decision brief.)
 */
```

- [ ] **Step 3: Confirm no stragglers**

Run: `cd frontend && grep -nE "dark:|text-gray|bg-gray|bg-white|indigo|#6366f1|#22c55e" src/components/EventLog.tsx src/components/MarketBrief.tsx`
Expected: no output.

- [ ] **Step 4: Lint + test**

Run: `cd frontend && npm run lint && npm run test`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/EventLog.tsx frontend/src/components/MarketBrief.tsx
git commit -m "refactor: migrate EventLog + MarketBrief to editorial tokens"
```

### Task 10: Migrate `ChatbotWidget` + `ChatMarkdown`

**Files:**
- Modify: `frontend/src/components/ChatbotWidget.tsx`
- Modify: `frontend/src/components/ChatMarkdown.tsx`

> `AskAIButton` was already migrated in Task 7.

- [ ] **Step 1: Swap dictionary in `ChatbotWidget.tsx`**

Apply the dictionary throughout (panel bg, borders, message bubbles, input, send button focus rings).

- [ ] **Step 2: Swap colors in `ChatMarkdown.tsx`**

Exact replacements:
- `a`: `text-indigo-600 dark:text-indigo-400 underline` → `text-[color:var(--accent)] underline`
- `li`: `marker:text-gray-400` → `marker:text-[color:var(--ink-4)]`
- inline `code`: `bg-black/10 dark:bg-white/10` → `bg-[color:var(--paper-2)]`
- `pre`: `overflow-x-auto rounded-lg bg-black/10 dark:bg-white/10 p-2 text-[0.85em]` → `overflow-x-auto bg-[color:var(--paper-2)] p-2 text-[0.85em]`
- `th` and `td`: `border-gray-300 dark:border-gray-600` → `border-[color:var(--rule-thin)]`

- [ ] **Step 3: Confirm no stragglers**

Run: `cd frontend && grep -nE "dark:|text-gray|bg-gray|bg-white|indigo|black/10|white/10" src/components/ChatbotWidget.tsx src/components/ChatMarkdown.tsx`
Expected: no output.

- [ ] **Step 4: Lint + test**

Run: `cd frontend && npm run lint && npm run test`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ChatbotWidget.tsx frontend/src/components/ChatMarkdown.tsx
git commit -m "refactor(chat): migrate chatbot widget + markdown to editorial tokens"
```

---

## Phase 4 — Detail views (ruled, no boxes)

### Task 11: Restyle `PortDetailView`

**Files:**
- Modify: `frontend/src/views/PortDetailView.tsx`

- [ ] **Step 1: Restyle the header (all three returns: loading, error, main)**

- back button: `p-1.5 rounded-md text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-colors` → `p-1.5 text-[color:var(--ink-3)] hover:text-[color:var(--ink)] focus-ring`
- title `h1`: `text-xl font-semibold text-gray-900 dark:text-gray-100` → `serif text-3xl text-[color:var(--ink)]`
- sub-line `p`: `text-sm text-gray-500 dark:text-gray-400 mt-0.5` → `text-sm text-[color:var(--ink-3)] mt-0.5`
- sync + untrack buttons: `border-gray-200 dark:border-gray-600 … hover:bg-gray-50 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-500` → `border-[color:var(--rule-thin)] … hover:bg-[color:var(--paper-2)] focus-ring`; star icon `text-amber-500` → `text-[color:var(--caution)]`; refresh icon `text-gray-400` → `text-[color:var(--ink-4)]`
- loading/error `<Card><DataState …/></Card>` → `<div className="card p-4"><DataState …/></div>`

- [ ] **Step 2: Convert content `<Card title="X">` blocks to ruled sections**

For each content card (Related News, Location, Metric Breakdown, Macro sensitivity, Vessel Mix, Narrative, Insights), replace `<Card title="X"> … </Card>` with:

```tsx
      <section className="space-y-4">
        <div className="section__head">
          <div>
            <p className="label-cap">EYEBROW</p>
            <h2 className="serif text-2xl">X</h2>
          </div>
        </div>
        {/* original Card children, unchanged */}
      </section>
```

Use a short EYEBROW per section (e.g. "Geography" for Location, "Drill-down" for Metric Breakdown, "Sensitivity" for Macro, "Fleet" for Vessel Mix, "Desk note" for Narrative, "Signals" for Insights, "News" for Related News).

**Exception — frame the map only:** wrap `MiniMap` as `<Card title="Location" inside> <MiniMap … /> </Card>` (flat variant) instead of a bare section.

- [ ] **Step 3: Convert the `MetricDrilldown` select + inline text**

- `<select … className="text-sm rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-500">` → `className="ui text-sm border border-[color:var(--rule-thin)] bg-[color:var(--card)] text-[color:var(--ink-2)] px-3 py-1.5 focus-ring"`
- label `text-gray-700 dark:text-gray-300` → `text-[color:var(--ink-2)]`
- "Latest:" span `text-gray-900 dark:text-gray-100` → `text-[color:var(--ink)]`
- Narrative `<p>` `text-gray-700 dark:text-gray-300` → `text-[color:var(--ink-2)]`

- [ ] **Step 4: Confirm no stragglers**

Run: `cd frontend && grep -nE "dark:|text-gray|bg-gray|bg-white|indigo|ring-indigo|amber-500" src/views/PortDetailView.tsx`
Expected: no output.

- [ ] **Step 5: Lint + test**

Run: `cd frontend && npm run lint && npm run test`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/PortDetailView.tsx
git commit -m "refactor(views): PortDetailView ruled-section editorial layout"
```

### Task 12: Restyle `ChokepointDetailView`

**Files:**
- Modify: `frontend/src/views/ChokepointDetailView.tsx`

- [ ] **Step 1: Apply the same transforms as Task 11 (Steps 1–3)**

`ChokepointDetailView` mirrors `PortDetailView` (header → Tabs → KpiStrip → EntitySummary → MiniMap → BreakdownChart → AnomalyCard → MacroSensitivity → VesselMixChart → Narrative → Insights). Apply the identical header restyle, `<Card title="…">` → ruled `<section>` conversion (map keeps `<Card … inside>`), and select/label/narrative color swaps. Read the file first to confirm which exact cards exist, then transform each.

- [ ] **Step 2: Confirm no stragglers**

Run: `cd frontend && grep -nE "dark:|text-gray|bg-gray|bg-white|indigo|ring-indigo|amber-500" src/views/ChokepointDetailView.tsx`
Expected: no output.

- [ ] **Step 3: Lint + test**

Run: `cd frontend && npm run lint && npm run test`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/ChokepointDetailView.tsx
git commit -m "refactor(views): ChokepointDetailView ruled-section editorial layout"
```

---

## Phase 5 — Backend: real brief endpoint

### Task 13: Add a redis dependency

**Files:**
- Modify: `backend/app/api/deps.py`

- [ ] **Step 1: Add the import + `get_redis` + `RedisClient`**

Add `import redis as redis_lib` to the top import block, then append to the file:

```python
# ---------------------------------------------------------------------------
# Redis dependency
# ---------------------------------------------------------------------------


def get_redis() -> redis_lib.Redis:
    """Return a Redis client built from settings.redis_url.

    ``from_url`` is lazy — it does not open a socket until first use — so this is
    cheap to construct per request and trivial to override in tests.
    """
    settings = get_settings()
    return redis_lib.Redis.from_url(settings.redis_url, decode_responses=True)


RedisClient = Annotated[redis_lib.Redis, Depends(get_redis)]
```

- [ ] **Step 2: Verify import resolves**

Run: `cd backend && python -c "from app.api.deps import get_redis, RedisClient; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/deps.py
git commit -m "feat(api): add get_redis dependency"
```

### Task 14: Add the brief schema

**Files:**
- Create: `backend/app/schemas/brief.py`

- [ ] **Step 1: Write the schema**

```python
from __future__ import annotations

from pydantic import BaseModel


class BriefResponse(BaseModel):
    brief: str
    as_of: str
```

- [ ] **Step 2: Verify import**

Run: `cd backend && python -c "from app.schemas.brief import BriefResponse; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/brief.py
git commit -m "feat(api): add BriefResponse schema"
```

### Task 15: Write the failing brief-route test

**Files:**
- Create: `backend/tests/api/test_brief.py`

- [ ] **Step 1: Write the test**

```python
"""Contract tests for GET /api/v1/brief."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_redis
from app.db.session import get_db
from app.main import app


@pytest.fixture()
def mock_session():
    return MagicMock()


@pytest.fixture()
def mock_redis():
    return MagicMock()


@pytest.fixture()
def client(mock_session, mock_redis):
    def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: mock_redis
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _story_event() -> MagicMock:
    e = MagicMock()
    e.event_key = "evt-1"
    e.severity = "critical"
    e.entity_name = "Suez Canal"
    e.entity_type = "chokepoint"
    e.event_type = "transit_disruption"
    e.narrative = "Transit halted"
    e.event_time = datetime(2026, 5, 30, 9, 0, tzinfo=timezone.utc)
    return e


def _insight() -> MagicMock:
    i = MagicMock()
    i.attention_level = "high"
    i.title = "LA congestion"
    i.narrative = "Dwell rising"
    return i


class TestBrief:
    def test_returns_brief_markdown(self, mock_session, client, monkeypatch):
        # db.query(...).order_by(...).limit(...).all() -> rows, for two queries
        story_q = MagicMock()
        story_q.order_by.return_value.limit.return_value.all.return_value = [_story_event()]
        insight_q = MagicMock()
        insight_q.order_by.return_value.limit.return_value.all.return_value = [_insight()]
        mock_session.query.side_effect = [story_q, insight_q]

        monkeypatch.setattr(
            "app.api.routes.brief.get_decision_brief",
            lambda session, redis_client, top_events, top_insights: "## Situation\nAll clear.",
        )

        resp = client.get("/api/v1/brief")
        assert resp.status_code == 200
        body = resp.json()
        assert body["brief"] == "## Situation\nAll clear."
        assert body["as_of"]
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && python -m pytest tests/api/test_brief.py -v`
Expected: FAIL (404, or `ModuleNotFoundError: app.api.routes.brief`).

- [ ] **Step 3: Commit the failing test**

```bash
git add backend/tests/api/test_brief.py
git commit -m "test(api): failing contract test for GET /brief"
```

### Task 16: Implement the brief route

**Files:**
- Create: `backend/app/api/routes/brief.py`
- Modify: `backend/app/api/router.py`

- [ ] **Step 1: Write the route**

```python
from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter
from sqlalchemy import desc

from app.api.deps import DbSession, RedisClient
from app.db.models import Insight, RiskStoryEvent
from app.llm.brief import get_decision_brief
from app.schemas.brief import BriefResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["brief"])

_MAX_EVENTS = 10
_MAX_INSIGHTS = 10


@router.get("/brief", response_model=BriefResponse)
def get_brief(db: DbSession, redis_client: RedisClient) -> BriefResponse:
    """Return the executive Decision Brief as markdown (redis-cached ~1h)."""
    top_events = (
        db.query(RiskStoryEvent)
        .order_by(desc(RiskStoryEvent.event_time))
        .limit(_MAX_EVENTS)
        .all()
    )
    top_insights = (
        db.query(Insight)
        .order_by(desc(Insight.generated_at))
        .limit(_MAX_INSIGHTS)
        .all()
    )

    brief = get_decision_brief(db, redis_client, top_events, top_insights)
    return BriefResponse(brief=brief, as_of=date.today().isoformat())
```

- [ ] **Step 2: Register the router**

In `backend/app/api/router.py`, add with the other imports:

```python
from app.api.routes.brief import router as brief_router
```

and after `router.include_router(story_router)`:

```python
router.include_router(brief_router)
```

- [ ] **Step 3: Run the test to confirm it passes**

Run: `cd backend && python -m pytest tests/api/test_brief.py -v`
Expected: PASS.

- [ ] **Step 4: Run the full backend suite**

Run: `cd backend && python -m pytest -q`
Expected: PASS (nothing else broke).

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routes/brief.py backend/app/api/router.py
git commit -m "feat(api): GET /brief endpoint wired to get_decision_brief"
```

---

## Phase 6 — Frontend: brief client + hero rewire

### Task 17: Add the brief API client

**Files:**
- Create: `frontend/src/api/brief.ts`
- Test: `frontend/src/__tests__/brief.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fetchBrief } from '../api/brief'

describe('fetchBrief', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('returns brief + as_of from the API', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({ brief: '## Hi', as_of: '2026-05-31' }),
      }),
    )
    const result = await fetchBrief()
    expect(result.brief).toBe('## Hi')
    expect(result.as_of).toBe('2026-05-31')
  })
})
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd frontend && npm run test -- brief.test.ts`
Expected: FAIL (cannot resolve `../api/brief`).

- [ ] **Step 3: Write the client**

```ts
import { apiGet } from './client'

export interface Brief {
  brief: string
  as_of: string
}

let _cache: Brief | null = null

export function getCachedBrief(): Brief | null {
  return _cache
}

export async function fetchBrief(): Promise<Brief> {
  const data = await apiGet<Brief>('/api/v1/brief')
  _cache = data
  return data
}
```

- [ ] **Step 4: Run the test to confirm it passes**

Run: `cd frontend && npm run test -- brief.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/brief.ts frontend/src/__tests__/brief.test.ts
git commit -m "feat(api): fetchBrief client + test"
```

### Task 18: Add the templated-fallback helper (pure function, TDD)

**Files:**
- Create: `frontend/src/lib/briefFallback.ts`
- Test: `frontend/src/__tests__/briefFallback.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, it, expect } from 'vitest'
import { buildFallbackBrief } from '../lib/briefFallback'

describe('buildFallbackBrief', () => {
  it('summarizes top risk + bdi move + congestion when data present', () => {
    const md = buildFallbackBrief({
      topRiskTitle: 'Suez transit disruption',
      bdiChangePct7d: -3.2,
      congestedPorts: 4,
    })
    expect(md).toContain('Suez transit disruption')
    expect(md).toContain('softens')
    expect(md).toContain('4')
  })

  it('falls back to a steady-state line when nothing notable', () => {
    const md = buildFallbackBrief({ topRiskTitle: null, bdiChangePct7d: null, congestedPorts: 0 })
    expect(md.toLowerCase()).toContain('steady')
  })
})
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd frontend && npm run test -- briefFallback.test.ts`
Expected: FAIL (cannot resolve module).

- [ ] **Step 3: Write the helper**

```ts
export interface FallbackInputs {
  topRiskTitle: string | null
  bdiChangePct7d: number | null
  congestedPorts: number
}

/**
 * Deterministic 1–2 sentence markdown brief built from live Overview metrics.
 * Used when the LLM brief endpoint fails — never the old hardcoded paragraphs.
 */
export function buildFallbackBrief({ topRiskTitle, bdiChangePct7d, congestedPorts }: FallbackInputs): string {
  if (!topRiskTitle && bdiChangePct7d == null && congestedPorts === 0) {
    return 'Global supply chain risk opens **steady**, with no critical watchpoints across ports and arteries this session.'
  }
  const parts: string[] = []
  if (topRiskTitle) parts.push(`Lead signal: **${topRiskTitle}**.`)
  if (bdiChangePct7d != null) {
    const dir = bdiChangePct7d >= 0 ? 'firms' : 'softens'
    parts.push(`Freight tape ${dir} ${Math.abs(bdiChangePct7d).toFixed(1)}% over 7 days.`)
  }
  parts.push(`${congestedPorts} port${congestedPorts === 1 ? '' : 's'} under congestion watch.`)
  return parts.join(' ')
}
```

- [ ] **Step 4: Run the test to confirm it passes**

Run: `cd frontend && npm run test -- briefFallback.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/briefFallback.ts frontend/src/__tests__/briefFallback.test.ts
git commit -m "feat: templated morning-brief fallback helper + test"
```

### Task 19: Rewire the Overview hero (skeleton-then-swap + markdown)

**Files:**
- Modify: `frontend/src/views/OverviewView.tsx`

- [ ] **Step 1: Add imports**

At the top of `OverviewView.tsx` add:

```tsx
import { ChatMarkdown } from '../components/ChatMarkdown'
import { fetchBrief, getCachedBrief } from '../api/brief'
import { buildFallbackBrief } from '../lib/briefFallback'
```

- [ ] **Step 2: Add brief state**

After the existing `useState` declarations inside `OverviewView` (near line 369, after `marketWindow`), add:

```tsx
  const [brief, setBrief] = useState<string | null>(() => getCachedBrief()?.brief ?? null)
  const [briefAsOf, setBriefAsOf] = useState<string | null>(() => getCachedBrief()?.as_of ?? null)
  const [briefLoading, setBriefLoading] = useState(!getCachedBrief())
  const [briefFailed, setBriefFailed] = useState(false)
```

- [ ] **Step 3: Add the fetch effect**

After the existing data-fetch `useEffect` (the one calling `fetchPorts`/`fetchChokepoints`/…, ending near line 394), add:

```tsx
  useEffect(() => {
    let cancelled = false
    fetchBrief()
      .then((res) => {
        if (cancelled) return
        setBrief(res.brief)
        setBriefAsOf(res.as_of)
        setBriefLoading(false)
      })
      .catch(() => {
        if (cancelled) return
        setBriefFailed(true)
        setBriefLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])
```

- [ ] **Step 4: Replace the hardcoded hero body**

In the hero `<article>` (lines ~416–434): keep the `<p className="label-cap">Morning Brief</p>` eyebrow and the `<h1 …>{buildHeadline(insights, indices)}</h1>`. **Delete** the static dek `<p className="serif mt-5 … italic …">The tape blends…</p>`, the old `<p className="label-cap mt-5">By SupplyTracker risk desk</p>`, and the entire `<div className="mt-6 columns-1 …"> … </div>` block (the two hardcoded paragraphs). In their place insert:

```tsx
          <p className="label-cap mt-5">By SupplyTracker risk desk{briefAsOf ? ` · as of ${briefAsOf}` : ''}</p>
          <div className="mt-6 max-w-3xl text-[color:var(--ink-2)]">
            {briefLoading ? (
              <div className="space-y-3" aria-hidden="true">
                <div className="h-4 w-full bg-[color:var(--paper-2)]" />
                <div className="h-4 w-11/12 bg-[color:var(--paper-2)]" />
                <div className="h-4 w-9/12 bg-[color:var(--paper-2)]" />
              </div>
            ) : (
              <ChatMarkdown
                content={
                  briefFailed || !brief
                    ? buildFallbackBrief({
                        topRiskTitle:
                          insights.find(
                            (i) => i.attention_level === 'critical' || i.attention_level === 'high',
                          )?.title ?? null,
                        bdiChangePct7d: bdi?.change_pct_7d ?? null,
                        congestedPorts,
                      })
                    : brief
                }
              />
            )}
          </div>
```

(`bdi` and `congestedPorts` are already computed in `OverviewView` at lines ~409–411.)

- [ ] **Step 5: Lint + test**

Run: `cd frontend && npm run lint && npm run test`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/OverviewView.tsx
git commit -m "feat(overview): wire Morning Brief hero to real LLM brief (skeleton+fallback)"
```

---

## Phase 7 — Drop the alerts rail

### Task 20: Remove `AlertsRail` from Overview

**Files:**
- Modify: `frontend/src/views/OverviewView.tsx`

- [ ] **Step 1: Delete the `AlertsRail` component**

Remove the entire `function AlertsRail({ insights }: { insights: InsightItem[] }) { … }` definition (lines ~307–357), including the hardcoded "Story" `<section>` ("Watch the narrow lanes first.").

- [ ] **Step 2: Remove its usage + collapse the grid**

Replace the bottom block (lines ~459–469):

```tsx
      <div className="grid gap-8 lg:grid-cols-[2.3fr_1fr]">
        <main className="space-y-10">
          <ArteriesTable chokepoints={sortedChokepoints} loading={chokepointsLoading} />
          {portsError ? (
            <DataState status="error" error={portsError} />
          ) : (
            <PortsDigest ports={sortedPorts} loading={portsLoading} />
          )}
        </main>
        {insightsLoading ? <DataState status="loading" /> : <AlertsRail insights={insights} />}
      </div>
```

with:

```tsx
      <div className="space-y-10">
        <ArteriesTable chokepoints={sortedChokepoints} loading={chokepointsLoading} />
        {portsError ? (
          <DataState status="error" error={portsError} />
        ) : (
          <PortsDigest ports={sortedPorts} loading={portsLoading} />
        )}
      </div>
```

- [ ] **Step 3: Remove now-unused imports**

`StatusDot` was used only by `AlertsRail` and the Overview tables — check: `ArteriesTable`/`PortsDigest` also use `StatusDot`, so keep it. Remove any import that `tsc` now reports as unused (run lint to find out). Keep `insights`, `insightsLoading`, `fetchInsights` (still feed `buildHeadline`, the evidence "Open anomalies" count, and the brief fallback).

- [ ] **Step 4: Lint + test**

Run: `cd frontend && npm run lint && npm run test`
Expected: PASS (zero unused-symbol errors).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/OverviewView.tsx
git commit -m "refactor(overview): drop broken AlertsRail + hardcoded Story aside"
```

---

## Phase 8 — Full verification

### Task 21: End-to-end verification pass

**Files:** none (verification only)

- [ ] **Step 1: Full frontend gate**

Run: `cd frontend && npm run lint && npm run test && npm run build`
Expected: all PASS.

- [ ] **Step 2: Full backend gate**

Run: `cd backend && python -m pytest -q` (or `make test`)
Expected: PASS.

- [ ] **Step 3: Confirm zero generic Tailwind remains in app source**

Run: `cd frontend && grep -rnE "dark:|text-gray-[0-9]|bg-gray-[0-9]|bg-white|indigo" src/ --include=*.tsx | grep -v "__tests__"`
Expected: empty.

- [ ] **Step 4: Visual + behavior check in the running app**

Run: `make up` then open `http://localhost:5173`. Confirm:
- Overview, `#/port/<id>`, `#/chokepoint/<id>` share one editorial look in **both** light and dark themes (toggle the theme).
- Morning Brief hero shows the skeleton, then a real generated markdown brief.
- Stop the backend (`docker compose stop backend`) and reload Overview → hero shows the **templated fallback** (live metrics), not lorem and not a crash. Restart: `docker compose start backend`.
- `curl http://localhost:8000/api/v1/brief` returns `{"brief": "...markdown...", "as_of": "..."}`; a second call within the hour is near-instant (redis cache hit).
- No "Last 24h alerts" rail and no "Watch the narrow lanes first." aside on Overview; layout reflows cleanly to full-width tables.

- [ ] **Step 5: Final commit (only if verification fixups were needed)**

```bash
git add -A
git commit -m "chore: verification fixups for frontend consistency + morning brief"
```

---

## Notes for the implementer

- **Line numbers drift** as you edit. Anchors quoted as strings ("the hero `<article>`", the bottom grid block) are stable — search for them.
- **Recharts color via CSS var:** Recharts accepts `var(--accent)` for `stroke`/`fill` string props in modern browsers. If a specific prop rejects it, read the token once via `getComputedStyle(document.documentElement).getPropertyValue('--accent')` — but try the `var()` form first.
- **Do not touch** `ui/StatusDot.tsx` (already token-based) or the masthead/nav/tape shell (already editorial).
- **`make test` vs `cd backend`:** if the backend runs only in Docker, prefix backend Python/test commands with `docker compose exec -w /app/backend backend …` per the Makefile.
- **`/story` + `/insights` return 0 rows** in the current seed, so the brief endpoint will exercise its cache-miss → LLM path; that is expected. `make collect-all` / `make bootstrap` can seed events if you want richer brief input.
