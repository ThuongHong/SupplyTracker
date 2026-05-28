import React, { useEffect, useRef, useState } from 'react'
import { Route, navigate } from '../../router'
import {
  IconMenu,
  IconX,
  IconChevronLeft,
  IconChevronRight,
} from '../ui/icons'

interface NavItem {
  label: string
  hash: string
  routeNames: Route['name'][]
  icon: React.ReactNode
}

// Three nav items exactly
const NAV_ITEMS: NavItem[] = [
  {
    label: 'Overview',
    hash: '/overview',
    routeNames: ['overview'],
    icon: (
      <svg viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5">
        <path
          fillRule="evenodd"
          d="M3 5a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 5a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 5a1 1 0 011-1h6a1 1 0 110 2H4a1 1 0 01-1-1z"
          clipRule="evenodd"
        />
      </svg>
    ),
  },
  {
    label: 'Ports',
    hash: '/ports',
    routeNames: ['ports', 'ports.detail'],
    icon: (
      <svg viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5">
        <path d="M9 2a1 1 0 000 2h2a1 1 0 100-2H9z" />
        <path
          fillRule="evenodd"
          d="M4 5a2 2 0 012-2 3 3 0 003 3h2a3 3 0 003-3 2 2 0 012 2v11a2 2 0 01-2 2H6a2 2 0 01-2-2V5zm3 4a1 1 0 000 2h.01a1 1 0 100-2H7zm3 0a1 1 0 000 2h3a1 1 0 100-2h-3zm-3 4a1 1 0 100 2h.01a1 1 0 100-2H7zm3 0a1 1 0 100 2h3a1 1 0 100-2h-3z"
          clipRule="evenodd"
        />
      </svg>
    ),
  },
  {
    label: 'Chokepoints',
    hash: '/chokepoints',
    routeNames: ['chokepoints', 'chokepoints.detail'],
    icon: (
      <svg viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5">
        <path
          fillRule="evenodd"
          d="M12 1.586l-4 4v12.828l4-4V1.586zM3.707 3.293A1 1 0 002 4v10a1 1 0 00.293.707L6 18.414V5.586L3.707 3.293zM17.707 5.293L14 1.586v12.828l2.293 2.293A1 1 0 0018 16V6a1 1 0 00-.293-.707z"
          clipRule="evenodd"
        />
      </svg>
    ),
  },
]

const AUTO_COLLAPSE_BREAKPOINT = 760 // px

interface SidebarProps {
  activeRoute: Route
}

export default function Sidebar({ activeRoute }: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false)
  const observerRef = useRef<ResizeObserver | null>(null)

  // Auto-collapse on narrow viewports
  useEffect(() => {
    const check = (width: number) => {
      setCollapsed(width < AUTO_COLLAPSE_BREAKPOINT)
    }

    // Initial check
    check(window.innerWidth)

    observerRef.current = new ResizeObserver((entries) => {
      for (const entry of entries) {
        check(entry.contentRect.width)
      }
    })
    observerRef.current.observe(document.body)

    return () => {
      observerRef.current?.disconnect()
    }
  }, [])

  const isActive = (item: NavItem): boolean =>
    item.routeNames.includes(activeRoute.name)

  const handleNav = (e: React.MouseEvent, hash: string) => {
    e.preventDefault()
    navigate(hash)
  }

  return (
    <aside
      aria-label="Main navigation"
      className={[
        'flex flex-col flex-shrink-0 h-full',
        'bg-gray-50 dark:bg-gray-800',
        'border-r border-gray-200 dark:border-gray-700',
        'transition-all duration-200 ease-in-out',
        collapsed ? 'w-16' : 'w-60',
      ].join(' ')}
    >
      {/* Logo / toggle row */}
      <div
        className={[
          'flex items-center h-14 px-3 border-b border-gray-200 dark:border-gray-700',
          collapsed ? 'justify-center' : 'justify-between',
        ].join(' ')}
      >
        {!collapsed && (
          <span className="font-semibold text-sm text-gray-900 dark:text-gray-100 truncate">
            SupplyTracker
          </span>
        )}
        <button
          onClick={() => setCollapsed((c) => !c)}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className="p-1.5 rounded-md text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          {collapsed ? (
            <IconChevronRight className="w-5 h-5" />
          ) : (
            <IconChevronLeft className="w-5 h-5" />
          )}
        </button>
      </div>

      {/* Nav items — exactly 3 */}
      <nav className="flex-1 py-3 space-y-1 px-2" aria-label="Primary">
        {NAV_ITEMS.map((item) => {
          const active = isActive(item)
          return (
            <a
              key={item.hash}
              href={`#${item.hash}`}
              onClick={(e) => handleNav(e, item.hash)}
              aria-current={active ? 'page' : undefined}
              title={collapsed ? item.label : undefined}
              className={[
                'flex items-center gap-3 rounded-md px-2 py-2 text-sm font-medium',
                'focus:outline-none focus:ring-2 focus:ring-indigo-500',
                'transition-colors duration-100',
                active
                  ? 'bg-indigo-50 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300'
                  : 'text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700',
                collapsed ? 'justify-center' : '',
              ].join(' ')}
            >
              <span className="flex-shrink-0">{item.icon}</span>
              {!collapsed && <span className="truncate">{item.label}</span>}
            </a>
          )
        })}
      </nav>

      {/* Bottom version stamp */}
      {!collapsed && (
        <div className="px-4 py-3 border-t border-gray-200 dark:border-gray-700">
          <p className="text-xs text-gray-400 dark:text-gray-500">v0.1.0</p>
        </div>
      )}
    </aside>
  )
}
