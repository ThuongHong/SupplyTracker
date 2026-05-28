import React, {
  lazy,
  Suspense,
  useEffect,
  useState,
} from 'react'
import { currentRoute, parseHash, navigate, Route } from './router'
import Sidebar from './components/layout/Sidebar'
import Header from './components/layout/Header'
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
    <div className="flex h-screen overflow-hidden bg-white dark:bg-gray-900">
      <Sidebar activeRoute={route} />
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <Header />
        <main className="flex-1 overflow-auto p-4 md:p-6">
          <RouterOutlet route={route} />
        </main>
      </div>
      <ChatbotWidget />
    </div>
  )
}
