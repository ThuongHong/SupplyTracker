import React, { useEffect, useState } from 'react'
import { IconSun, IconMoon } from '../ui/icons'

const THEME_KEY = 'theme'
type Theme = 'light' | 'dark'

function getStoredTheme(): Theme {
  const stored = localStorage.getItem(THEME_KEY)
  if (stored === 'dark' || stored === 'light') return stored
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function applyTheme(theme: Theme) {
  if (theme === 'dark') {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
  localStorage.setItem(THEME_KEY, theme)
}

export default function Header() {
  const [theme, setTheme] = useState<Theme>(() => {
    // Read from DOM state (already applied by inline script in index.html)
    return document.documentElement.classList.contains('dark') ? 'dark' : 'light'
  })

  const toggleTheme = () => {
    const next: Theme = theme === 'dark' ? 'light' : 'dark'
    applyTheme(next)
    setTheme(next)
  }

  return (
    <header className="flex items-center justify-between h-14 px-4 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 flex-shrink-0">
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
          Supply Chain Risk Dashboard
        </span>
      </div>

      <div className="flex items-center gap-2">
        {/* Theme toggle */}
        <button
          onClick={toggleTheme}
          aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          className="p-2 rounded-md text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-colors"
        >
          {theme === 'dark' ? (
            <IconSun className="w-5 h-5" />
          ) : (
            <IconMoon className="w-5 h-5" />
          )}
        </button>
      </div>
    </header>
  )
}
