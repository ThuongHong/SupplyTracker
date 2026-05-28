## ADDED Requirements

### Requirement: Daily Tape design tokens applied globally
The system SHALL define CSS custom properties on `:root` for light theme and `[data-theme="dark"]` for dark theme, matching the Daily Tape prototype token set: `--paper`, `--paper-2`, `--card`, `--card-2`, `--ink`, `--ink-2`, `--ink-3`, `--ink-4`, `--rule`, `--rule-thin`, `--rule-hair`, `--accent`, `--accent-soft`, `--positive`, `--negative`, `--caution`, `--highlight`, `--f-display`, `--f-body`, `--f-ui`, `--f-mono`.

#### Scenario: Light theme tokens applied on load
- **WHEN** page loads without a stored dark preference
- **THEN** `:root` has `--paper: #F1ECE0` and `--ink: #1A1714` and body background is `var(--paper)`

#### Scenario: Dark theme tokens applied when toggled
- **WHEN** user toggles to dark mode
- **THEN** `[data-theme="dark"]` is set on `<html>` and `--paper` becomes `#15120D` and `--ink` becomes `#ECE3D2`

### Requirement: Google Fonts loaded for editorial typography
The system SHALL load Newsreader (ital,opsz,wght 400–700), Inter (400–700), and JetBrains Mono (400–600) via Google Fonts link tag in `index.html`.

#### Scenario: Fonts available for CSS
- **WHEN** the page is loaded in a browser with network access
- **THEN** `font-family: var(--f-display)` resolves to Newsreader serif and `font-family: var(--f-mono)` resolves to JetBrains Mono

### Requirement: Animated ticker tape replaces static header title
The system SHALL render an animated horizontal scrolling tape above the masthead showing supply chain index symbols, values, and percentage changes. The tape SHALL pause on hover. The tape SHALL fetch real index data from the existing `/api/indices` endpoint and fall back to static placeholder items if the fetch fails.

#### Scenario: Tape renders and scrolls
- **WHEN** the page loads
- **THEN** a horizontal tape strip appears at the top of the page with items scrolling left continuously

#### Scenario: Tape pauses on hover
- **WHEN** user hovers over the tape
- **THEN** animation pauses and resumes on mouse leave

#### Scenario: Tape falls back gracefully
- **WHEN** the indices API is unavailable
- **THEN** the tape shows static placeholder items (BDI, FBX, WCI) rather than an empty strip

### Requirement: Masthead replaces header bar
The system SHALL render a newspaper-style masthead with three zones: left (edition info and date), center (app wordmark "SupplyTracker" in Newsreader serif with kicker "The Daily" above), right (live status summary). The masthead SHALL have a double-rule bottom border.

#### Scenario: App name displayed in masthead
- **WHEN** the page loads
- **THEN** the center zone shows "SupplyTracker" as the large Newsreader wordmark

#### Scenario: Current date shown in edition zone
- **WHEN** the page loads
- **THEN** the left zone displays the current date formatted as "Weekday, Month Day, Year"

### Requirement: Horizontal nav tabs replace sidebar
The system SHALL render a horizontal navigation bar below the masthead with exactly 3 tab items: "Overview", "Ports", "Chokepoints". The active tab SHALL be underlined with a 2px solid `var(--ink)` bottom border. The nav SHALL include a right utility area with the dark/light theme toggle button.

#### Scenario: Overview tab active by default
- **WHEN** the page loads at `#/overview`
- **THEN** the "Overview" tab has `is-active` styling with underline

#### Scenario: Tab navigation works
- **WHEN** user clicks "Ports" tab
- **THEN** URL hash changes to `#/ports` and Ports tab becomes active

#### Scenario: Theme toggle in nav utility area
- **WHEN** user clicks the theme toggle in the nav utility area
- **THEN** theme switches between light and dark

### Requirement: Full-width frame layout
The system SHALL use a full-width scroll layout (no sidebar) with a centered frame (`max-width: 1280px`, `margin: 0 auto`, `padding: 28px 36px 80px`). The overall page background SHALL be `var(--paper)`.

#### Scenario: No sidebar present
- **WHEN** any tab is viewed
- **THEN** there is no left sidebar; content spans full available width inside the frame

#### Scenario: Content centered on wide screens
- **WHEN** viewport is wider than 1280px
- **THEN** the frame content is centered with equal margins on both sides
