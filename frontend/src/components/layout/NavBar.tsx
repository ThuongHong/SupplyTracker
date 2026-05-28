import React, { useEffect, useState } from 'react'
import { navigate, type Route } from '../../router'
import { IconMoon, IconSun } from '../ui/icons'

type Theme = 'light' | 'dark'

const THEME_KEY = 'theme'

const TABS: Array<{ route: Route['name']; label: string; path: string }> = [
  { route: 'overview', label: 'Overview', path: '/overview' },
  { route: 'ports', label: 'Ports', path: '/ports' },
  { route: 'chokepoints', label: 'Chokepoints', path: '/chokepoints' },
]

function parentRouteName(route: Route) {
  if (route.name === 'ports.detail') return 'ports'
  if (route.name === 'chokepoints.detail') return 'chokepoints'
  return route.name
}

function readTheme(): Theme {
  return document.documentElement.dataset.theme === 'dark' ||
    document.documentElement.classList.contains('dark')
    ? 'dark'
    : 'light'
}

function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme
  document.documentElement.classList.toggle('dark', theme === 'dark')
  localStorage.setItem(THEME_KEY, theme)
}

export default function NavBar({ activeRoute }: { activeRoute: Route }) {
  const [theme, setTheme] = useState<Theme>(() => readTheme())
  const active = parentRouteName(activeRoute)

  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  return (
    <nav className="nav mt-4 flex flex-col gap-3 py-3 md:flex-row md:items-center md:justify-between">
      <div className="flex flex-wrap gap-2">
        {TABS.map((tab) => {
          const isActive = active === tab.route
          return (
            <button
              key={tab.route}
              type="button"
              onClick={() => navigate(tab.path)}
              className={[
                'ui border-b-2 px-1 py-2 text-sm font-semibold uppercase text-[color:var(--ink-2)]',
                isActive
                  ? 'border-[color:var(--ink)] text-[color:var(--ink)]'
                  : 'border-transparent hover:border-[color:var(--rule-thin)] hover:text-[color:var(--ink)]',
              ].join(' ')}
              aria-current={isActive ? 'page' : undefined}
            >
              {tab.label}
            </button>
          )
        })}
      </div>

      <div className="flex items-center gap-2">
        <span className="label-cap hidden sm:inline">Utility</span>
        <button
          type="button"
          onClick={() => setTheme((current) => (current === 'dark' ? 'light' : 'dark'))}
          className="ui inline-flex items-center gap-2 border border-[color:var(--rule-thin)] bg-[color:var(--card)] px-3 py-2 text-xs font-semibold text-[color:var(--ink)] hover:bg-[color:var(--card-2)] focus:outline-none focus:ring-2 focus:ring-[color:var(--accent)]"
          aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          {theme === 'dark' ? <IconSun className="h-4 w-4" /> : <IconMoon className="h-4 w-4" />}
          {theme === 'dark' ? 'Light' : 'Dark'}
        </button>
      </div>
    </nav>
  )
}
