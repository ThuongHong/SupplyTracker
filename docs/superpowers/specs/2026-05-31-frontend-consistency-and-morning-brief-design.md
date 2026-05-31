# Design: Frontend consistency + real Morning Brief

- **Date:** 2026-05-31
- **Branch:** feat/portwatch-insights
- **Status:** Approved (brainstorming complete)
- **Author:** SupplyTracker / risk desk

## Problem

Two related defects in the SupplyTracker frontend.

### 1. The Morning Brief is fake

`frontend/src/views/OverviewView.tsx` renders a large editorial "Morning Brief"
hero (lines ~413–453). Only the headline is lightly data-derived
(`buildHeadline()`); the dek, byline, and two body paragraphs are **hardcoded
static strings** — identical on every load.

Meanwhile:

- A real LLM brief generator exists: `backend/app/llm/brief.py :: get_decision_brief()`
  (prompt in `backend/app/llm/prompts.py :: DECISION_BRIEF_SYSTEM`, redis-cached
  via `decision_brief_cache_ttl_s = 3600`).
- **No API route calls it.** Clean greps across `backend/app` find `brief` only
  in `brief.py`, `prompts.py`, `dashboard.py`, `grounding.py`, `config.py` — never
  in `backend/app/api/routes/`. (One corrupted file read during exploration
  appeared to show a `/story/brief` route; this contradicted every grep and is
  treated as a read glitch. **Implementation must re-verify** whether such a
  route exists before adding a new one.)
- A genuinely data-driven AI summary already renders lower on the page in
  `frontend/src/components/MarketBrief.tsx` (`<Card title="AI summary">` →
  `data.narrative` from `GET /market/insights`). It is a *market* summary, not the
  full decision brief, and it is buried below the fake hero.

### 1b. The "Last 24h alerts" rail is broken + redundant

`OverviewView.tsx :: AlertsRail` (lines ~307–357) reads fields that **do not
exist** on `InsightItem` (confirmed against `frontend/src/api/types.ts` and
`backend/app/schemas/insights.py`):

- `item.entity_name ?? item.entity_type ?? 'Signal'` — neither field exists on
  an insight (real entity is in `affected_entities[]`), so the eyebrow always
  renders the literal **"Signal"**.
- `item.timestamp ? … : 'Live'` — there is no `timestamp` field (it is
  `generated_at`), so the byline always renders **"Live"**.

The card body (title + narrative) does render, but eyebrow + timestamp are dead
placeholders. The rail is also **redundant** — the same critical/high insights
already drive the hero headline (`buildHeadline`) and the evidence rail's "Open
anomalies" count — and it carries a **hardcoded** "Story" aside ("Watch the
narrow lanes first."), the same anti-pattern as the fake hero.

A real event feed exists and is unused on the front page: `GET /story` returns
`RiskStoryEvent` rows with genuine `entity_name`, `event_time`, `severity`,
`event_type`, and `narrative` (verified: 16 seeded events, e.g. a critical
"Suez Canal" transit disruption). There is **no frontend story client** yet.

### 2. Inconsistent design language

Two clashing visual systems coexist:

| Layer | Style | Tokens |
|---|---|---|
| Overview, MarketBrief | **editorial** — masthead, ticker tape, serif headlines, `.section__head` double-rules, `.dtable`, `.bar-cell`, paper/ink palette | CSS custom properties in `index.css` (`--paper`, `--ink`, `--rule`, `--accent`, …), theme-aware via `[data-theme="dark"]` |
| Port/Chokepoint detail + shared UI | **generic dashboard** — `<Card>` boxes, `rounded-xl`, `shadow-sm`, sans headings, indigo focus rings | hardcoded Tailwind `gray-*` / `indigo-*` / `white` + manual `dark:` variants |

**Root cause:** the inconsistency is not just in the two detail *views*. The
shared components they compose hardcode generic colors, so even after the views
are restyled they would still look generic. 24 files carry
`dark:` / `text-gray` / `focus:ring-indigo` / `bg-white` / `rounded-lg`:

- **Views (2):** `PortDetailView.tsx`, `ChokepointDetailView.tsx`
- **Charts/feature (7):** `charts/AnomalyCard`, `charts/EntitySummary`,
  `charts/IndicesPanel`, `charts/VesselMixChart`, `MacroSensitivity`,
  `EventLog`, `MarketBrief`
- **Shared UI (13):** `ui/Card`, `ui/Badge`, `ui/DataState`, `ui/Tabs`,
  `ui/WindowPicker`, `ui/RiskKpis`, `ui/MiniMap`, `ui/InsightRow`,
  `ui/AreaChart`, `ui/StatusDot`, `ui/AskAIButton`, `ui/InfoTooltip`
- **Chatbot (2):** `ChatbotWidget`, `ChatMarkdown` (+ `AskAIButton`)

Fixing the shared layer once propagates to both detail pages **and** Overview.

## Goals

1. One consistent editorial design language across the whole app.
2. The Morning Brief hero shows a **real, generated** decision brief.
3. Low churn in view files; centralize styling in the design system.

## Non-goals

- No redesign of the underlying data model or risk scoring.
- No change to the masthead/nav/tape shell (already editorial).
- No new charts; only restyling existing ones.

## Decisions (locked via brainstorming)

| Topic | Decision |
|---|---|
| Design direction | Editorial base + lighter **"inside page"** variant for detail pages |
| Inside-page variant | **Ruled sections, no boxes** — drop `<Card>` on detail pages; use `.section__head` + bare content (like Overview's tables) |
| Migration approach | **B — editorial component classes**: add reusable classes to `index.css` `@layer`, rewrite shared components to use them, delete all `dark:` (tokens auto-swap via `[data-theme]`) |
| Scope | **Shared layer + detail pages** (root-cause fix), **including the chatbot** |
| Morning Brief | **Wire to the real LLM brief** via a backend endpoint |
| Hero loading | **Skeleton-then-swap** — masthead + skeleton dek paint immediately, real brief swaps in when resolved |
| Brief failure | **Templated fallback** built from live metrics (top risks + index moves); never the old hardcoded lorem |
| Brief format | **Markdown**, rendered rich with existing `react-markdown` + `remark-gfm` |
| Alerts rail | **Replace with a real `/story` feed** — drop the buggy insight-based rail + hardcoded "Story" aside; render genuine 24h `RiskStoryEvent`s, editorially styled |

## Design

### A. Editorial component class layer (`index.css`)

Add to the existing `@layer utilities` block, built only from existing tokens:

- `.card` — editorial panel: `background: var(--card)`; `border: 1px solid
  var(--rule-thin)`; no shadow; square corners. Replaces the generic
  `rounded-xl border-gray-200 bg-white shadow-sm`.
- `.card__head` — title row: `border-bottom: 1px solid var(--rule-hair)`; title
  uses `.label-cap` styling.
- `.card--inside` — flatter modifier (hair border only) for the rare detail-page
  panel that still needs a frame (map, charts). Most detail content uses bare
  `.section__head` sections instead (per "ruled sections, no boxes").
- `.tab` / `.tab--active` — underline tab built on `--ink` / `--rule-thin`;
  active = `border-bottom: 2px solid var(--accent)`, `color: var(--ink)`.
- `.seg` / `.seg__btn` / `.seg__btn--active` — segmented control for
  `WindowPicker` and the `MetricDrilldown` range buttons, matching the existing
  inline `MarketPanel` range buttons (`bg var(--ink)` active on `var(--paper)`).
- `.pill` + severity modifiers (`.pill--low/moderate/elevated/high/critical/
  unknown/info`) — replaces `Badge`'s `green/amber/orange/red` Tailwind with
  token-mapped colors: low→`--positive`, moderate/elevated→`--caution`,
  high/critical→`--negative`, info→`--accent`, unknown→`--ink-4`. Tinted
  backgrounds via `color-mix(in srgb, <token> N%, transparent)`.
- `.spinner` — replaces the indigo `animate-spin` SVG; `border-color:
  var(--rule-thin)`, top `var(--accent)`.
- `.focus-ring` (or a shared `:focus-visible` rule) — replaces
  `focus:ring-indigo-500` with an `--accent` outline.

All `dark:` variants are **deleted** from the migrated components — the tokens
already invert under `[data-theme="dark"]`.

### B. Component rewrites (props unchanged)

Internals only; public APIs stay identical so views barely change.

- `ui/Card` → `.card` / `.card__head`; accept optional `inside` prop →
  `.card--inside`.
- `ui/Badge` / `SeverityBadge` → `.pill` + severity modifier (drop the
  `variantClasses` Tailwind map).
- `ui/Tabs` → `.tab` classes; `focus-ring` instead of indigo.
- `ui/WindowPicker` → `.seg`.
- `ui/DataState` → `.spinner`; error/empty icons use `--negative` / `--ink-4`;
  retry link uses `--accent`.
- `ui/RiskKpis`, `ui/MiniMap`, `ui/InsightRow`, `ui/StatusDot`,
  `ui/AreaChart`, `ui/AskAIButton`, `ui/InfoTooltip` → swap gray/indigo for
  tokens; remove `dark:`.
- `charts/*` (`AnomalyCard`, `EntitySummary`, `IndicesPanel`, `VesselMixChart`)
  + `MacroSensitivity`, `EventLog` → token swap. Chart series colors that were
  literal hex (`#6366f1`, `#22c55e`) move to `--accent` / `--positive`.
- `ChatbotWidget`, `ChatMarkdown`, `AskAIButton` → token swap.

### C. Detail-view restyle (ruled, no boxes)

In `PortDetailView.tsx` and `ChokepointDetailView.tsx`:

- Header: serif `h1` (`text-[color:var(--ink)]`), `.label-cap` sub-line,
  `.seg` window picker, token-styled back/sync/untrack buttons (no indigo, no
  gray).
- Replace each `<Card title="…">` block with a `<section>` + `.section__head`
  (`.label-cap` eyebrow + serif `h2`) and bare content beneath, matching
  Overview's `ArteriesTable` / `PortsDigest` pattern.
- Keep `.card--inside` only where a visual frame genuinely helps (the `MiniMap`,
  possibly the vessel-mix chart).
- Tabs use the new `.tab` classes.

### D. Morning Brief — real LLM brief

**Backend**

1. Re-verify no brief route exists. If absent, add
   `GET /api/v1/brief` (own route module or fold into an existing one):
   - Select top risk events (`RiskStoryEvent` by severity) + recent `Insight`s,
     mirroring `_build_brief_prompt`'s inputs.
   - Call `get_decision_brief(session, redis_client, top_events, top_insights)`
     (already redis-cached; logs `LLMUsageLog`).
   - Return `{ "brief": "<markdown>", "as_of": "<date>" }`.
   - Register the router in `backend/app/api/router.py`.

**Frontend**

2. `frontend/src/api/brief.ts` — `fetchBrief()` returning `{ brief, as_of }`,
   following the `fetchMarketInsights` pattern (optional in-memory cache).
3. `OverviewView` hero (`MorningBrief` extracted as a component):
   - Headline: keep `buildHeadline()` (cheap, data-derived) for instant paint.
   - Evidence rail: unchanged (already live).
   - Body: **skeleton-then-swap** — render a skeleton dek immediately, call
     `fetchBrief()`, then render the markdown brief with `react-markdown` +
     `remark-gfm` (same stack as `ChatMarkdown`) inside the editorial column
     layout. Byline becomes "By SupplyTracker risk desk · as of {as_of}".
   - **Templated fallback** on error/timeout: build a deterministic 1–2 sentence
     brief from live data already in `OverviewView` state (top
     critical/high insight titles, BDI 7D move, congested-port count). Never
     render the old hardcoded paragraphs.
4. Delete the hardcoded dek + two body `<p>` paragraphs.
5. Resolve the brief duplication: the `MarketBrief` "AI summary" card stays as
   the *market* desk summary lower on the page (distinct from the decision
   brief). Update its doc comment so it no longer claims to be "the morning
   brief".

### E. Alerts rail → real `/story` feed

Replace `AlertsRail` (and its hardcoded "Story" aside) on `OverviewView`:

1. `frontend/src/api/story.ts` — `fetchStory()` hitting `GET /story`, plus a
   `StoryEvent` type in `types.ts` mirroring the backend `StoryEventItem`
   (`event_key`, `event_time`, `entity_type`, `entity_id`, `entity_name`,
   `event_type`, `severity`, `narrative`, `attention_level`, …).
2. New editorial rail component rendering the real events: `.label-cap` eyebrow
   = `entity_name` (real, no longer "Signal"), serif title = `event_type` /
   narrative summary, `.pill` severity badge, `.mono` timestamp from
   `event_time` (no longer "Live"), `StatusDot` by severity. Sort by
   `event_time` desc; cap ~5.
3. Empty state via `DataState status="empty"` when `/story` is empty.
4. Delete `AlertsRail`, the hardcoded "Story" aside, and the unused
   insight-feeds-the-rail wiring. The hero headline/evidence rail still consume
   `insights`; `/story` powers the new rail.

## Risks / tradeoffs

- **LLM latency / cost** on cold cache — mitigated by redis cache (1h TTL),
  skeleton-then-swap (never blocks paint), and the templated fallback.
- **Large surface (24 files)** — mitigated by Approach B: most edits are
  mechanical class swaps; component props stay stable so views are low-touch.
- **`color-mix` browser support** — already used in `index.css` (`.dtable`
  hover, `.anomaly`); no new risk.
- **Pill contrast** — verify WCAG AA for token-tinted pills in both themes
  (the old Badge comment claimed AA; re-check after the token swap).

## Verification

- `npm run lint` (tsc) + `npm run test` (vitest) green.
- Visual pass in the running app (`make up`, http://localhost:5173):
  Overview `#/`, Port `#/port/<id>`, Chokepoint `#/chokepoint/<id>` — confirm
  one consistent editorial look in **both** light and dark themes.
- Hero shows a real brief; kill the backend / force an error to confirm the
  templated fallback (not lorem) appears.
- `GET /api/v1/brief` returns markdown; second call within the hour is a cache
  hit.
- New alerts rail shows real `/story` events with actual entity names + event
  times (no "Signal"/"Live" placeholders); empty `/story` shows the empty state.

## Out of scope / follow-ups

- Streaming the brief token-by-token (current design swaps the whole result).
- Consolidating `OverviewView`'s inline `[color:var(--…)]` soup into the new
  component classes (opportunistic, not required).
