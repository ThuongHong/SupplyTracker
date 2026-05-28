## Why

The current SupplyTracker UI uses a generic dark-sidebar dashboard aesthetic that fails to convey the editorial, data-as-story narrative appropriate for logistics analysts who monitor the app all day. A redesign to "The Daily Tape" editorial aesthetic — newsprint paper tones, serif headlines, monospaced figures — will make data scanning faster and more readable.

## What Changes

- Replace sidebar + fixed header layout with a newspaper-style masthead, horizontal nav tabs, and animated ticker tape
- Apply "Daily Tape" design token system: Newsreader serif, Inter UI, JetBrains Mono numbers, warm newsprint paper (`#F1ECE0`) and leather dark (`#15120D`) themes
- Redesign Overview tab: editorial Morning Brief hero section, evidence column, Markets/Indices panel with area chart + watchlist, Arteries atlas placeholder, Ports digest table, side rail with alerts/forecast/story
- Redesign Ports tab: editorial table with congestion bar cells, severity column, search/filter strip using new tokens
- Redesign Chokepoints tab: editorial table with status dots, transit time, delta, severity using new tokens
- Replace Sidebar and Header components with Masthead + NavBar components
- **BREAKING**: Remove sidebar — layout changes from `flex h-screen` with aside to full-width frame layout

## Capabilities

### New Capabilities
- `editorial-shell`: Masthead, horizontal nav, and animated ticker tape replacing sidebar/header shell
- `overview-editorial`: Overview tab redesigned as "The Daily Tape" morning brief with evidence column, indices panel, arteries section, ports digest, and side rail
- `ports-editorial`: Ports tab redesigned with Daily Tape table styling and filter strip
- `chokepoints-editorial`: Chokepoints tab redesigned with Daily Tape table styling

### Modified Capabilities

## Impact

- `frontend/src/App.tsx`: layout restructure
- `frontend/src/components/layout/Header.tsx`: replaced by Masthead
- `frontend/src/components/layout/Sidebar.tsx`: replaced by NavBar
- `frontend/src/views/OverviewView.tsx`: full redesign
- `frontend/src/views/PortsView.tsx`: full redesign  
- `frontend/src/views/ChokepointsView.tsx`: full redesign
- `frontend/src/index.css` or global styles: new CSS custom properties (design tokens)
- Google Fonts: Newsreader, Inter, JetBrains Mono (added to `index.html`)
- No API or backend changes
