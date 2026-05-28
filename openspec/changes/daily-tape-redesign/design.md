## Context

SupplyTracker is a React + Vite + Tailwind frontend consuming a FastAPI/PostgreSQL backend. Current layout: collapsible sidebar (`w-60`/`w-16`) + fixed `h-14` header + scrollable main. Three tab views (Overview, Ports, Chokepoints) plus detail views. ChatbotWidget floats bottom-right.

The design source is "The Daily Tape" — a newspaper-editorial HTML/CSS/JS prototype exported from Claude Design. Target aesthetic: warm newsprint paper, Newsreader serif, Inter UI, JetBrains Mono figures, double-rule mastheads, editorial hierarchy.

## Goals / Non-Goals

**Goals:**
- Apply Daily Tape design tokens via CSS custom properties on `:root` + `[data-theme=dark]`
- Replace sidebar/header shell with Masthead + horizontal NavBar + Tape ticker
- Full-width frame layout (max-width 1280px, centered) replacing flex-with-sidebar
- Redesign all 3 tab views to use editorial component patterns from the prototype
- Preserve all existing data fetching, routing, and ChatbotWidget

**Non-Goals:**
- No backend or API changes
- No new data sources
- No changes to routing logic or URL hash scheme
- No redesign of PortDetailView or ChokepointDetailView (detail pages stay as-is for now)

## Decisions

### D1: CSS custom properties over Tailwind utility classes for design tokens

Daily Tape tokens (`--paper`, `--ink`, `--accent`, `--f-display`, etc.) don't map to Tailwind's default palette. Adding them as CSS vars on `:root` lets components use them directly without extending `tailwind.config.ts`. We can still use Tailwind for layout (flex, grid, spacing) and override colors inline or via className when needed.

Alternatives: Extend tailwind.config.ts with all tokens. Rejected — the token set is large and editorial-specific, CSS vars are simpler and match the prototype directly.

### D2: Masthead + NavBar as new layout components; retire Sidebar and Header

`Sidebar.tsx` and `Header.tsx` are deleted and replaced by:
- `Masthead.tsx` — newspaper header with app name, date, edition info
- `NavBar.tsx` — horizontal tab navigation (Overview / Ports / Chokepoints)
- `Tape.tsx` — animated scrolling ticker (real index data from existing API)

App.tsx layout changes from `flex h-screen` with sidebar to a full-page scroll: `<Tape /> <div class="frame"> <Masthead /> <NavBar /> <main> ... </main> </div>`.

### D3: Preserve existing view component boundaries

Each view (OverviewView, PortsView, ChokepointsView) is fully rewritten to use Daily Tape editorial patterns but keeps the same file paths and import contracts. Data fetching hooks/calls inside each view remain unchanged.

### D4: Font loading via index.html link tag

Google Fonts (Newsreader, Inter, JetBrains Mono) are added to `frontend/index.html` via `<link>` tag — same as the prototype. No npm font packages needed.

### D5: Theme toggle moves to NavBar utility area

The dark/light toggle was in Header. It moves to the NavBar's right utility strip (same location as the prototype's nav__util area), styled as a small `nav__btn`.

## Risks / Trade-offs

- [Tailwind purge] CSS vars referenced only in JS strings won't be purged, but since we're using `var(--token)` syntax in inline styles/CSS, this is fine.
- [Font load jank] Newsreader is a web font; first paint may show fallback serif. Mitigation: `font-display: swap` is default for Google Fonts.
- [Ticker with real data] Tape uses live index data from `fetchIndices()`; if the API is slow, ticker shows empty. Mitigation: fall back to static placeholder items while loading.
- [Detail views unstyled] PortDetailView and ChokepointDetailView will look mismatched after shell changes. Accept for now — they're navigated to from list views and still functional.

## Migration Plan

1. Add fonts to `index.html`
2. Add CSS tokens to `index.css`
3. Add new layout components (Masthead, NavBar, Tape)
4. Rewrite App.tsx layout
5. Rewrite OverviewView, PortsView, ChokepointsView
6. Delete Sidebar.tsx and Header.tsx (or keep but unused)

Rollback: git revert the branch. No DB migration, no API changes.

## Open Questions

- Should the ticker show real-time index data or static placeholders? → Use real `fetchIndices()` data, fall back gracefully.
- Keep ChatbotWidget? → Yes, it remains as a floating overlay unchanged.
