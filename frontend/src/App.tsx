import React, {
  lazy,
  Suspense,
  useEffect,
  useState,
} from 'react'
import { currentRoute, parseHash, navigate, Route } from './router'
import Tape from './components/layout/Tape'
import Masthead from './components/layout/Masthead'
import NavBar from './components/layout/NavBar'
import { DataState } from './components/ui/DataState'
import ChatbotWidget from './components/ChatbotWidget'

// Eager-loaded tab views (small, always needed)
const OverviewView = lazy(() => import('./views/OverviewView'))
const PortsView = lazy(() => import('./views/PortsView'))
const ChokepointsView = lazy(() => import('./views/ChokepointsView'))

// Lazy detail views
const PortDetailView = lazy(() => import('./views/PortDetailView'))
const ChokepointDetailView = lazy(() => import('./views/ChokepointDetailView'))

function RouterOutlet({ route }: { route: Route }) {
  return (
    <Suspense fallback={<DataState status="loading" />}>
      {route.name === 'overview' && <OverviewView />}
      {route.name === 'ports' && <PortsView />}
      {route.name === 'ports.detail' && <PortDetailView id={route.id} />}
      {route.name === 'chokepoints' && <ChokepointsView />}
      {route.name === 'chokepoints.detail' && <ChokepointDetailView id={route.id} />}
    </Suspense>
  )
}

export default function App() {
  const [route, setRoute] = useState<Route>(() => {
    const r = currentRoute()
    // On initial load, if at root, redirect to #/overview
    if (
      !window.location.hash ||
      window.location.hash === '#' ||
      window.location.hash === '#/'
    ) {
      navigate('/overview')
      return { name: 'overview' }
    }
    return r
  })

  useEffect(() => {
    function onHashChange() {
      const r = parseHash(window.location.hash)
      setRoute(r)
      // If parseHash returned overview due to legacy redirect, also update the URL
      if (
        r.name === 'overview' &&
        window.location.hash !== '#/overview'
      ) {
        navigate('/overview')
      }
    }

    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  return (
    <div className="min-h-screen bg-[color:var(--paper)] text-[color:var(--ink)]">
      <Tape />
      <div className="frame">
        <Masthead />
        <NavBar activeRoute={route} />
        <main className="pt-8">
          <RouterOutlet route={route} />
        </main>
      </div>
      <ChatbotWidget />
    </div>
  )
}
