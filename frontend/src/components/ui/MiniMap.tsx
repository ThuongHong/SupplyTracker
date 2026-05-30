import React, { useEffect, useRef } from 'react'
import maplibregl, { type Map as MaplibreMap } from 'maplibre-gl'

interface MiniMapProps {
  /** [longitude, latitude] */
  center: [number, number]
  zoom?: number
  width?: string | number
  height?: string | number
  className?: string
  /** Optional marker at center */
  showMarker?: boolean
  /** Allow pan/zoom interaction + zoom buttons (default true) */
  interactive?: boolean
}

const FREE_STYLE_URL =
  'https://demotiles.maplibre.org/style.json'

export function MiniMap({
  center,
  zoom = 4,
  width = '100%',
  height = 200,
  className = '',
  showMarker = true,
  interactive = true,
}: MiniMapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MaplibreMap | null>(null)
  const markerRef = useRef<maplibregl.Marker | null>(null)

  useEffect(() => {
    if (!containerRef.current) return

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: FREE_STYLE_URL,
      center,
      zoom,
      attributionControl: false,
      interactive,
    })

    map.addControl(
      new maplibregl.AttributionControl({ compact: true }),
      'bottom-right',
    )

    if (interactive) {
      map.addControl(
        new maplibregl.NavigationControl({ showCompass: false }),
        'top-right',
      )
    }

    mapRef.current = map

    if (showMarker) {
      markerRef.current = new maplibregl.Marker({ color: '#6366f1' })
        .setLngLat(center)
        .addTo(map)
    }

    return () => {
      markerRef.current?.remove()
      map.remove()
      mapRef.current = null
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Update center + zoom when props change
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    map.flyTo({ center, zoom, duration: 600 })
    markerRef.current?.setLngLat(center)
  }, [center[0], center[1], zoom]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div
      ref={containerRef}
      className={['rounded-lg overflow-hidden', className].join(' ')}
      style={{
        width: typeof width === 'number' ? `${width}px` : width,
        height: typeof height === 'number' ? `${height}px` : height,
      }}
      aria-label="Map showing location"
      role="img"
    />
  )
}
