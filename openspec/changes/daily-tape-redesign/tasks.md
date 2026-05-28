## 1. Design Tokens and Fonts

- [x] 1.1 Add Google Fonts link tag to `frontend/index.html` (Newsreader, Inter, JetBrains Mono)
- [x] 1.2 Add Daily Tape CSS custom property tokens to `frontend/src/index.css` (`:root` light theme + `[data-theme="dark"]` dark theme tokens: `--paper`, `--paper-2`, `--card`, `--card-2`, `--ink`, `--ink-2`, `--ink-3`, `--ink-4`, `--rule`, `--rule-thin`, `--rule-hair`, `--accent`, `--accent-soft`, `--positive`, `--negative`, `--caution`, `--highlight`, `--f-display`, `--f-body`, `--f-ui`, `--f-mono`)
- [x] 1.3 Add editorial utility CSS classes to `index.css` (`.mono`, `.ui`, `.serif`, `.label-cap`, `.rule-thin`, `.rule-double`, `.section__head`, `.dtable`, `.bar-cell`, `.anomaly`, `.frame`, `.tape`, `.masthead`, `.nav`)

## 2. Layout Shell Components

- [x] 2.1 Create `frontend/src/components/layout/Tape.tsx` — animated scrolling ticker that fetches index data from `fetchIndices()` and scrolls horizontally, pausing on hover; falls back to static items on error
- [x] 2.2 Create `frontend/src/components/layout/Masthead.tsx` — three-zone newspaper masthead (edition/date left, "SupplyTracker" wordmark center, live status right) with double-rule bottom border
- [x] 2.3 Create `frontend/src/components/layout/NavBar.tsx` — horizontal nav with 3 tabs (Overview, Ports, Chokepoints), active underline indicator, theme toggle button in utility area; accepts `activeRoute` and calls `navigate()`

## 3. App Layout Restructure

- [x] 3.1 Rewrite `frontend/src/App.tsx` to use full-width frame layout: `<Tape />` → `<div class="frame">` → `<Masthead />` → `<NavBar />` → `<main>` → `<RouterOutlet />` → `</div>` with `<ChatbotWidget />` as overlay; remove Sidebar and Header imports

## 4. Overview Tab Redesign

- [x] 4.1 Rewrite `frontend/src/views/OverviewView.tsx` — Morning Brief hero: two-column grid (brief left 2.4fr, evidence right 1fr) using Newsreader serif headline built from real insights data, evidence rows with live index/anomaly counts
- [x] 4.2 Add Markets/Indices panel to OverviewView — restyled version of existing IndicesPanel with `section__head` double-rule, index tabs with mono values + delta colors, 7D/30D/90D range pills, area chart, and side watchlist
- [x] 4.3 Add Arteries section to OverviewView — `section__head` + `dtable` table of chokepoints (name+region, status dot, transit time, delta) using `fetchChokepoints()` data
- [x] 4.4 Add two-column body layout to OverviewView (main 2.3fr + siderail 1fr): main column has Arteries + Ports digest table; siderail has Alerts feed (from `fetchInsights()`) with severity dots, editorial serif text

## 5. Ports Tab Redesign

- [x] 5.1 Rewrite `frontend/src/views/PortsView.tsx` — replace card grid with `section__head` + filter strip (search input + severity pills styled with editorial tokens) + `dtable` table (columns: Port/country, Severity, Risk score mono, Congestion bar-cell, Status dot, Star toggle)
- [x] 5.2 Ensure tracked ports sort to top and star toggle works inline in the new table rows

## 6. Chokepoints Tab Redesign

- [x] 6.1 Rewrite `frontend/src/views/ChokepointsView.tsx` — replace card grid with `section__head` + filter strip + `dtable` table (columns: Chokepoint/region, Severity, Risk score, Status dot, Transit time mono, Delta colored mono, Last updated)
- [x] 6.2 Ensure severity filter and search work with new table layout

## 7. Cleanup

- [x] 7.1 Delete or deprecate `frontend/src/components/layout/Sidebar.tsx` and `Header.tsx` (no longer imported)
- [x] 7.2 Verify ChatbotWidget still renders correctly as a floating overlay on top of the new layout
- [x] 7.3 Run `npm run build` in `frontend/` and confirm no TypeScript errors
- [x] 7.4 Verify all 3 tabs load, render real data, and that navigation (tab clicks, row clicks to detail pages) works correctly
